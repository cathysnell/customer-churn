# Databricks notebook source
# Stage 4 (Intelligence) — score the current at-risk cohort and write predictions back
# as a governed gold table.
#
# Loads the @champion model registered by train_churn_model.py, scores the most recent
# at-risk month for each user (the same "latest row per user" cohort the Stage-3
# serving table exposes), and writes dev_churn.gold.churn_predictions: one row per
# user with a churn propensity score, a coarse risk band for the CRM trigger, and the
# model version for auditability. The table is documented (table + column comments)
# and carries a user_id primary key so it can be synced to Lakebase exactly like
# churn_serving. This table is NOT Lakeflow-owned, so ALTER ... COMMENT / PRIMARY KEY
# apply cleanly here (unlike the silver streaming tables in Stage 2).
#
# Runs as a serverless notebook job, downstream of the train task.

# COMMAND ----------
# MAGIC %pip install "scikit-learn>=1.4" "mlflow>=2.15" "pandas>=2.0"

# COMMAND ----------
dbutils.library.restartPython()  # noqa: F821 (Databricks runtime builtin)

# COMMAND ----------
import mlflow
import pandas as pd
from pyspark.sql import functions as F
from pyspark.sql.window import Window

SOURCE_TABLE = "dev_churn.silver.churn_labels"
MODEL_NAME = "dev_churn.gold.churn_model"
CHAMPION_ALIAS = "champion"
TARGET_TABLE = "dev_churn.gold.churn_predictions"

# Must match train_churn_model.py.
NUMERIC_FEATURES = [
    "tenure_months", "active_days", "avg_coding_hours", "avg_acceptance_rate",
    "avg_session_frequency", "coding_hours_trend_30d", "support_tickets_30d",
    "features_adopted", "crm_touches_30d",
]
BOOL_FEATURES = ["is_power_user_month"]
FEATURES = NUMERIC_FEATURES + BOOL_FEATURES

# COMMAND ----------
# 1. Current cohort: the most recent at-risk month for each user.
w = Window.partitionBy("user_id").orderBy(F.col("month_start").desc())
cohort = (
    spark.table(SOURCE_TABLE)  # noqa: F821 (spark provided by the runtime)
    .withColumn("_rn", F.row_number().over(w))
    .where(F.col("_rn") == 1)
    .drop("_rn")
)
pdf = cohort.select("user_id", "month_start", *FEATURES).toPandas()
pdf["is_power_user_month"] = pdf["is_power_user_month"].astype("int8")
print(f"cohort rows={len(pdf):,}  as_of_month={pdf['month_start'].max()}")

# COMMAND ----------
# 2. Load @champion and score. Resolve the concrete version for the audit column.
mlflow.set_registry_uri("databricks-uc")
model_uri = f"models:/{MODEL_NAME}@{CHAMPION_ALIAS}"
model = mlflow.sklearn.load_model(model_uri)

from mlflow.tracking import MlflowClient

mv = MlflowClient(registry_uri="databricks-uc").get_model_version_by_alias(
    MODEL_NAME, CHAMPION_ALIAS)
model_version = int(mv.version)

pdf["churn_score"] = model.predict_proba(pdf[FEATURES])[:, 1]

# Coarse risk band for the CRM trigger (thresholds are demo defaults; tune to the
# retention team's capacity). high -> personalized outreach, medium -> nurture.
def _band(p: float) -> str:
    if p >= 0.60:
        return "high"
    if p >= 0.30:
        return "medium"
    return "low"

pdf["churn_risk_band"] = pdf["churn_score"].map(_band)
pdf["model_name"] = MODEL_NAME
pdf["model_version"] = model_version
pdf["scored_at"] = pd.Timestamp.utcnow().tz_localize(None)

out = pdf[["user_id", "month_start", "churn_score", "churn_risk_band",
           "model_name", "model_version", "scored_at"]].rename(
    columns={"month_start": "as_of_month"})
print(out["churn_risk_band"].value_counts().to_dict())

# COMMAND ----------
# 3. Write the governed predictions table, then document it and set the PK.
sdf_out = spark.createDataFrame(out)  # noqa: F821 (spark provided by the runtime)
(sdf_out.write.mode("overwrite")
 .option("overwriteSchema", "true")
 .saveAsTable(TARGET_TABLE))

_table_comment = (
    "Per-user churn propensity from the Stage-4 @champion model. One row per user "
    "(latest at-risk month), consumed by the CRM re-engagement trigger and the app "
    "via Lakebase."
)
spark.sql(  # noqa: F821 (spark provided by the runtime)
    f"ALTER TABLE {TARGET_TABLE} SET TBLPROPERTIES ('comment' = '{_table_comment}')"
)
_COMMENTS = {
    "user_id": "FK to users.user_id. Primary key of this table (one row per user).",
    "as_of_month": "Observation month the features were drawn from (latest at-risk month).",
    "churn_score": "Model churn propensity in [0,1] — P(user cancels next month).",
    "churn_risk_band": "Coarse band for the CRM trigger: high (>=0.60), medium (>=0.30), low.",
    "model_name": "UC registry name of the scoring model.",
    "model_version": "UC model version used for this score (audit trail).",
    "scored_at": "UTC timestamp this scoring run wrote the row.",
}
for col, comment in _COMMENTS.items():
    esc = comment.replace("'", "''")
    spark.sql(f"ALTER TABLE {TARGET_TABLE} ALTER COLUMN {col} COMMENT '{esc}'")  # noqa: F821

spark.sql(f"ALTER TABLE {TARGET_TABLE} ALTER COLUMN user_id SET NOT NULL")  # noqa: F821
spark.sql(f"ALTER TABLE {TARGET_TABLE} ADD CONSTRAINT churn_predictions_pk PRIMARY KEY (user_id)")  # noqa: F821

print(f"wrote {out.shape[0]:,} rows to {TARGET_TABLE} (model v{model_version})")
