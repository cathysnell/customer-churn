-- Stage 6 — Lakebase Postgres role + grants for the app's service principal.
--
-- Needed for the "do this now" queue to stream from Lakebase (Option A). Run in the
-- Lakebase database as the instance owner (psql + OAuth token — see serving/README.md).
-- This is the Postgres-side grant that Stage 3 deferred to Stage 6.
--
-- The app SP's OAuth token authenticates as a Postgres ROLE whose name is the SP's
-- CLIENT ID. A plain `CREATE ROLE` will NOT accept Databricks OAuth JWTs — the role
-- must be created with the databricks_auth extension's databricks_create_role().
--
-- App SP client id: 1768cda0-b24e-493f-8b2f-16fb8b8eda3a

CREATE EXTENSION IF NOT EXISTS databricks_auth;
SELECT databricks_create_role('1768cda0-b24e-493f-8b2f-16fb8b8eda3a', 'SERVICE_PRINCIPAL');

GRANT CONNECT ON DATABASE databricks_postgres TO "1768cda0-b24e-493f-8b2f-16fb8b8eda3a";
GRANT USAGE   ON SCHEMA   public              TO "1768cda0-b24e-493f-8b2f-16fb8b8eda3a";
GRANT SELECT  ON public.churn_serving         TO "1768cda0-b24e-493f-8b2f-16fb8b8eda3a";
GRANT SELECT  ON public.churn_predictions     TO "1768cda0-b24e-493f-8b2f-16fb8b8eda3a";

-- Verify:
--   \dp public.churn_serving
