from pyspark import pipelines as dp
from pyspark.sql.functions import col, current_timestamp

# ---- Bronze: raw A06 telemetry, ingested incrementally via Auto Loader ----
@dp.table(
    name="dev_churn.bronze.usage_events_raw",
    comment="A06 raw developer-behavior telemetry via Auto Loader",
)
def usage_events_raw():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "parquet")
        .option("cloudFiles.schemaLocation",
                "/Volumes/dev_churn/landing/raw/_schemas/usage_events")
        .load("/Volumes/dev_churn/landing/raw/usage_events/")
        # cheap, high-value lineage/debug breadcrumbs
        .withColumn("_source_file", col("_metadata.file_path"))
        .withColumn("_ingested_at", current_timestamp())
    )

# ---- Silver: typed + quality-checked ----
# Expectations bind to this function's OUTPUT columns, so valid_accept references
# the aliased `ai_acceptance_rate`, not the source `ai_suggestion_acceptance_rate`.
@dp.table(
    name="dev_churn.silver.usage_events",
    comment="A06 cleaned/typed telemetry with data-quality expectations",
)
@dp.expect_all_or_drop({"valid_user": "user_id IS NOT NULL"})
@dp.expect_all({
    "valid_hours":  "coding_hours BETWEEN 0 AND 24",
    "valid_accept": "ai_acceptance_rate BETWEEN 0 AND 1",
})
def usage_events():
    return (
        spark.readStream.table("dev_churn.bronze.usage_events_raw")
        .selectExpr(
            "CAST(user_id AS STRING)                       AS user_id",
            "CAST(event_date AS DATE)                      AS event_date",
            "CAST(coding_hours AS DOUBLE)                  AS coding_hours",
            "CAST(ai_suggestion_acceptance_rate AS DOUBLE) AS ai_acceptance_rate",
            "CAST(session_frequency AS INT)                AS session_frequency",
            "geo",
        )
    )
