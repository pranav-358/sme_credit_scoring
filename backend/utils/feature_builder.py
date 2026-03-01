"""
feature_builder.py
------------------
Bridge between Flask (backend) and the ml/preprocessor.py module.
Converts a LoanApplication SQLAlchemy object → feature dict → numpy array.
"""

import os
import sys

# Ensure ml/ is on the path when called from backend
ML_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'ml'))
if ML_DIR not in sys.path:
    sys.path.insert(0, ML_DIR)

from preprocessor import build_features, features_to_array, get_feature_names  # noqa


def application_to_features(app_obj):
    """
    Takes a LoanApplication model instance and returns:
      - feature_dict : dict of all 32 features (raw + engineered)
      - feature_array: np.ndarray of shape (1, 32) ready for model.predict()
    """
    raw = {col.name: getattr(app_obj, col.name)
           for col in app_obj.__table__.columns}

    feat_dict  = build_features(raw)
    feat_array = features_to_array(feat_dict)
    return feat_dict, feat_array