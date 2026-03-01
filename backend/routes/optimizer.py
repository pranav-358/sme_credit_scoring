"""
optimizer.py — Flask route for Loan Amount Optimizer
"""

import os, sys, json
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from models.loan_application import LoanApplication

optimizer_bp = Blueprint('optimizer', __name__, url_prefix='/optimize')

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR      = os.path.normpath(os.path.join(BACKEND_DIR, '..', '..', 'ml'))
if ML_DIR not in sys.path:
    sys.path.insert(0, ML_DIR)


@optimizer_bp.route('/<int:app_id>')
@login_required
def show(app_id):
    application = LoanApplication.query.filter_by(
        id=app_id, user_id=current_user.id
    ).first_or_404()

    # Must be scored first
    if application.ai_credit_score is None:
        return redirect(url_for('score.run_scoring', app_id=app_id))

    from optimizer import optimize
    result = optimize(application, application.ai_credit_score)

    # Load explanation for context
    explanation = {}
    if application.explanation_json:
        try:
            explanation = json.loads(application.explanation_json)
        except Exception:
            pass

    from scorer import get_band
    band = get_band(application.ai_credit_score)

    return render_template('optimizer.html',
                           application=application,
                           result=result,
                           band=band,
                           explanation=explanation)