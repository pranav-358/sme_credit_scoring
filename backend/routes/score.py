"""
score.py — Flask routes for credit scoring + SHAP explanation
"""

import os, sys, json
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from extensions import db
from models.loan_application import LoanApplication

score_bp = Blueprint('score', __name__, url_prefix='/score')

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR      = os.path.normpath(os.path.join(BACKEND_DIR, '..', '..', 'ml'))
UTILS_DIR   = os.path.normpath(os.path.join(BACKEND_DIR, '..', 'utils'))

for p in [ML_DIR, UTILS_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)


@score_bp.route('/run/<int:app_id>')
@login_required
def run_scoring(app_id):
    application = LoanApplication.query.filter_by(
        id=app_id, user_id=current_user.id
    ).first_or_404()

    try:
        from feature_builder import application_to_features
        from scorer import score_application
        from explainer import explain

        feat_dict, feat_array = application_to_features(application)
        result                = score_application(feat_array)

        # Generate SHAP explanation
        explanation = explain(
            feature_dict  = feat_dict,
            feature_array = feat_array,
            score         = result['credit_score'],
            risk_category = result['risk_category'],
        )

        # Persist to DB
        application.ai_credit_score  = result['credit_score']
        application.risk_category    = result['risk_category']
        application.explanation_json = json.dumps(explanation)
        application.status           = 'pending'
        db.session.commit()

        return redirect(url_for('score.result', app_id=app_id))

    except FileNotFoundError as e:
        return render_template('score_error.html', error=str(e)), 500
    except Exception as e:
        import traceback
        return render_template('score_error.html', error=traceback.format_exc()), 500


@score_bp.route('/result/<int:app_id>')
@login_required
def result(app_id):
    application = LoanApplication.query.filter_by(
        id=app_id, user_id=current_user.id
    ).first_or_404()

    if application.ai_credit_score is None:
        return redirect(url_for('score.run_scoring', app_id=app_id))

    from scorer import get_band
    band = get_band(application.ai_credit_score)

    # Parse saved explanation
    explanation = {}
    if application.explanation_json:
        try:
            explanation = json.loads(application.explanation_json)
        except Exception:
            explanation = {}

    return render_template('score_result.html',
                           application=application,
                           band=band,
                           explanation=explanation)