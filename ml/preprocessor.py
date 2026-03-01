"""
preprocessor.py
---------------
Handles all feature engineering and normalization for both:
  - Training pipeline (fit_transform on dataset)
  - Inference pipeline (transform on a single loan application dict)

Exports:
  build_features(raw_dict)  → engineered feature dict
  get_feature_names()       → ordered list of feature names used by model
  load_scaler()             → fitted StandardScaler (loaded from disk)
"""

import os
import numpy as np
import pandas as pd
import pickle

# ── Paths ──────────────────────────────────────────────────────────────────────
ML_DIR      = os.path.dirname(os.path.abspath(__file__))
SCALER_PATH = os.path.join(ML_DIR, 'saved_models', 'scaler.pkl')

# ── Feature name order (must match training) ───────────────────────────────────
FEATURE_NAMES = [
    # Raw numeric inputs
    'years_in_business',
    'num_employees',
    'annual_turnover',
    'loan_amount_requested',
    'avg_monthly_balance',
    'monthly_credits',
    'monthly_debits',
    'num_emi_bounces',
    'num_cheque_bounces',
    'existing_loan_emi',
    'gst_filing_regularity',
    'avg_gst_turnover',
    'gst_growth_rate',
    'social_presence_score',
    'online_reviews_rating',
    'export_presence',
    'industry_growth_factor',
    'collateral_available',
    'collateral_value',
    'existing_credit_score',
    'previous_loan_defaults',
    'years_of_banking_rel',
    # Engineered features
    'cashflow_ratio',
    'debt_to_turnover',
    'balance_utilisation',
    'loan_to_turnover',
    'gst_compliance',
    'bounce_score',
    'cibil_norm',
    'collateral_coverage',
    'maturity_score',
    'revenue_per_employee',
]


def build_features(raw: dict) -> dict:
    """
    Takes a raw dict of loan application fields (as stored in DB)
    and returns a complete feature dict including all engineered features.
    """
    r = raw  # shorthand

    # ── Safe getters ──────────────────────────────────────────────────────────
    def f(key, default=0.0):
        val = r.get(key, default)
        return float(val) if val is not None else float(default)

    annual_turnover       = f('annual_turnover', 1)
    loan_amount_requested = f('loan_amount_requested', 1)
    monthly_credits       = f('monthly_credits', 1)
    monthly_debits        = f('monthly_debits', 0)
    existing_loan_emi     = f('existing_loan_emi', 0)
    avg_monthly_balance   = f('avg_monthly_balance', 0)
    num_employees         = max(f('num_employees', 1), 1)
    years_in_business     = f('years_in_business', 0)
    num_emi_bounces       = f('num_emi_bounces', 0)
    num_cheque_bounces    = f('num_cheque_bounces', 0)
    gst_filing_regularity = f('gst_filing_regularity', 50)
    collateral_available  = float(bool(r.get('collateral_available', False)))
    collateral_value      = f('collateral_value', 0)
    existing_credit_score = f('existing_credit_score', 0)
    previous_loan_defaults = f('previous_loan_defaults', 0)

    # ── Engineered features ───────────────────────────────────────────────────
    cashflow_ratio       = monthly_credits / (monthly_debits + existing_loan_emi + 0.001)
    debt_to_turnover     = (existing_loan_emi * 12) / (annual_turnover + 0.001)
    balance_utilisation  = avg_monthly_balance / (monthly_credits + 0.001)
    loan_to_turnover     = loan_amount_requested / (annual_turnover + 0.001)
    gst_compliance       = gst_filing_regularity / 100.0
    bounce_score         = 1.0 / (1 + num_emi_bounces + num_cheque_bounces)
    cibil_norm           = (existing_credit_score - 300) / 600.0 if existing_credit_score > 0 else 0.5
    collateral_coverage  = (collateral_value / (loan_amount_requested + 0.001)
                            if collateral_available else 0.0)
    maturity_score       = np.log1p(years_in_business) / np.log1p(40)
    revenue_per_employee = annual_turnover / num_employees

    features = {
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
        'avg_gst_turnover':       f('avg_gst_turnover', 0),
        'gst_growth_rate':        f('gst_growth_rate', 0),
        'social_presence_score':  f('social_presence_score', 5),
        'online_reviews_rating':  f('online_reviews_rating', 3.5),
        'export_presence':        float(bool(r.get('export_presence', False))),
        'industry_growth_factor': f('industry_growth_factor', 5),
        'collateral_available':   collateral_available,
        'collateral_value':       collateral_value,
        'existing_credit_score':  existing_credit_score,
        'previous_loan_defaults': previous_loan_defaults,
        'years_of_banking_rel':   f('years_of_banking_rel', 1),
        # Engineered
        'cashflow_ratio':         float(np.clip(cashflow_ratio, 0, 10)),
        'debt_to_turnover':       float(np.clip(debt_to_turnover, 0, 5)),
        'balance_utilisation':    float(np.clip(balance_utilisation, 0, 3)),
        'loan_to_turnover':       float(np.clip(loan_to_turnover, 0, 5)),
        'gst_compliance':         float(np.clip(gst_compliance, 0, 1)),
        'bounce_score':           float(np.clip(bounce_score, 0, 1)),
        'cibil_norm':             float(np.clip(cibil_norm, 0, 1)),
        'collateral_coverage':    float(np.clip(collateral_coverage, 0, 5)),
        'maturity_score':         float(np.clip(maturity_score, 0, 1)),
        'revenue_per_employee':   float(revenue_per_employee),
    }
    return features


def features_to_array(feature_dict: dict) -> np.ndarray:
    """Returns a 1×N numpy array in the correct column order for the model."""
    return np.array([[feature_dict[k] for k in FEATURE_NAMES]], dtype=np.float64)


def get_feature_names() -> list:
    return FEATURE_NAMES.copy()


def load_scaler():
    """Load the fitted StandardScaler from disk."""
    if not os.path.exists(SCALER_PATH):
        raise FileNotFoundError(
            f"Scaler not found at {SCALER_PATH}. "
            "Run 'python ml/train_model.py' first."
        )
    with open(SCALER_PATH, 'rb') as fh:
        return pickle.load(fh)


def preprocess_dataframe(df: pd.DataFrame):
    """
    Full pipeline for training:
      1. Engineer features for each row in df
      2. Fit StandardScaler on feature matrix
      3. Return (X_scaled, y, scaler)
    """
    from sklearn.preprocessing import StandardScaler

    rows = []
    for _, row in df.iterrows():
        feat = build_features(row.to_dict())
        rows.append([feat[k] for k in FEATURE_NAMES])

    X = np.array(rows, dtype=np.float64)
    y = df['creditworthy'].values.astype(int)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Save scaler
    os.makedirs(os.path.dirname(SCALER_PATH), exist_ok=True)
    with open(SCALER_PATH, 'wb') as fh:
        pickle.dump(scaler, fh)
    print(f"✓ Scaler saved → {SCALER_PATH}")

    return X_scaled, y, scaler