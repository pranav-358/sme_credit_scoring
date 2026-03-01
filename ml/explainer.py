"""
explainer.py
------------
Generates SHAP-style feature explanations for a credit score.

Strategy:
  - If `shap` is installed  → uses real TreeExplainer SHAP values
  - If not installed        → uses permutation-based importance (same concept,
                              slightly less precise but fully RBI-compliant)

Public API:
  explain(feature_dict, feature_array) -> dict with:
    - contributions   : list of {feature, display_name, value, impact, direction}
    - top_positive    : top 3 factors helping the score
    - top_negative    : top 3 factors hurting the score
    - summary_text    : human-readable paragraph
    - rbi_explanation : RBI-compliant formal explanation block
"""

import os, sys, pickle
import numpy as np

ML_DIR      = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH  = os.path.join(ML_DIR, 'saved_models', 'credit_model.pkl')
SCALER_PATH = os.path.join(ML_DIR, 'saved_models', 'scaler.pkl')

sys.path.insert(0, ML_DIR)
from preprocessor import FEATURE_NAMES

# ── Human-readable display names for each feature ─────────────────────────────
DISPLAY_NAMES = {
    'years_in_business'     : 'Years in Business',
    'num_employees'         : 'Number of Employees',
    'annual_turnover'       : 'Annual Turnover',
    'loan_amount_requested' : 'Loan Amount Requested',
    'avg_monthly_balance'   : 'Avg Monthly Bank Balance',
    'monthly_credits'       : 'Monthly Credit Inflow',
    'monthly_debits'        : 'Monthly Debit Outflow',
    'num_emi_bounces'       : 'EMI Bounce Count',
    'num_cheque_bounces'    : 'Cheque Bounce Count',
    'existing_loan_emi'     : 'Existing EMI Obligations',
    'gst_filing_regularity' : 'GST Filing Regularity',
    'avg_gst_turnover'      : 'Avg GST-Declared Turnover',
    'gst_growth_rate'       : 'GST Turnover Growth Rate',
    'social_presence_score' : 'Digital / Social Presence',
    'online_reviews_rating' : 'Online Reviews Rating',
    'export_presence'       : 'Export / International Presence',
    'industry_growth_factor': 'Industry Growth Factor',
    'collateral_available'  : 'Collateral Availability',
    'collateral_value'      : 'Collateral Value',
    'existing_credit_score' : 'Existing CIBIL Score',
    'previous_loan_defaults': 'Previous Loan Defaults',
    'years_of_banking_rel'  : 'Banking Relationship Duration',
    'cashflow_ratio'        : 'Cash Flow Ratio',
    'debt_to_turnover'      : 'Debt-to-Turnover Ratio',
    'balance_utilisation'   : 'Balance Utilisation',
    'loan_to_turnover'      : 'Loan-to-Turnover Ratio',
    'gst_compliance'        : 'GST Compliance Score',
    'bounce_score'          : 'Payment Bounce Score',
    'cibil_norm'            : 'Normalised Credit History',
    'collateral_coverage'   : 'Collateral Coverage Ratio',
    'maturity_score'        : 'Business Maturity Score',
    'revenue_per_employee'  : 'Revenue per Employee',
}


def _load(path):
    with open(path, 'rb') as f:
        return pickle.load(f)


def _permutation_contributions(model, scaler, feature_array: np.ndarray,
                                feature_dict: dict) -> list:
    """
    Compute feature contributions via baseline comparison.
    For each feature: measure score change when feature is set to its
    median (neutral) value. The delta = that feature's contribution.
    """
    X_scaled   = scaler.transform(feature_array)
    base_prob  = float(model.predict_proba(X_scaled)[0, 1])

    contributions = []
    for i, feat_name in enumerate(FEATURE_NAMES):
        X_perturbed              = X_scaled.copy()
        X_perturbed[0, i]        = 0.0          # 0 = mean in StandardScaler space
        perturbed_prob           = float(model.predict_proba(X_perturbed)[0, 1])
        impact                   = base_prob - perturbed_prob  # positive = feature helps

        raw_val = feature_dict.get(feat_name, 0)

        contributions.append({
            'feature'      : feat_name,
            'display_name' : DISPLAY_NAMES.get(feat_name, feat_name),
            'raw_value'    : raw_val,
            'impact'       : round(float(impact), 5),
            'direction'    : 'positive' if impact >= 0 else 'negative',
            'abs_impact'   : abs(impact),
        })

    # Sort by absolute impact descending
    contributions.sort(key=lambda x: x['abs_impact'], reverse=True)
    return contributions


def _shap_contributions(model, scaler, feature_array: np.ndarray,
                         feature_dict: dict) -> list:
    """Real SHAP TreeExplainer — used when shap package is available."""
    import shap
    X_scaled   = scaler.transform(feature_array)
    explainer  = shap.TreeExplainer(model)
    shap_vals  = explainer.shap_values(X_scaled)

    # For binary classifiers shap_values returns [neg_class, pos_class]
    if isinstance(shap_vals, list):
        vals = shap_vals[1][0]
    else:
        vals = shap_vals[0]

    contributions = []
    for i, feat_name in enumerate(FEATURE_NAMES):
        impact    = float(vals[i])
        raw_val   = feature_dict.get(feat_name, 0)
        contributions.append({
            'feature'      : feat_name,
            'display_name' : DISPLAY_NAMES.get(feat_name, feat_name),
            'raw_value'    : raw_val,
            'impact'       : round(impact, 5),
            'direction'    : 'positive' if impact >= 0 else 'negative',
            'abs_impact'   : abs(impact),
        })

    contributions.sort(key=lambda x: x['abs_impact'], reverse=True)
    return contributions


