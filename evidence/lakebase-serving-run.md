# Lakebase serving — execution evidence (Stage 3)

Text evidence that the governed per-user churn state is served from **Lakebase
Autoscaling** (managed Postgres) for low-latency operational reads. Captured
2026-09-10 on `fevm-serverless-stable-yuzk83`.

## Topology

```
dev_churn.silver.*  ──►  dev_churn.gold.churn_serving  ──(serverless reverse-ETL job)──►  Lakebase Postgres
  governed source        1 row/user, PK user_id, 50,000 rows        dev_churn_serving_pg.public.churn_serving
```

- **Lakebase project:** `dev-churn-serving` (Autoscaling, PG 17), endpoint
  `…/branches/production/endpoints/primary`, host
  `ep-quiet-heart-d8t4ei2i.database.us-east-2.cloud.databricks.com`.
- **UC catalog over PG:** `dev_churn_serving_pg` (registers the Postgres DB in UC).
- **Sync job:** `dev-churn-reverse-etl-serving` (job id 1029175375045470), serverless
  notebook, full-snapshot refresh (TRUNCATE + COPY), daily schedule (paused).

## Why a serverless job (not a UC synced table)

The managed UC synced-table pipeline could not run here: its sync pipeline uses
**classic compute**, which needs the metastore storage root URL — and this
workspace's metastore has none:

```
UNITY_CATALOG_INITIALIZATION_FAILED … [INVALID_STATE] Metastore storage root URL does not exist
```

Our ingestion pipeline only worked because it is **serverless**. So the reverse ETL
is a serverless notebook job that reads the gold Delta table with Spark and
`COPY`s it into Postgres — no classic compute, no metastore-root dependency.

## Reverse-ETL run

Serverless notebook run (`jobs submit`) — **SUCCESS**:

```
read 50,000 rows / 24 cols from dev_churn.gold.churn_serving
loaded 50,000 rows into Lakebase public.churn_serving
```

Two issues found and fixed during bring-up (both runtime, not logic):
1. `toPandas()` crashed the serverless kernel via the Arrow/grpc native path →
   switched to `collect()` + psycopg3 `write_row` (types/NULLs handled natively).
2. `WorkspaceClient` had no `postgres` attribute → the runtime's bundled
   `databricks-sdk` predates 0.81.0; pinned `databricks-sdk>=0.81.0` in `%pip`.

## Verification (queried directly against Lakebase Postgres)

```
row_count:            50,000          -- matches the gold source exactly
currently_subscribed: 26,568

sample point lookup (user_id = 'USR-00000021'):
  user_id      | geo   | subscription_status | churned_latest_month | avg_coding_hours | coding_hours_trend_30d
  USR-00000021 | LATAM | active              | false                | 11.279           | 0.9844

point-lookup latency (PK indexed, 5 reads): min=59.37 ms  median=91.65 ms  max=133.00 ms
```

Latency was measured from a laptop across regions (client → us-east-2); in-workspace
reads (the CRM trigger / app path) are lower. The point is the operational access
pattern: single-user key lookups against the served table.

## Access / grants

The reverse-ETL job reads the source Delta and writes to Lakebase as its **run-as
identity** — no extra UC grant needed. The **app** (Stage 6) reads Lakebase Postgres
and gets a **Postgres-side role grant to its service principal** then; deliberately
not granted here (per-stage governance model).
