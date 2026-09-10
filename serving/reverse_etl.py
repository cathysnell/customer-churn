# Databricks notebook source
# Stage 3 serving — serverless reverse ETL: dev_churn.gold.churn_serving -> Lakebase Postgres.
#
# Runs as a serverless NOTEBOOK job (this workspace's metastore has no storage root,
# so the managed UC synced-table pipeline — classic compute — fails with
# UNITY_CATALOG_INITIALIZATION_FAILED; serverless works, so we sync ourselves).
#
# Full-snapshot refresh (SNAPSHOT semantics): read the governed gold table with
# Spark, then TRUNCATE + COPY into Postgres in one transaction. Uses Spark
# collect() + psycopg3 write_row (types/NULLs handled natively) — deliberately NOT
# toPandas(), which crashed the serverless kernel via the Arrow/grpc native path.
#
# Access: connects as the run-as identity via a short-lived OAuth token. The app SP
# gets its own Postgres role grant in Stage 6 — not here.

# COMMAND ----------
# MAGIC %pip install "psycopg[binary]" "databricks-sdk>=0.81.0"

# COMMAND ----------
dbutils.library.restartPython()  # noqa: F821 (Databricks runtime builtin)

# COMMAND ----------
import time

import psycopg
from databricks.sdk import WorkspaceClient

SOURCE_TABLE = "dev_churn.gold.churn_serving"
ENDPOINT = "projects/dev-churn-serving/branches/production/endpoints/primary"
PG_DATABASE = "databricks_postgres"
TARGET_TABLE = "public.churn_serving"
PK = "user_id"

_PG_TYPE = {
    "string": "TEXT", "boolean": "BOOLEAN", "date": "DATE",
    "double": "DOUBLE PRECISION", "float": "REAL",
    "bigint": "BIGINT", "long": "BIGINT", "int": "INTEGER", "integer": "INTEGER",
    "timestamp": "TIMESTAMPTZ",
}


def _pg_type(spark_type: str) -> str:
    return _PG_TYPE.get(spark_type.lower(), "TEXT")


w = WorkspaceClient()

# 1. Read the governed gold serving table (collect, not toPandas).
sdf = spark.table(SOURCE_TABLE)  # noqa: F821 (spark provided by the runtime)
cols = [(f.name, _pg_type(f.dataType.typeName())) for f in sdf.schema.fields]
rows = sdf.collect()
print(f"read {len(rows):,} rows / {len(cols)} cols from {SOURCE_TABLE}")

# 2. Connect to Lakebase with a short-lived OAuth token.
ep = w.postgres.get_endpoint(name=ENDPOINT)
host = ep.status.hosts.host
token = w.postgres.generate_database_credential(endpoint=ENDPOINT).token
user = w.current_user.me().user_name
conn_str = f"host={host} dbname={PG_DATABASE} user={user} password={token} sslmode=require"

ddl_cols = ", ".join(f'"{n}" {t}' for n, t in cols)
col_list = ", ".join(f'"{n}"' for n, _ in cols)

# 3. Full-snapshot refresh in one transaction.
t0 = time.time()
with psycopg.connect(conn_str, autocommit=False) as conn:
    with conn.cursor() as cur:
        cur.execute(
            f'CREATE TABLE IF NOT EXISTS {TARGET_TABLE} ({ddl_cols}, PRIMARY KEY ("{PK}"))'
        )
        cur.execute(f"TRUNCATE {TARGET_TABLE}")
        with cur.copy(f"COPY {TARGET_TABLE} ({col_list}) FROM STDIN") as cp:
            for r in rows:
                cp.write_row(tuple(r))
    conn.commit()

# 4. Verify.
with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {TARGET_TABLE}")
        n = cur.fetchone()[0]
print(f"loaded {n:,} rows into Lakebase {TARGET_TABLE} in {time.time() - t0:.1f}s")
