"""Stage 4 churn model — logic, learned signal, and notebook drift guards.

Two kinds of coverage:

* **Behaviour** — the estimator built from ``churn_ml`` actually learns churn from the
  generator's ``churn_labels`` frame (and would catch a leakage/feature regression).
* **Drift guards** — the self-contained ``ml/`` notebooks embed the same feature
  contract and risk-band thresholds as ``churn_ml`` (they run on serverless without
  importing the repo, so the values are duplicated by necessity; these tests fail if
  the copies diverge).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from churn_ml import model
from datagen import schemas
from datagen.pipeline import GenerationResult

REPO = Path(__file__).resolve().parents[1]
TRAIN_NB = REPO / "ml" / "train_churn_model.py"
SCORE_NB = REPO / "ml" / "score_churn.py"
JOB_JSON = REPO / "ml" / "churn_ml_job.json"
REVERSE_ETL = REPO / "serving" / "reverse_etl.py"


# ---------------------------------------------------------------------------
# Feature contract
# ---------------------------------------------------------------------------


def test_features_are_real_churn_labels_columns() -> None:
    """Every feature (and the label) must exist on the source table."""
    cols = {c.name for c in schemas.CHURN_LABELS.columns}
    assert set(model.FEATURES) <= cols
    assert model.LABEL in cols


def test_features_exclude_leakage_columns() -> None:
    """churn_date/user_id/month_start/geo/churned must never be features."""
    assert model.LEAKAGE_COLUMNS.isdisjoint(model.FEATURES)
    assert model.LABEL not in model.FEATURES


def test_leakage_columns_are_actual_columns() -> None:
    """The guard list names real columns (so it's guarding something)."""
    cols = {c.name for c in schemas.CHURN_LABELS.columns}
    assert cols >= model.LEAKAGE_COLUMNS


# ---------------------------------------------------------------------------
# Risk bands
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "p, expected",
    [
        (0.0, "low"),
        (0.2999, "low"),
        (0.30, "medium"),
        (0.5999, "medium"),
        (0.60, "high"),
        (1.0, "high"),
    ],
)
def test_risk_band_boundaries(p: float, expected: str) -> None:
    assert model.risk_band(p) == expected


# ---------------------------------------------------------------------------
# Sample weighting
# ---------------------------------------------------------------------------


def test_sample_weight_upweights_the_rare_positive() -> None:
    import numpy as np

    y = np.array([0] * 95 + [1] * 5)  # 5% positive
    w = model.sample_weight(y)
    assert w[y == 1].mean() > w[y == 0].mean()
    # inverse-frequency: positive weight ~= (1-p)/p = 0.95/0.05 = 19
    assert w[y == 1][0] == pytest.approx(19.0, rel=1e-6)


def test_sample_weight_degenerate_class_is_uniform() -> None:
    import numpy as np

    assert (model.sample_weight(np.zeros(10)) == 1.0).all()


# ---------------------------------------------------------------------------
# Temporal split
# ---------------------------------------------------------------------------


def test_temporal_split_holds_out_the_latest_month(result: GenerationResult) -> None:
    labels = result.frames["churn_labels"]
    train_df, valid_df, holdout = model.temporal_split(labels)
    assert holdout == labels["month_start"].max()
    assert (train_df["month_start"] < holdout).all()
    assert (valid_df["month_start"] == holdout).all()
    assert len(train_df) + len(valid_df) <= len(labels)  # earlier months + holdout
    assert len(valid_df) > 0 and len(train_df) > 0


# ---------------------------------------------------------------------------
# Behaviour: the model learns real churn signal
# ---------------------------------------------------------------------------


def _fit_and_score(labels):
    """Train on history, score the holdout month; return (proba, y_true)."""
    from sklearn.metrics import roc_auc_score

    pdf = labels.copy()
    pdf[model.LABEL] = pdf[model.LABEL].astype("int8")
    pdf["is_power_user_month"] = pdf["is_power_user_month"].astype("int8")
    train_df, valid_df, _ = model.temporal_split(pdf)

    pipe = model.build_pipeline()
    pipe.fit(
        train_df[model.FEATURES],
        train_df[model.LABEL],
        gbt__sample_weight=model.sample_weight(train_df[model.LABEL]),
    )
    proba = pipe.predict_proba(valid_df[model.FEATURES])[:, 1]
    return proba, valid_df[model.LABEL], roc_auc_score(valid_df[model.LABEL], proba)


