# Databricks notebook source
# Stage 4 (Intelligence) — train the per-user monthly churn classifier.
#
# Trains on the governed feature/label table dev_churn.silver.churn_labels (one row
# per user per at-risk month; churned is the label). Uses a TEMPORAL split — train on
# every month except the most recent, validate on the most recent — so the metric
# reflects "predict next month from history", not a random shuffle that leaks the
# future. MLflow autologs the run; the fitted pipeline is registered to the Unity
# Catalog model registry dev_churn.gold.churn_model and promoted to the @champion
# alias, which the scoring notebook (score_churn.py) loads by alias.
#
# Runs as a SERVERLESS NOTEBOOK job (same proven path as Stage 3 serving) — Spark is
# provided by the runtime; we pull the training frame with toPandas() here because it
# is a one-shot read of a modest table inside the well-trodden notebook kernel (the
# Arrow/grpc crash in Stage 3 was in a bare spark_python_task, not a notebook).
#
# Model choice: scikit-learn HistGradientBoostingClassifier — no extra native deps,
# handles the ~570k rows in seconds on serverless, tolerates the class imbalance via
# sample weighting, and emits calibrated-enough probabilities for a risk score. The
# whole thing is a single sklearn Pipeline (impute -> GBT) so scoring is one predict.

# COMMAND ----------
# MAGIC %pip install "scikit-learn>=1.4" "mlflow>=2.15" "pandas>=2.0"

# COMMAND ----------
dbutils.library.restartPython()  # noqa: F821 (Databricks runtime builtin)

# COMMAND ----------
import mlflow
import mlflow.sklearn
import numpy as np
from mlflow.models.signature import infer_signature
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline

SOURCE_TABLE = "dev_churn.silver.churn_labels"
MODEL_NAME = "dev_churn.gold.churn_model"  # 3-level UC registry name
CHAMPION_ALIAS = "champion"

# Features the model is allowed to see. Deliberately EXCLUDES churn_date (NULL unless
# churned -> target leakage), user_id / month_start (identifiers), and geo (left out
# to keep the demo model portable across regions; add as a categorical later if desired).
NUMERIC_FEATURES = [
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
BOOL_FEATURES = ["is_power_user_month"]
FEATURES = NUMERIC_FEATURES + BOOL_FEATURES
LABEL = "churned"

# COMMAND ----------
# 1. Load the governed feature/label table. Cast the bool feature + label to int so
#    sklearn sees numbers, and pull the observation month for the temporal split.
sdf = spark.table(SOURCE_TABLE).select(  # noqa: F821 (spark provided by the runtime)
    "month_start", *FEATURES, LABEL
)
pdf = sdf.toPandas()
pdf["is_power_user_month"] = pdf["is_power_user_month"].astype("int8")
pdf[LABEL] = pdf[LABEL].astype("int8")

print(f"rows={len(pdf):,}  months={pdf['month_start'].nunique()}  "
      f"base churn rate={pdf[LABEL].mean():.4f}")

# COMMAND ----------
# 2. Temporal split: hold out the most recent month for validation.
holdout_month = pdf["month_start"].max()
train_df = pdf[pdf["month_start"] < holdout_month]
valid_df = pdf[pdf["month_start"] == holdout_month]
print(f"train rows={len(train_df):,} (< {holdout_month})   "
      f"valid rows={len(valid_df):,} (== {holdout_month})")

X_train, y_train = train_df[FEATURES], train_df[LABEL]
X_valid, y_valid = valid_df[FEATURES], valid_df[LABEL]

# Class weighting: churn is rare, so up-weight the positive class inversely to its
# frequency. HistGBT takes per-sample weights rather than a class_weight arg.
pos_rate = float(y_train.mean())
sample_weight = np.where(y_train == 1, (1 - pos_rate) / pos_rate, 1.0)

# COMMAND ----------
# 3. Fit inside an MLflow run with autologging on.
mlflow.set_registry_uri("databricks-uc")
mlflow.sklearn.autolog(log_models=False, silent=True)  # we log/register the model explicitly

pipeline = Pipeline(steps=[
    ("prep", ColumnTransformer(
        transformers=[("num", SimpleImputer(strategy="median"), NUMERIC_FEATURES)],
        remainder="passthrough",  # bool feature passes through as-is
    )),
    ("gbt", HistGradientBoostingClassifier(
        max_iter=300,
        learning_rate=0.06,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        early_stopping=True,
        validation_fraction=0.1,
        random_state=1729,  # same seed lineage as the datagen
    )),
])

with mlflow.start_run(run_name="churn-histgbt") as run:
    pipeline.fit(X_train, y_train, gbt__sample_weight=sample_weight)

    # Validation metrics on the held-out month. AUC-PR is the honest headline for a
    # rare-positive problem; ROC-AUC for continuity with common reporting.
    p_valid = pipeline.predict_proba(X_valid)[:, 1]
    auc_roc = roc_auc_score(y_valid, p_valid)
    auc_pr = average_precision_score(y_valid, p_valid)
    mlflow.log_metrics({"valid_roc_auc": auc_roc, "valid_pr_auc": auc_pr,
                        "valid_base_rate": float(y_valid.mean())})
    print(f"holdout ROC-AUC={auc_roc:.3f}  PR-AUC={auc_pr:.3f}  "
          f"base rate={y_valid.mean():.4f}")

    signature = infer_signature(X_valid, p_valid)
    mlflow.sklearn.log_model(
        pipeline,
        artifact_path="model",
        signature=signature,
        input_example=X_valid.head(3),
        registered_model_name=MODEL_NAME,
    )
    run_id = run.info.run_id

# COMMAND ----------
# 4. Promote the just-registered version to @champion (the alias score_churn.py loads).
from mlflow.tracking import MlflowClient

client = MlflowClient(registry_uri="databricks-uc")
versions = client.search_model_versions(f"name='{MODEL_NAME}' and run_id='{run_id}'")
new_version = max(int(v.version) for v in versions)
client.set_registered_model_alias(MODEL_NAME, CHAMPION_ALIAS, new_version)
client.update_model_version(
    MODEL_NAME, new_version,
    description=(f"HistGBT churn classifier. Trained on {SOURCE_TABLE} through the "
                 f"month before {holdout_month}. Holdout ROC-AUC={auc_roc:.3f}, "
                 f"PR-AUC={auc_pr:.3f}."),
)
print(f"registered {MODEL_NAME} v{new_version} -> @{CHAMPION_ALIAS}")
