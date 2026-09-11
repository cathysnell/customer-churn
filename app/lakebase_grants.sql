-- Stage 6 — Lakebase Postgres grants for the "do this now" queue (optional path).
--
-- Only needed once you wire the Lakebase env in app.yaml (the app falls back to the
-- warehouse otherwise). Run in the Lakebase Postgres database as the instance owner
-- (psql with an OAuth token — see serving/README.md for the connection pattern). This
-- is the Postgres-side grant that Stage 3 deliberately deferred to Stage 6.
--
-- Replace <app_sp_role> with the app SP's Postgres role (its application id).

GRANT USAGE ON SCHEMA public TO "<app_sp_role>";
GRANT SELECT ON public.churn_serving     TO "<app_sp_role>";
GRANT SELECT ON public.churn_predictions TO "<app_sp_role>";

-- Verify:
--   \dp public.churn_serving