def test_model_learns_churn_signal(result: GenerationResult) -> None:
    """Holdout ROC-AUC must be well above chance — else features/labels regressed."""
    pytest.importorskip("sklearn")
    _, _, auc = _fit_and_score(result.frames["churn_labels"])
    assert auc > 0.65, f"holdout ROC-AUC={auc:.3f} — model is not learning signal"


def test_churners_score_higher_than_retained(result: GenerationResult) -> None:
    pytest.importorskip("sklearn")
    proba, y, _ = _fit_and_score(result.frames["churn_labels"])
    assert proba[y == 1].mean() > proba[y == 0].mean()


# ---------------------------------------------------------------------------
# Notebook drift guards (ast-parsed, not regex)
# ---------------------------------------------------------------------------


def _module_assignments(path: Path, names: set[str]) -> dict[str, object]:
    """Return literal values of top-level ``NAME = <literal>`` assignments.

    Handles ``FEATURES = NUMERIC_FEATURES + BOOL_FEATURES`` by resolving the two
    operands from earlier assignments in the same file.
    """
    tree = ast.parse(path.read_text())
    out: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id not in names:
            continue
        try:
            out[target.id] = ast.literal_eval(node.value)
        except ValueError:
            if (
                isinstance(node.value, ast.BinOp)
                and isinstance(node.value.op, ast.Add)
                and isinstance(node.value.left, ast.Name)
                and isinstance(node.value.right, ast.Name)
            ):
                out[target.id] = out.get(node.value.left.id, []) + out.get(
                    node.value.right.id, []
                )
    return out


@pytest.mark.parametrize("nb", [TRAIN_NB, SCORE_NB])
def test_notebook_feature_lists_match_library(nb: Path) -> None:
    got = _module_assignments(nb, {"NUMERIC_FEATURES", "BOOL_FEATURES", "FEATURES"})
    assert got["NUMERIC_FEATURES"] == model.NUMERIC_FEATURES
    assert got["BOOL_FEATURES"] == model.BOOL_FEATURES
    assert got["FEATURES"] == model.FEATURES


def _band_constants(path: Path) -> set[float]:
    """Numeric constants used inside the notebook's ``_band`` function."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_band":
            return {
                n.value
                for n in ast.walk(node)
                if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            }
    return set()


def test_score_notebook_risk_thresholds_match_library() -> None:
    consts = _band_constants(SCORE_NB)
    assert model.HIGH_THRESHOLD in consts
    assert model.MEDIUM_THRESHOLD in consts


# ---------------------------------------------------------------------------
# Job wiring
# ---------------------------------------------------------------------------


def test_job_task_graph_is_train_score_sync() -> None:
    job = json.loads(JOB_JSON.read_text())
    tasks = {t["task_key"]: t for t in job["tasks"]}
    assert set(tasks) == {"train", "score", "sync_predictions"}
    assert tasks["score"]["depends_on"] == [{"task_key": "train"}]
    assert tasks["sync_predictions"]["depends_on"] == [{"task_key": "score"}]
    # The sync task must be paused-by-default and driven off churn_predictions.
    assert job["schedule"]["pause_status"] == "PAUSED"


def test_sync_task_params_match_reverse_etl_widgets() -> None:
    """The job's sync params must be exactly the widget names reverse_etl.py reads."""
    job = json.loads(JOB_JSON.read_text())
    sync = next(t for t in job["tasks"] if t["task_key"] == "sync_predictions")
    params = sync["notebook_task"]["base_parameters"]
    assert set(params) == {"source_table", "target_table", "pk"}
    assert params["source_table"] == "dev_churn.gold.churn_predictions"
    assert params["target_table"] == "public.churn_predictions"
    assert params["pk"] == "user_id"

    widgets = _reverse_etl_widget_defaults()
    assert set(params) <= set(widgets)


def _reverse_etl_widget_defaults() -> dict[str, str]:
    """Parse dbutils.widgets.text("name", "default") calls from reverse_etl.py."""
    tree = ast.parse(REVERSE_ETL.read_text())
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "text"
            and len(node.args) == 2
            and all(isinstance(a, ast.Constant) for a in node.args)
        ):
            out[node.args[0].value] = node.args[1].value
    return out


def test_reverse_etl_defaults_preserve_stage3_behaviour() -> None:
    """Defaults must still target churn_serving so the Stage-3 job is unchanged."""
    widgets = _reverse_etl_widget_defaults()
    assert widgets == {
        "source_table": "dev_churn.gold.churn_serving",
        "target_table": "public.churn_serving",
        "pk": "user_id",
    }
