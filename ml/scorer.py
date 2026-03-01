"""
scorer.py — Inference engine
Maps model probability → credit score (300–900) → risk category
"""

import os, sys, pickle
import numpy as np

ML_DIR      = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH  = os.path.join(ML_DIR, 'saved_models', 'credit_model.pkl')
SCALER_PATH = os.path.join(ML_DIR, 'saved_models', 'scaler.pkl')

sys.path.insert(0, ML_DIR)

# ── Score bands ────────────────────────────────────────────────────────────────
SCORE_BANDS = [
    (800, 900, 'Excellent', 'Low',    '#10b981'),
    (720, 799, 'Very Good', 'Low',    '#34d399'),
    (650, 719, 'Good',      'Medium', '#f59e0b'),
    (580, 649, 'Fair',      'Medium', '#f97316'),
    (300, 579, 'Poor',      'High',   '#ef4444'),
]


# ── Module-level cache — load once, reuse forever ─────────────────────────────
_MODEL_CACHE  = {}

def _load(path):
    if path in _MODEL_CACHE:
        return _MODEL_CACHE[path]
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"File not found: {path}\n"
            "Run: python ml/train_model.py"
        )
    with open(path, 'rb') as fh:
        obj = pickle.load(fh)
    _MODEL_CACHE[path] = obj
    return obj


def probability_to_score(prob: float) -> int:
    """Non-linear mapping: probability (0–1) → CIBIL-style score (300–900)."""
    prob = float(np.clip(prob, 0.0, 1.0))
    breakpoints = [
        (0.00, 300), (0.20, 450), (0.35, 550),
        (0.50, 640), (0.65, 700), (0.78, 760),
        (0.88, 820), (0.95, 860), (1.00, 900),
    ]
    for i in range(len(breakpoints) - 1):
        p0, s0 = breakpoints[i]
        p1, s1 = breakpoints[i + 1]
        if p0 <= prob <= p1:
            t = (prob - p0) / (p1 - p0)
            return int(s0 + t * (s1 - s0))
    return 300


def get_band(score: int) -> dict:
    for lo, hi, label, risk, color in SCORE_BANDS:
        if lo <= score <= hi:
            return {'label': label, 'risk': risk,
                    'color': color, 'range': f'{lo}–{hi}'}
    return {'label': 'Poor', 'risk': 'High',
            'color': '#ef4444', 'range': '300–579'}


def score_application(feature_array: np.ndarray) -> dict:
    """
    Args:   feature_array — np.ndarray shape (1, 32), NOT yet scaled
    Returns dict with credit_score, risk_category, probability, band info
    """
    model  = _load(MODEL_PATH)
    scaler = _load(SCALER_PATH)

    X_scaled = scaler.transform(feature_array)
    prob     = float(model.predict_proba(X_scaled)[0, 1])
    score    = probability_to_score(prob)
    band     = get_band(score)

    return {
        'credit_score'  : score,
        'risk_category' : band['risk'],
        'probability'   : round(prob, 4),
        'band_label'    : band['label'],
        'band_color'    : band['color'],
        'band_range'    : band['range'],
        'approved'      : score >= 620,
    }