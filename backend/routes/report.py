"""
report.py — PDF download route
"""
import os, sys, json
from flask import Blueprint, make_response, redirect, url_for
from flask_login import login_required, current_user
from models.loan_application import LoanApplication

report_bp = Blueprint('report', __name__, url_prefix='/report')

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR      = os.path.normpath(os.path.join(BACKEND_DIR, '..', '..', 'ml'))
UTILS_DIR   = os.path.normpath(os.path.join(BACKEND_DIR, '..', 'utils'))
for p in [ML_DIR, UTILS_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)


@report_bp.route('/pdf/<int:app_id>')
@login_required
def download_pdf(app_id):
    # Both applicant (own) and lender (any) can download
    if current_user.role == 'lender':
        application = LoanApplication.query.get_or_404(app_id)
    else:
        application = LoanApplication.query.filter_by(
            id=app_id, user_id=current_user.id
        ).first_or_404()

    if not application.ai_credit_score:
        return redirect(url_for('score.run_scoring', app_id=app_id))

    from scorer import get_band
    from pdf_generator import generate_pdf

    band        = get_band(application.ai_credit_score)
    explanation = {}
    if application.explanation_json:
        try:
            explanation = json.loads(application.explanation_json)
        except Exception:
            pass

    pdf_bytes = generate_pdf(application, band, explanation)

    filename  = f"CreditReport_{application.business_name.replace(' ','_')}_{app_id}.pdf"
    response  = make_response(pdf_bytes)
    response.headers['Content-Type']        = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response