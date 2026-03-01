"""
optimizer.py
------------
Loan Amount Optimizer — suggests optimal loan size, tenure, EMI,
and cash flow safety ratio based on the applicant's financial profile.

Public API:
    optimize(application_obj, credit_score) -> dict
"""

import math


# ── Interest rate by risk category ────────────────────────────────────────────
RATE_TABLE = {
    'Low'    : 10.5,   # % per annum
    'Medium' : 13.5,
    'High'   : 17.0,
}

# ── Tenure options (months) by risk ───────────────────────────────────────────
TENURE_OPTIONS = {
    'Low'    : [12, 24, 36, 48, 60],
    'Medium' : [12, 24, 36, 48],
    'High'   : [12, 24, 36],
}

# ── Max loan-to-turnover ratio allowed by risk ────────────────────────────────
MAX_LTR = {
    'Low'    : 0.50,   # 50% of annual turnover
    'Medium' : 0.35,
    'High'   : 0.20,
}

# ── Cash flow safety thresholds ───────────────────────────────────────────────
SAFETY_THRESHOLD = {
    'Low'    : 1.25,   # after new EMI, cashflow ratio must stay >= this
    'Medium' : 1.40,
    'High'   : 1.60,
}


def _emi(principal: float, annual_rate: float, months: int) -> float:
    """Standard reducing-balance EMI formula. Returns monthly EMI in same units as principal."""
    if annual_rate == 0:
        return principal / months
    r = annual_rate / 100 / 12
    return principal * r * math.pow(1 + r, months) / (math.pow(1 + r, months) - 1)


def _max_affordable_loan(monthly_free_cash: float, annual_rate: float,
                          months: int, safety_buffer: float) -> float:
    """
    Back-calculate maximum principal given a monthly free cash amount,
    keeping a safety buffer so not 100% of free cash goes to EMI.
    """
    usable = monthly_free_cash / safety_buffer
    if usable <= 0:
        return 0.0
    r = annual_rate / 100 / 12
    if r == 0:
        return usable * months
    return usable * (math.pow(1 + r, months) - 1) / (r * math.pow(1 + r, months))


def _cashflow_safety_ratio(monthly_credits: float, monthly_debits: float,
                            existing_emi: float, new_emi: float) -> float:
    """
    CSR = monthly_credits / (monthly_debits + existing_emi + new_emi)
    > 1.25 = safe, 1.0–1.25 = caution, < 1.0 = dangerous
    """
    denom = monthly_debits + existing_emi + new_emi
    return monthly_credits / denom if denom > 0 else 0.0


