# Stage 6 — do-now queue served from Lakebase (execution evidence)

The account-manager "do this now" queue now streams live from the **Lakebase
Autoscaling** serving layer (Stage 3), not the analytical warehouse — the visible
payoff of the serving stage. Captured 2026-09-11 on `fevm-serverless-stable-yuzk83`,
app SP `1768cda0-b24e-493f-8b2f-16fb8b8eda3a`.

## App auth to Lakebase — OAuth, no static secret

`@databricks/lakebase` (`createLakebasePool`) returns a standard `pg.Pool` whose
password is a callback minting a **short-lived OAuth token per physical connection**
(Lakebase tokens expire ~1h; a static `LAKEBASE_PASSWORD` secret would die after the
first hour). In Apps the app SP identity is auto-resolved from the ServiceContext, so
`app.yaml` carries only `LAKEBASE_HOST` + `LAKEBASE_ENDPOINT` — no secret.

## Postgres role + grant (the Stage-3-deferred grant)

The SP authenticates as a Postgres role named for its client id, created via the
`databricks_auth` extension (a plain `CREATE ROLE` will not accept Databricks OAuth
JWTs). Applied via psql/psycopg as the instance owner:

```
OK  : CREATE EXTENSION IF NOT EXISTS databricks_auth
OK  : SELECT databricks_create_role('1768cda0-…', 'SERVICE_PRINCIPAL')
OK  : GRANT CONNECT ON DATABASE databricks_postgres TO "1768cda0-…"
OK  : GRANT USAGE   ON SCHEMA   public              TO "1768cda0-…"
OK  : GRANT SELECT  ON public.churn_serving         TO "1768cda0-…"
OK  : GRANT SELECT  ON public.churn_predictions     TO "1768cda0-…"

GRANTS: churn_predictions=SELECT, churn_serving=SELECT   (verified)
```

## Live verification (served responses)

```
GET /api/health
{"status":"ok","doNowSource":"lakebase"}          ← reading Lakebase, not the warehouse

GET /api/do-now?limit=3                            ← streamed from public.churn_predictions ⋈ churn_serving
  USR-00009599 APAC high mrr 40 crm 0
  USR-00011356 EMEA high mrr 40 crm 0
  USR-00033592 EMEA high mrr 40 crm 0
  (high-risk · currently-subscribed · 0 CRM touches, ordered by MRR desc — highest-value saves first)

GET /api/do-now/count
{"count":1004}                                     ← governed-warehouse cohort count (banner headline)
```

Served SPA bundle contains the "⚡ Served live from Lakebase" pill (shown in the
Worklist when the do-now queue is open).

## UX (Option A)

The "Do this now" banner is now a button: clicking it loads the untouched-high-risk
queue into the table **from Lakebase**, with a `⚡ Served live from Lakebase` pill and a
"← All at-risk subscribers" exit. The banner headline count stays the governed-warehouse
COUNT (1,004); the streamed list is capped at 500 rows for the operational table. If the
Lakebase env is unset the queue transparently falls back to the warehouse
(`doNowSource: "warehouse"`).
