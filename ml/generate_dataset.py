"""
generate_dataset.py
-------------------
Generates a realistic synthetic dataset of 1500 SME loan applications
for training the Gradient Boosting credit model.

Run once:  python ml/generate_dataset.py
Output  :  ml/data/sme_loan_dataset.csv
"""

import numpy as np
import pandas as pd
import os

np.random.seed(42)
N = 1500

# ── Helper: clamp ─────────────────────────────────────────────────────────────
def clamp(arr, lo, hi):
    return np.clip(arr, lo, hi)

# ── Raw features ──────────────────────────────────────────────────────────────
years_in_business     = clamp(np.random.exponential(5, N), 0.5, 40)
num_employees         = clamp(np.random.exponential(30, N).astype(int), 1, 500)
annual_turnover       = clamp(np.random.lognormal(4.5, 1.0, N), 5, 5000)      # lakhs
loan_amount_requested = clamp(annual_turnover * np.random.uniform(0.05, 0.6, N), 1, 1000)

avg_monthly_balance   = clamp(annual_turnover / 12 * np.random.uniform(0.3, 1.2, N), 0.5, 300)
monthly_credits       = clamp(annual_turnover / 12 * np.random.uniform(0.7, 1.3, N), 1, 400)
monthly_debits        = clamp(monthly_credits * np.random.uniform(0.5, 0.98, N), 0.5, 390)
num_emi_bounces       = np.random.poisson(0.8, N).astype(int)
num_cheque_bounces    = np.random.poisson(0.6, N).astype(int)
existing_loan_emi     = clamp(np.random.exponential(1.5, N), 0, 20)

gst_filing_regularity = clamp(np.random.beta(7, 2, N) * 100, 0, 100)
avg_gst_turnover      = clamp(annual_turnover / 4 * np.random.uniform(0.7, 1.1, N), 1, 1500)
gst_growth_rate       = np.random.normal(8, 15, N)

social_presence_score  = clamp(np.random.beta(3, 2, N) * 9 + 1, 1, 10)
online_reviews_rating  = clamp(np.random.normal(3.8, 0.8, N), 1, 5)
export_presence        = (np.random.rand(N) < 0.15).astype(int)

industry_growth_factor = clamp(np.random.beta(4, 3, N) * 9 + 1, 1, 10)
collateral_available   = (np.random.rand(N) < 0.45).astype(int)
collateral_value       = np.where(collateral_available,
                            clamp(loan_amount_requested * np.random.uniform(0.5, 2.5, N), 0, 2000), 0)

existing_credit_score  = np.where(
    np.random.rand(N) < 0.6,
    clamp(np.random.normal(680, 80, N).astype(int), 300, 900),
    0)
previous_loan_defaults = np.random.poisson(0.3, N).astype(int)
years_of_banking_rel   = clamp(np.random.exponential(4, N), 0.5, 30)

# ── Derived / engineered features ─────────────────────────────────────────────
# 1. Cash-flow ratio
cashflow_ratio = monthly_credits / (monthly_debits + existing_loan_emi + 0.001)

# 2. Debt-to-turnover ratio
debt_to_turnover = (existing_loan_emi * 12) / (annual_turnover + 0.001)

# 3. Balance utilisation
balance_utilisation = avg_monthly_balance / (monthly_credits + 0.001)

# 4. Loan-to-turnover ratio
loan_to_turnover = loan_amount_requested / (annual_turnover + 0.001)

# 5. GST compliance score (0–1)
gst_compliance = gst_filing_regularity / 100

# 6. Bounce score (penalises bounces)
bounce_score = 1 / (1 + num_emi_bounces + num_cheque_bounces)

# 7. Credit history score (0–1)
cibil_norm = np.where(existing_credit_score > 0,
                      (existing_credit_score - 300) / 600, 0.5)

# 8. Collateral coverage ratio
collateral_coverage = np.where(collateral_available,
                               collateral_value / (loan_amount_requested + 0.001), 0)

# 9. Business maturity score
maturity_score = np.log1p(years_in_business) / np.log1p(40)

# 10. Revenue per employee (proxy for productivity)
revenue_per_employee = annual_turnover / (num_employees + 1)

# ── Target: creditworthy (1 = good borrower, 0 = risky) ──────────────────────
# Weighted linear score (ground truth signal)
raw_score = (
    0.20 * cashflow_ratio.clip(0, 3) / 3 +
    0.15 * gst_compliance +
    0.15 * cibil_norm +
    0.10 * bounce_score +
    0.10 * (1 - debt_to_turnover.clip(0, 1)) +
    0.08 * maturity_score +
    0.07 * (social_presence_score / 10) +
    0.07 * (industry_growth_factor / 10) +
    0.05 * collateral_coverage.clip(0, 2) / 2 +
    0.03 * (1 - (previous_loan_defaults.clip(0, 5) / 5))
)

# Add noise and threshold
noise = np.random.normal(0, 0.06, N)
final_score = clamp(raw_score + noise, 0, 1)
creditworthy = (final_score > 0.52).astype(int)

# ── Build DataFrame ────────────────────────────────────────────────────────────
df = pd.DataFrame({
    # Raw inputs
    'years_in_business':      years_in_business,
    'num_employees':          num_employees,
    'annual_turnover':        annual_turnover,
    'loan_amount_requested':  loan_amount_requested,
    'avg_monthly_balance':    avg_monthly_balance,
    'monthly_credits':        monthly_credits,
    'monthly_debits':         monthly_debits,
    'num_emi_bounces':        num_emi_bounces,
    'num_cheque_bounces':     num_cheque_bounces,
    'existing_loan_emi':      existing_loan_emi,
    'gst_filing_regularity':  gst_filing_regularity,
    'avg_gst_turnover':       avg_gst_turnover,
    'gst_growth_rate':        gst_growth_rate,
    'social_presence_score':  social_presence_score,
    'online_reviews_rating':  online_reviews_rating,
    'export_presence':        export_presence,
    'industry_growth_factor': industry_growth_factor,
    'collateral_available':   collateral_available,
    'collateral_value':       collateral_value,
    'existing_credit_score':  existing_credit_score,
    'previous_loan_defaults': previous_loan_defaults,
    'years_of_banking_rel':   years_of_banking_rel,
    # Engineered features
    'cashflow_ratio':         cashflow_ratio,
    'debt_to_turnover':       debt_to_turnover,
    'balance_utilisation':    balance_utilisation,
    'loan_to_turnover':       loan_to_turnover,
    'gst_compliance':         gst_compliance,
    'bounce_score':           bounce_score,
    'cibil_norm':             cibil_norm,
    'collateral_coverage':    collateral_coverage,
    'maturity_score':         maturity_score,
    'revenue_per_employee':   revenue_per_employee,
    # Target
    'creditworthy':           creditworthy,
})

# Round for readability
df = df.round(4)

out_path = os.path.join(os.path.dirname(__file__), 'data', 'sme_loan_dataset.csv')
df.to_csv(out_path, index=False)
print(f"✓ Dataset saved → {out_path}")
print(f"  Rows        : {len(df)}")
print(f"  Creditworthy: {creditworthy.sum()} ({creditworthy.mean()*100:.1f}%)")
print(f"  Risky       : {(1-creditworthy).sum()} ({(1-creditworthy).mean()*100:.1f}%)")
print(f"  Features    : {df.shape[1]-1}")