def optimize(app, credit_score: int) -> dict:
    """
    Main optimizer.

    Args:
        app          : LoanApplication SQLAlchemy object
        credit_score : int 300–900

    Returns:
        dict with full optimization payload
    """
    risk        = app.risk_category or 'High'
    annual_rate = RATE_TABLE.get(risk, 17.0)
    tenures     = TENURE_OPTIONS.get(risk, [12, 24, 36])

    requested   = float(app.loan_amount_requested)      # lakhs
    turnover    = float(app.annual_turnover)
    credits     = float(app.monthly_credits)
    debits      = float(app.monthly_debits)
    existing_emi = float(app.existing_loan_emi or 0)
    collateral  = float(app.collateral_value or 0)

    # ── 1. Maximum allowed by policy (LTR cap) ──────────────────────────────
    max_by_ltr = turnover * MAX_LTR.get(risk, 0.20)

    # ── 2. Maximum by cash-flow capacity ────────────────────────────────────
    free_cash         = credits - debits - existing_emi
    safety_buf        = SAFETY_THRESHOLD.get(risk, 1.40)
    recommended_tenure = tenures[len(tenures) // 2]      # middle tenure as default

    max_by_cashflow = _max_affordable_loan(
        free_cash, annual_rate, recommended_tenure, safety_buf
    )

    # ── 3. Credit-score multiplier (300–900 → 0.5–1.0) ────────────────────
    score_mult = 0.5 + ((credit_score - 300) / 600) * 0.5
    max_by_cashflow *= score_mult

    # ── 4. Collateral boost (up to +20%) ────────────────────────────────────
    if collateral > 0:
        collateral_ratio  = min(collateral / (requested + 0.001), 2.0)
        collateral_boost  = 1.0 + (collateral_ratio * 0.10)
        max_by_cashflow  *= collateral_boost

    # ── 5. Final recommended amount ─────────────────────────────────────────
    recommended_amount = min(requested, max_by_ltr, max(max_by_cashflow, 0))
    recommended_amount = max(round(recommended_amount, 1), 0.0)

    # ── 6. Build tenure comparison table ────────────────────────────────────
    tenure_table = []
    for t in tenures:
        emi_val  = _emi(recommended_amount, annual_rate, t) if recommended_amount > 0 else 0
        csr      = _cashflow_safety_ratio(credits, debits, existing_emi, emi_val)
        total    = emi_val * t
        interest = total - recommended_amount

        tenure_table.append({
            'months'        : t,
            'emi'           : round(emi_val, 4),
            'total_payment' : round(total, 2),
            'total_interest': round(interest, 2),
            'cashflow_safety_ratio': round(csr, 3),
            'safe'          : csr >= 1.0,
            'recommended'   : t == recommended_tenure,
        })

    # Pick best tenure = longest tenure that keeps CSR safe
    safe_tenures = [t for t in tenure_table if t['safe']]
    best_tenure  = safe_tenures[-1] if safe_tenures else tenure_table[0]

    # ── 7. Recalculate with best tenure ─────────────────────────────────────
    best_emi = best_tenure['emi']
    final_csr = _cashflow_safety_ratio(credits, debits, existing_emi, best_emi)

    # ── 8. Gap analysis ─────────────────────────────────────────────────────
    gap         = requested - recommended_amount
    gap_reasons = []

    if recommended_amount < requested:
        if max_by_cashflow < requested:
            gap_reasons.append('Monthly cash flow is insufficient to service the full loan amount')
        if max_by_ltr < requested:
            gap_reasons.append(f'Loan exceeds the {int(MAX_LTR[risk]*100)}% annual-turnover cap for {risk} risk profile')
        if collateral == 0 and risk != 'Low':
            gap_reasons.append('Adding collateral would increase the eligible amount')

    # ── 9. Improvement tips ─────────────────────────────────────────────────
    tips = []
    if final_csr < 1.25:
        tips.append('Reduce monthly debits or existing EMI obligations to improve cash flow')
    if app.gst_filing_regularity < 80:
        tips.append('Improve GST filing regularity to above 80% to qualify for better rates')
    if app.num_emi_bounces > 0 or app.num_cheque_bounces > 0:
        tips.append('Eliminate payment bounces — they directly lower your credit score')
    if collateral == 0:
        tips.append('Offering collateral can increase your eligible loan amount by up to 20%')
    if not tips:
        tips.append('Your financial profile is strong — maintain current performance')

    return {
        'recommended_amount'   : recommended_amount,
        'requested_amount'     : requested,
        'gap'                  : round(gap, 2),
        'gap_reasons'          : gap_reasons,
        'annual_rate'          : annual_rate,
        'risk_category'        : risk,
        'recommended_tenure'   : best_tenure['months'],
        'recommended_emi'      : best_tenure['emi'],
        'total_payment'        : best_tenure['total_payment'],
        'total_interest'       : best_tenure['total_interest'],
        'cashflow_safety_ratio': round(final_csr, 3),
        'safety_status'        : (
            'Safe' if final_csr >= 1.25 else
            'Caution' if final_csr >= 1.0 else
            'Risky'
        ),
        'tenure_table'         : tenure_table,
        'improvement_tips'     : tips,
        'max_by_ltr'           : round(max_by_ltr, 2),
        'max_by_cashflow'      : round(max(max_by_cashflow, 0), 2),
    }