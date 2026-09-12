# Databricks notebook source
# Serverless sync: Lakebase Postgres -> a governed Delta table. The REVERSE direction
# of serving/reverse_etl.py — it brings operational writes (the outreach log, whose
# system of record is Lakebase) back into the lakehouse so the governed crm_touches_30d
# can recompute. This is the analytical half of the closed loop (layer c).
#
# Why a self-managed notebook (not managed Lakehouse Sync / Lakebase CDF): the managed
# PG->Delta path is Public Preview, AND this workspace's metastore has no storage root,
# so managed UC synced-table pipelines fail here (UNITY_CATALOG_INITIALIZATION_FAILED)
# — the same reason the forward gold->Lakebase sync is a serverless notebook. Serverless
# works, so we sync ourselves, mirroring reverse_etl.py's idioms (psycopg + Spark, no
# toPandas). Incremental append by an id high-watermark (the log is append-only).
#
# NOT yet deployed — committed as an artifact; import + `databricks jobs create
# --json @serving/crm_outreach_sync_job.json` in a follow-up PR.

# COMMAND ----------
# MAGIC %pip install "psycopg[binary]" "databricks-sdk>=0.81.0"

# COMMAND ----------
dbutils.library.restartPython()  # noqa: F821 (Databricks runtime builtin)

# COMMAND ----------
import time

import psycopg
from databricks.sdk import WorkspaceClient

dbutils.widgets.text("source_table", "public.crm_outreach_log")  # noqa: F821 (Lakebase, source of truth)
dbutils.widgets.text("target_table", "dev_churn.gold.crm_outreach_log")  # noqa: F821 (Delta landing)
SOURCE_TABLE = dbutils.widgets.get("source_table")  # noqa: F821
TARGET_TABLE = dbutils.widgets.get("target_table")  # noqa: F821

ENDPOINT = "projects/dev-churn-serving/branches/production/endpoints/primary"
PG_DATABASE = "databricks_postgres"

w = WorkspaceClient()

# 1. Connect to Lakebase with a short-lived OAuth token (same pattern as reverse_etl.py).
ep = w.postgres.get_endpoint(name=ENDPOINT)
host = ep.status.hosts.host
token = w.postgres.generate_database_credential(endpoint=ENDPOINT).token
user = w.current_user.me().user_name
conn_str = f"host={host} dbname={PG_DATABASE} user={user} password={token} sslmode=require"

# 2. High-watermark: only pull rows newer than what's already in Delta (append-only log).
#    (First run — table empty or absent — pulls everything.)
try:
    hi = spark.sql(f"SELECT COALESCE(MAX(id), 0) AS hi FROM {TARGET_TABLE}").collect()[0]["hi"]  # noqa: F821
except Exception:
    hi = 0
print(f"delta high-watermark id = {hi}")

# 3. Read new rows from the Lakebase system-of-record.
with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, user_id, channel, note, logged_at "
            f"FROM {SOURCE_TABLE} WHERE id > %s ORDER BY id",
            (hi,),
        )
        new_rows = cur.fetchall()
print(f"read {len(new_rows):,} new rows from Lakebase {SOURCE_TABLE}")

# 4. Append to the governed Delta table.
if new_rows:
    t0 = time.time()
    df = spark.createDataFrame(  # noqa: F821
        new_rows, schema="id long, user_id string, channel string, note string, logged_at timestamp"
    )
    df.write.mode("append").saveAsTable(TARGET_TABLE)
    print(f"appended {len(new_rows):,} rows to Delta {TARGET_TABLE} in {time.time() - t0:.1f}s")
else:
    print("nothing new to sync")
