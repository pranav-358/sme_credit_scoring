from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models.loan_application import LoanApplication

loan_bp = Blueprint('loan', __name__, url_prefix='/loan')


@loan_bp.route('/apply', methods=['GET', 'POST'])
@login_required
def apply():
    if current_user.role != 'applicant':
        return redirect(url_for('main.dashboard'))

    error = None
    if request.method == 'POST':
        try:
            f = request.form

            app_obj = LoanApplication(
                user_id               = current_user.id,

                # Business Details
                business_name         = f['business_name'].strip(),
                business_type         = f['business_type'],
                industry              = f['industry'],
                years_in_business     = float(f['years_in_business']),
                num_employees         = int(f['num_employees']),
                annual_turnover       = float(f['annual_turnover']),
                loan_amount_requested = float(f['loan_amount_requested']),
                loan_purpose          = f['loan_purpose'].strip(),

                # Bank Statement
                avg_monthly_balance   = float(f['avg_monthly_balance']),
                monthly_credits       = float(f['monthly_credits']),
                monthly_debits        = float(f['monthly_debits']),
                num_emi_bounces       = int(f.get('num_emi_bounces', 0)),
                num_cheque_bounces    = int(f.get('num_cheque_bounces', 0)),
                existing_loan_emi     = float(f.get('existing_loan_emi', 0)),

                # GST
                gst_filing_regularity = float(f['gst_filing_regularity']),
                avg_gst_turnover      = float(f['avg_gst_turnover']),
                gst_growth_rate       = float(f['gst_growth_rate']),

                # Social
                social_presence_score = float(f.get('social_presence_score', 5)),
                online_reviews_rating = float(f.get('online_reviews_rating', 3.5)),
                export_presence       = f.get('export_presence') == 'on',

                # Industry
                industry_growth_factor = float(f['industry_growth_factor']),
                collateral_available   = f.get('collateral_available') == 'on',
                collateral_value       = float(f.get('collateral_value', 0)),

                # Credit History
                existing_credit_score  = int(f.get('existing_credit_score', 0)),
                previous_loan_defaults = int(f.get('previous_loan_defaults', 0)),
                years_of_banking_rel   = float(f.get('years_of_banking_rel', 1)),
            )

            db.session.add(app_obj)
            db.session.commit()
            return redirect(url_for('loan.submitted', app_id=app_obj.id))

        except (ValueError, KeyError) as e:
            error = f'Please fill all required fields correctly. ({str(e)})'

    return render_template('loan_apply.html', error=error)


@loan_bp.route('/submitted/<int:app_id>')
@login_required
def submitted(app_id):
    application = LoanApplication.query.filter_by(
        id=app_id, user_id=current_user.id
    ).first_or_404()
    return render_template('loan_submitted.html', application=application)


@loan_bp.route('/my-applications')
@login_required
def my_applications():
    apps = LoanApplication.query.filter_by(user_id=current_user.id)\
                                .order_by(LoanApplication.submitted_at.desc()).all()
    return render_template('my_applications.html', applications=apps)