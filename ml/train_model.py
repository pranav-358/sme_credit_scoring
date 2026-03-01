"""
train_model.py
--------------
Trains a Gradient Boosting credit scoring model.
Uses XGBoost if installed, falls back to sklearn GradientBoostingClassifier.

Run:  python ml/train_model.py
"""

import os, sys, pickle
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import (accuracy_score, roc_auc_score,
                              classification_report, confusion_matrix)

ML_DIR      = os.path.dirname(os.path.abspath(__file__))
DATA_PATH   = os.path.join(ML_DIR, 'data',         'sme_loan_dataset.csv')
MODEL_PATH  = os.path.join(ML_DIR, 'saved_models', 'credit_model.pkl')
SCALER_PATH = os.path.join(ML_DIR, 'saved_models', 'scaler.pkl')
META_PATH   = os.path.join(ML_DIR, 'saved_models', 'model_meta.pkl')

sys.path.insert(0, ML_DIR)
from preprocessor import preprocess_dataframe, FEATURE_NAMES

# ── Model selection ────────────────────────────────────────────────────────────
try:
    from xgboost import XGBClassifier
    def build_model(scale_pos_weight):
        return XGBClassifier(
            n_estimators      = 300,
            max_depth         = 5,
            learning_rate     = 0.08,
            subsample         = 0.80,
            colsample_bytree  = 0.80,
            min_child_weight  = 3,
            gamma             = 0.1,
            reg_alpha         = 0.05,
            reg_lambda        = 1.0,
            scale_pos_weight  = scale_pos_weight,
            use_label_encoder = False,
            eval_metric       = 'logloss',
            random_state      = 42,
            n_jobs            = -1,
        )
    MODEL_TYPE = 'XGBoost'
except ImportError:
    from sklearn.ensemble import GradientBoostingClassifier
    def build_model(scale_pos_weight):
        return GradientBoostingClassifier(
            n_estimators      = 300,
            max_depth         = 5,
            learning_rate     = 0.08,
            subsample         = 0.80,
            min_samples_split = 6,
            min_samples_leaf  = 3,
            max_features      = 'sqrt',
            random_state      = 42,
        )
    MODEL_TYPE = 'sklearn GradientBoosting'


def train():
    print("=" * 55)
    print("  SME Credit Scoring — Model Training")
    print(f"  Engine: {MODEL_TYPE}")
    print("=" * 55)

    # 1. Load
    print("\n[1/5] Loading dataset...")
    df = pd.read_csv(DATA_PATH)
    print(f"      Rows: {len(df)}  |  Features: {df.shape[1]-1}")

    # 2. Preprocess
    print("[2/5] Engineering features & scaling...")
    X, y, scaler = preprocess_dataframe(df)
    n_pos = y.sum();  n_neg = len(y) - n_pos
    print(f"      X shape: {X.shape}  |  Good:{n_pos}  Risky:{n_neg}")

    # 3. Split
    print("[3/5] Splitting data (80/20 stratified)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    # 4. Train
    print("[4/5] Training model (this may take ~30s)...")
    model = build_model(scale_pos_weight=n_neg / n_pos)

    if MODEL_TYPE == 'XGBoost':
        model.fit(X_train, y_train,
                  eval_set=[(X_test, y_test)], verbose=False)
    else:
        model.fit(X_train, y_train)

    # 5. Evaluate
    print("[5/5] Evaluating...\n")
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    acc  = accuracy_score(y_test, y_pred)
    roc  = roc_auc_score(y_test, y_prob)
    cv   = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cvs  = cross_val_score(model, X, y, cv=cv, scoring='roc_auc', n_jobs=-1)

    print(f"  Test Accuracy  : {acc*100:.2f}%")
    print(f"  Test ROC-AUC   : {roc:.4f}")
    print(f"  5-Fold CV AUC  : {cvs.mean():.4f} ± {cvs.std():.4f}")
    print()
    print("  Classification Report:")
    print(classification_report(y_test, y_pred,
                                target_names=['Risky','Creditworthy']))

    cm = confusion_matrix(y_test, y_pred)
    print(f"  Confusion Matrix:\n    TN={cm[0,0]}  FP={cm[0,1]}\n"
          f"    FN={cm[1,0]}  TP={cm[1,1]}")

    # Feature importances
    importances = dict(zip(FEATURE_NAMES, model.feature_importances_))
    top5 = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\n  Top 5 Feature Importances:")
    for feat, imp in top5:
        bar = "█" * int(imp * 200)
        print(f"    {feat:<28} {imp:.4f}  {bar}")

    # Save
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, 'wb') as fh:
        pickle.dump(model, fh)

    meta = {
        'model_type'    : MODEL_TYPE,
        'feature_names' : FEATURE_NAMES,
        'accuracy'      : round(acc, 4),
        'roc_auc'       : round(roc, 4),
        'cv_auc_mean'   : round(cvs.mean(), 4),
        'cv_auc_std'    : round(cvs.std(), 4),
        'n_train'       : len(X_train),
        'n_test'        : len(X_test),
        'top_features'  : top5,
    }
    with open(META_PATH, 'wb') as fh:
        pickle.dump(meta, fh)

    print(f"\n✓ Model saved → {MODEL_PATH}")
    print(f"✓ Meta  saved → {META_PATH}")
    print("\n  Training complete!")
    return model, scaler, meta


if __name__ == '__main__':
    train()