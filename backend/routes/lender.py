"""
lender.py — Lender Dashboard routes
"""

import os, sys, json
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.loan_application import LoanApplication
from models.user import User

lender_bp = Blueprint('lender', __name__, url_prefix='/lender')

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR      = os.path.normpath(os.path.join(BACKEND_DIR, '..', '..', 'ml'))
if ML_DIR not in sys.path:
    sys.path.insert(0, ML_DIR)


def lender_required(f):
    """Decorator: only lenders can access these routes."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'lender':
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated


@lender_bp.route('/dashboard')
@login_required
@lender_required
def dashboard():
    # ── Fetch all applications with user info ──────────────────────────────
    all_apps = (LoanApplication.query
                .join(User, LoanApplication.user_id == User.id)
                .order_by(LoanApplication.submitted_at.desc())
                .all())

    # ── Filter ─────────────────────────────────────────────────────────────
    risk_filter   = request.args.get('risk',   'all')
    status_filter = request.args.get('status', 'all')
    search        = request.args.get('search', '').strip().lower()

    filtered = all_apps
    if risk_filter != 'all':
        filtered = [a for a in filtered if a.risk_category == risk_filter]
    if status_filter != 'all':
        filtered = [a for a in filtered if a.status == status_filter]
    if search:
        filtered = [a for a in filtered
                    if search in a.business_name.lower()
                    or search in a.industry.lower()
                    or search in a.user.full_name.lower()]

    # ── Analytics ──────────────────────────────────────────────────────────
    scored = [a for a in all_apps if a.ai_credit_score]
    analytics = {
        'total'          : len(all_apps),
        'pending'        : sum(1 for a in all_apps if a.status == 'pending'),
        'approved'       : sum(1 for a in all_apps if a.status == 'approved'),
        'rejected'       : sum(1 for a in all_apps if a.status == 'rejected'),
        'low_risk'       : sum(1 for a in all_apps if a.risk_category == 'Low'),
        'medium_risk'    : sum(1 for a in all_apps if a.risk_category == 'Medium'),
        'high_risk'      : sum(1 for a in all_apps if a.risk_category == 'High'),
        'avg_score'      : round(sum(a.ai_credit_score for a in scored) / len(scored), 0) if scored else 0,
        'total_requested': round(sum(a.loan_amount_requested for a in all_apps), 1),
        'total_approved_amt': round(sum(a.loan_amount_requested for a in all_apps if a.status == 'approved'), 1),
    }

    return render_template('lender_dashboard.html',
                           applications=filtered,
                           analytics=analytics,
                           risk_filter=risk_filter,
                           status_filter=status_filter,
                           search=search,
                           all_count=len(all_apps))


@lender_bp.route('/application/<int:app_id>')
@login_required
@lender_required
def view_application(app_id):
    application = LoanApplication.query.get_or_404(app_id)
    applicant   = User.query.get(application.user_id)

    explanation = {}
    if application.explanation_json:
        try:
            explanation = json.loads(application.explanation_json)
        except Exception:
            pass

    from scorer import get_band
    band = get_band(application.ai_credit_score) if application.ai_credit_score else {}

    # Optimizer data
    optimizer_result = None
    if application.ai_credit_score:
        from optimizer import optimize
        optimizer_result = optimize(application, application.ai_credit_score)

    return render_template('lender_application.html',
                           application=application,
                           applicant=applicant,
                           explanation=explanation,
                           band=band,
                           optimizer_result=optimizer_result)


@lender_bp.route('/action/<int:app_id>', methods=['POST'])
@login_required
@lender_required
def take_action(app_id):
    application = LoanApplication.query.get_or_404(app_id)
    action      = request.form.get('action')   # 'approved' | 'rejected' | 'pending'

    if action in ('approved', 'rejected', 'pending'):
        application.status      = action
        application.reviewed_at = datetime.utcnow()
        db.session.commit()

    return redirect(url_for('lender.view_application', app_id=app_id))