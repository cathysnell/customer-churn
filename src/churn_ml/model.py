"""Churn-model feature contract, estimator, and scoring helpers.

Pure Python + scikit-learn — no Databricks, Spark, or MLflow imports — so it is unit
testable and trainable on the generator's output. The ``ml/`` notebooks mirror these
values; keep the two in sync (the drift tests enforce it).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:  # pragma: no cover - typing only
    from sklearn.pipeline import Pipeline

# ---------------------------------------------------------------------------
# Feature contract
# ---------------------------------------------------------------------------

#: Numeric monthly engagement signals the model is allowed to see.
NUMERIC_FEATURES: list[str] = [
    "tenure_months",
    "active_days",
    "avg_coding_hours",
    "avg_acceptance_rate",
    "avg_session_frequency",
    "coding_hours_trend_30d",  # the headline decline feature
    "support_tickets_30d",
    "features_adopted",
    "crm_touches_30d",
]

#: Boolean feature(s), passed through as 0/1.
BOOL_FEATURES: list[str] = ["is_power_user_month"]

#: The full ordered feature list handed to the estimator.
FEATURES: list[str] = NUMERIC_FEATURES + BOOL_FEATURES

#: The supervised target.
LABEL: str = "churned"

#: Columns from churn_labels that must NEVER be used as features. ``churn_date`` is
#: NULL unless the user churned (direct target leakage); ``user_id``/``month_start``
#: are identifiers; ``geo`` is deliberately excluded to keep the demo model portable
#: across regions; ``churned`` is the label itself.
LEAKAGE_COLUMNS: frozenset[str] = frozenset(
    {"churn_date", "user_id", "month_start", "geo", "churned"}
)

# ---------------------------------------------------------------------------
# Risk bands (for the CRM re-engagement trigger)
# ---------------------------------------------------------------------------

HIGH_THRESHOLD: float = 0.60
MEDIUM_THRESHOLD: float = 0.30


def risk_band(p: float) -> str:
    """Map a churn probability to a coarse CRM action band.

    ``high`` (>= 0.60) -> personalized outreach, ``medium`` (>= 0.30) -> nurture,
    ``low`` -> leave alone. Thresholds are demo defaults; tune to team capacity.
    """
    if p >= HIGH_THRESHOLD:
        return "high"
    if p >= MEDIUM_THRESHOLD:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Estimator
# ---------------------------------------------------------------------------

#: HistGradientBoostingClassifier hyperparameters. No native deps, fast on ~570k rows,
#: and one Pipeline so scoring is a single predict_proba.
HGB_PARAMS: dict[str, object] = {
    "max_iter": 300,
    "learning_rate": 0.06,
    "max_leaf_nodes": 31,
    "l2_regularization": 1.0,
    "early_stopping": True,
    "validation_fraction": 0.1,
    "random_state": 1729,  # same seed lineage as the datagen
}


def build_pipeline(params: dict[str, object] | None = None) -> Pipeline:
    """Median-impute the numeric features, pass the bool through, then fit HistGBT."""
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline

    return Pipeline(
        steps=[
            (
                "prep",
                ColumnTransformer(
                    transformers=[
                        ("num", SimpleImputer(strategy="median"), NUMERIC_FEATURES)
                    ],
                    remainder="passthrough",  # bool feature passes through as-is
                ),
            ),
            ("gbt", HistGradientBoostingClassifier(**(params or HGB_PARAMS))),
        ]
    )


def sample_weight(y: pd.Series | np.ndarray) -> np.ndarray:
    """Up-weight the rare positive class inversely to its frequency."""
    y = np.asarray(y)
    pos_rate = float(y.mean())
    if pos_rate <= 0.0 or pos_rate >= 1.0:
        return np.ones(len(y))
    return np.where(y == 1, (1 - pos_rate) / pos_rate, 1.0)


# ---------------------------------------------------------------------------
# Temporal split
# ---------------------------------------------------------------------------


def temporal_split(
    pdf: pd.DataFrame, month_col: str = "month_start"
) -> tuple[pd.DataFrame, pd.DataFrame, object]:
    """Hold out the most recent month for validation (no future leakage).

    Returns ``(train_df, valid_df, holdout_month)``.
    """
    holdout_month = pdf[month_col].max()
    train_df = pdf[pdf[month_col] < holdout_month]
    valid_df = pdf[pdf[month_col] == holdout_month]
    return train_df, valid_df, holdout_month
