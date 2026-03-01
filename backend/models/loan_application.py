from extensions import db
from datetime import datetime


class LoanApplication(db.Model):
    __tablename__ = 'loan_applications'

    id                      = db.Column(db.Integer, primary_key=True)
    user_id                 = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Business Details
    business_name           = db.Column(db.String(200), nullable=False)
    business_type           = db.Column(db.String(100), nullable=False)
    industry                = db.Column(db.String(100), nullable=False)
    years_in_business       = db.Column(db.Float, nullable=False)
    num_employees           = db.Column(db.Integer, nullable=False)
    annual_turnover         = db.Column(db.Float, nullable=False)
    loan_amount_requested   = db.Column(db.Float, nullable=False)
    loan_purpose            = db.Column(db.String(200), nullable=False)

    # Bank Statement Metrics
    avg_monthly_balance     = db.Column(db.Float, nullable=False)
    monthly_credits         = db.Column(db.Float, nullable=False)
    monthly_debits          = db.Column(db.Float, nullable=False)
    num_emi_bounces         = db.Column(db.Integer, default=0)
    num_cheque_bounces      = db.Column(db.Integer, default=0)
    existing_loan_emi       = db.Column(db.Float, default=0.0)

    # GST Patterns
    gst_filing_regularity   = db.Column(db.Float, nullable=False)
    avg_gst_turnover        = db.Column(db.Float, nullable=False)
    gst_growth_rate         = db.Column(db.Float, nullable=False)

    # Social / Alternate
    social_presence_score   = db.Column(db.Float, default=5.0)
    online_reviews_rating   = db.Column(db.Float, default=3.5)
    export_presence         = db.Column(db.Boolean, default=False)

    # Industry & Market
    industry_growth_factor  = db.Column(db.Float, nullable=False)
    collateral_available    = db.Column(db.Boolean, default=False)
    collateral_value        = db.Column(db.Float, default=0.0)

    # Credit History
    existing_credit_score   = db.Column(db.Integer, default=0)
    previous_loan_defaults  = db.Column(db.Integer, default=0)
    years_of_banking_rel    = db.Column(db.Float, default=1.0)

    # ML Results
    status                  = db.Column(db.String(30), default='pending')
    ai_credit_score         = db.Column(db.Integer, nullable=True)
    risk_category           = db.Column(db.String(20), nullable=True)
    explanation_json        = db.Column(db.Text, nullable=True)   # stores JSON explanation
    submitted_at            = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at             = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref='applications')

    def __repr__(self):
        return f'<LoanApplication {self.id} – {self.business_name}>'