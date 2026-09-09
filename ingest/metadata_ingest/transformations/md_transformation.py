from metadata import TABLES
from pyspark import pipelines as dp
from pyspark.sql.functions import col, current_timestamp

BASE = "/Volumes/dev_churn/landing/raw"

def build(spec):                       # factory = clean per-table closure
    name = spec["name"]

    @dp.table(name=f"dev_churn.bronze.{name}_raw",
              comment=f"raw {name} via Auto Loader")
    def _bronze(spec=spec, name=name):
        return (spark.readStream.format("cloudFiles")
                .option("cloudFiles.format", spec["format"])
                .option("cloudFiles.schemaLocation", f"{BASE}/_schemas/{name}")
                .load(f"{BASE}/{name}/")
                .withColumn("_source_file", col("_metadata.file_path"))
                .withColumn("_ingested_at", current_timestamp()))

    @dp.table(name=f"dev_churn.silver.{name}",
              comment=f"typed + quality-checked {name}")
    @dp.expect_all_or_drop(spec["expect_drop"])
    @dp.expect_all(spec["expect_keep"])
    def _silver(spec=spec, name=name):
        return spark.readStream.table(f"dev_churn.bronze.{name}_raw").selectExpr(*spec["select"])

for spec in TABLES:
    build(spec)
