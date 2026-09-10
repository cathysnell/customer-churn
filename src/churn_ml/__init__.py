"""Stage 4 churn-model logic — the tested source of truth shared with the notebooks.

The Databricks notebooks under ``ml/`` are self-contained deployment artifacts (they
run on serverless without importing the repo), but the *logic* they embed — the
feature set, the leakage guards, the risk-band thresholds, and the estimator
hyperparameters — lives here so it can be unit-tested and trained against the
synthetic generator. ``tests/test_churn_model.py`` both exercises this module and
guards the notebooks against drifting from it.
"""

from churn_ml.model import (
    BOOL_FEATURES,
    FEATURES,
    HGB_PARAMS,
    HIGH_THRESHOLD,
    LABEL,
    LEAKAGE_COLUMNS,
    MEDIUM_THRESHOLD,
    NUMERIC_FEATURES,
    build_pipeline,
    risk_band,
    sample_weight,
    temporal_split,
)

__all__ = [
    "BOOL_FEATURES",
    "FEATURES",
    "HGB_PARAMS",
    "HIGH_THRESHOLD",
    "LABEL",
    "LEAKAGE_COLUMNS",
    "MEDIUM_THRESHOLD",
    "NUMERIC_FEATURES",
    "build_pipeline",
    "risk_band",
    "sample_weight",
    "temporal_split",
]