def _format_value(feat_name: str, raw_val) -> str:
    """Format a raw feature value into a human-readable string."""
    pct_fields  = {'gst_filing_regularity', 'gst_compliance', 'gst_growth_rate'}
    money_fields = {'annual_turnover', 'loan_amount_requested', 'avg_monthly_balance',
                    'monthly_credits', 'monthly_debits', 'existing_loan_emi',
                    'avg_gst_turnover', 'collateral_value'}
    bool_fields = {'collateral_available', 'export_presence'}
    score_fields = {'social_presence_score', 'industry_growth_factor',
                    'online_reviews_rating'}

    try:
        val = float(raw_val)
    except (TypeError, ValueError):
        return str(raw_val)

    if feat_name in bool_fields:
        return 'Yes' if val else 'No'
    if feat_name in pct_fields:
        return f'{val:.1f}%'
    if feat_name in money_fields:
        return f'Rs.{val:.1f}L'
    if feat_name == 'existing_credit_score':
        return str(int(val)) if val > 0 else 'Not provided'
    if feat_name in score_fields:
        return f'{val:.1f}/10' if feat_name != 'online_reviews_rating' else f'{val:.1f}/5'
    if feat_name in {'num_emi_bounces', 'num_cheque_bounces', 'previous_loan_defaults',
                     'num_employees'}:
        return str(int(val))
    if feat_name in {'cashflow_ratio', 'debt_to_turnover', 'balance_utilisation',
                     'loan_to_turnover', 'collateral_coverage'}:
        return f'{val:.2f}x'
    return f'{val:.2f}'


def _build_summary(top_pos: list, top_neg: list, score: int) -> str:
    pos_names = [c['display_name'] for c in top_pos[:2]]
    neg_names = [c['display_name'] for c in top_neg[:2]]

    if score >= 750:
        opener = "Your application demonstrates a strong financial profile."
    elif score >= 620:
        opener = "Your application shows a satisfactory credit profile."
    else:
        opener = "Your application has several areas that need improvement."

    parts = [opener]

    if pos_names:
        parts.append(
            f"Key strengths include {' and '.join(pos_names)}, "
            "which positively contributed to your score."
        )
    if neg_names:
        parts.append(
            f"Areas that reduced your score include {' and '.join(neg_names)}. "
            "Addressing these can significantly improve your creditworthiness."
        )

    return ' '.join(parts)


def _build_rbi_explanation(contributions: list, score: int,
                            risk_category: str) -> str:
    top3 = contributions[:3]
    factor_lines = []
    for i, c in enumerate(top3, 1):
        direction = 'positively' if c['direction'] == 'positive' else 'adversely'
        factor_lines.append(
            f"  {i}. {c['display_name']} ({_format_value(c['feature'], c['raw_value'])}) "
            f"— {direction} affected the credit assessment."
        )

    factors_text = '\n'.join(factor_lines)

    return (
        f"CREDIT ASSESSMENT DISCLOSURE (RBI Fair Lending Guidelines)\n"
        f"{'─' * 55}\n"
        f"Credit Score Assigned : {score} / 900\n"
        f"Risk Classification   : {risk_category} Risk\n"
        f"Scoring Model         : Gradient Boosting Classifier\n"
        f"Assessment Date       : Auto-generated\n\n"
        f"Principal Factors Influencing This Decision:\n"
        f"{factors_text}\n\n"
        f"This assessment was generated by an AI model trained on SME "
        f"financial data. The score reflects the applicant's repayment "
        f"likelihood based on cash flow, GST compliance, credit history, "
        f"and business profile. The applicant has the right to request a "
        f"manual review of this decision."
    )


def explain(feature_dict: dict, feature_array: np.ndarray,
            score: int, risk_category: str) -> dict:
    """
    Main explainability function.

    Args:
        feature_dict  : raw + engineered feature values
        feature_array : np.ndarray (1, 32) — unscaled
        score         : int credit score 300–900
        risk_category : 'Low' | 'Medium' | 'High'

    Returns:
        dict with full explanation payload
    """
    model  = _load(MODEL_PATH)
    scaler = _load(SCALER_PATH)

    # Choose SHAP or permutation
    try:
        import shap  # noqa
        contributions = _shap_contributions(model, scaler, feature_array, feature_dict)
        method = 'SHAP TreeExplainer'
    except ImportError:
        contributions = _permutation_contributions(model, scaler, feature_array, feature_dict)
        method = 'Permutation Importance'

    # Attach formatted values
    for c in contributions:
        c['formatted_value'] = _format_value(c['feature'], c['raw_value'])

    top_positive = [c for c in contributions if c['direction'] == 'positive'][:5]
    top_negative = [c for c in contributions if c['direction'] == 'negative'][:5]

    return {
        'method'          : method,
        'contributions'   : contributions[:12],   # top 12 for display
        'top_positive'    : top_positive,
        'top_negative'    : top_negative,
        'summary_text'    : _build_summary(top_positive, top_negative, score),
        'rbi_explanation' : _build_rbi_explanation(contributions, score, risk_category),
    }