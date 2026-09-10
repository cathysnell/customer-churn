"""Stage 3 serving — serverless reverse ETL: dev_churn.gold.churn_serving -> Lakebase Postgres.

Runs as a Databricks **serverless** job (this workspace's metastore has no storage
root, so the managed UC synced-table pipeline — which uses classic compute — fails
with UNITY_CATALOG_INITIALIZATION_FAILED; serverless works, so we sync ourselves).

Full-snapshot refresh (matches SNAPSHOT semantics): read the governed gold table
with Spark, then TRUNCATE + COPY into Postgres inside one transaction. For ~50k
rows this is a couple of seconds. Idempotent; safe to schedule (e.g. daily).

Access: connects as the job's run-as identity via a short-lived OAuth token
(w.postgres.generate_database_credential). The app SP gets its own Postgres role
grant in Stage 6 — not here.
"""
import io
import time

import psycopg
from databricks.sdk import WorkspaceClient

SOURCE_TABLE = "dev_churn.gold.churn_serving"
ENDPOINT = "projects/dev-churn-serving/branches/production/endpoints/primary"
PG_DATABASE = "databricks_postgres"
TARGET_TABLE = "public.churn_serving"
PK = "user_id"

# Spark SQL type -> Postgres type
_PG_TYPE = {
    "string": "TEXT", "boolean": "BOOLEAN", "date": "DATE",
    "double": "DOUBLE PRECISION", "float": "REAL",
    "bigint": "BIGINT", "long": "BIGINT", "int": "INTEGER", "integer": "INTEGER",
    "timestamp": "TIMESTAMPTZ",
}


def _pg_type(spark_type: str) -> str:
    return _PG_TYPE.get(spark_type.lower(), "TEXT")


def main() -> None:
    w = WorkspaceClient()

    # 1. Read the governed gold serving table (Spark is available on serverless).
    sdf = spark.table(SOURCE_TABLE)  # noqa: F821 (spark provided by the runtime)
    cols = [(f.name, _pg_type(f.dataType.typeName())) for f in sdf.schema.fields]
    pdf = sdf.toPandas()
    print(f"read {len(pdf):,} rows / {len(cols)} cols from {SOURCE_TABLE}")

    # 2. Connect to Lakebase with a short-lived OAuth token.
    ep = w.postgres.get_endpoint(name=ENDPOINT)
    host = ep.status.hosts.host
    token = w.postgres.generate_database_credential(endpoint=ENDPOINT).token
    user = w.current_user.me().user_name
    conn_str = (
        f"host={host} dbname={PG_DATABASE} user={user} "
        f"password={token} sslmode=require"
    )

    ddl_cols = ", ".join(f'"{n}" {t}' for n, t in cols)
    col_list = ", ".join(f'"{n}"' for n, _ in cols)

    t0 = time.time()
    with psycopg.connect(conn_str, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f'CREATE TABLE IF NOT EXISTS {TARGET_TABLE} '
                f'({ddl_cols}, PRIMARY KEY ("{PK}"))'
            )
            # Full-snapshot refresh in one transaction.
            cur.execute(f"TRUNCATE {TARGET_TABLE}")
            buf = io.StringIO()
            pdf.to_csv(buf, index=False, header=False, na_rep="\\N")
            buf.seek(0)
            with cur.copy(
                f"COPY {TARGET_TABLE} ({col_list}) FROM STDIN WITH (FORMAT csv, NULL '\\N')"
            ) as cp:
                cp.write(buf.read())
        conn.commit()

    # 3. Verify.
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {TARGET_TABLE}")
            n = cur.fetchone()[0]
    print(f"loaded {n:,} rows into Lakebase {TARGET_TABLE} in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
