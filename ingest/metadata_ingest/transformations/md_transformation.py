from metadata import TABLES
from pyspark import pipelines as dp
from pyspark.sql.functions import col, current_timestamp

BASE = "/Volumes/dev_churn/landing/raw"

def _schema_ddl(columns):
    # Build "name TYPE COMMENT '...'" for each column. An explicit schema is how
    # UC column comments get set on a Lakeflow streaming table (DataFrame column
    # metadata does not propagate). All columns declared nullable so the schema
    # never fights the data — validation is the expectations' job. Single quotes
    # in comment text are doubled for the DDL string literal.
    return ", ".join(
        f"{c['name']} {c['type']} COMMENT '{c['comment'].replace(chr(39), chr(39) * 2)}'"
        for c in columns
    )

def build(spec):                       # factory = clean per-table closure
    name = spec["name"]

    @dp.table(name=f"dev_churn.bronze.{name}_raw",
              comment=f"raw {name} via Auto Loader",
              table_properties={"delta.feature.timestampNtz": "supported"})
    def _bronze(spec=spec, name=name):
        return (spark.readStream.format("cloudFiles")
                .option("cloudFiles.format", spec["format"])
                .option("cloudFiles.schemaLocation", f"{BASE}/_schemas/{name}")
                .load(f"{BASE}/{name}/")
                .withColumn("_source_file", col("_metadata.file_path"))
                .withColumn("_ingested_at", current_timestamp()))

    # Silver: typed, quality-checked, and GOVERNED. The table comment and the
    # schema (which carries per-column UC comments) come from the metadata, so
    # governance is set by the pipeline that owns the table rather than ALTER-ed
    # on afterward (which Lakeflow would reject/clobber).
    @dp.table(name=f"dev_churn.silver.{name}",
              comment=spec["comment"],
              schema=_schema_ddl(spec["columns"]))
    @dp.expect_all_or_drop(spec["expect_drop"])
    @dp.expect_all(spec["expect_keep"])
    def _silver(spec=spec, name=name):
        projection = [f"{c['expr']} AS {c['name']}" for c in spec["columns"]]
        return spark.readStream.table(f"dev_churn.bronze.{name}_raw").selectExpr(*projection)

for spec in TABLES:
    build(spec)
