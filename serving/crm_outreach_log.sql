-- Stage 6 (closed loop) — Lakebase-native outreach log. Lakebase is the SYSTEM OF
-- RECORD for this operational write: the app INSERTs a row when an account manager
-- clicks "Log outreach", and the do-now queue LEFT JOINs it to drop contacted
-- subscribers from the queue LIVE — before the (slower) warehouse crm_touches_30d
-- recompute catches up. See app/server/lakebase.ts (LOG_OUTREACH_SQL, DO_NOW_SQL) and
-- app/server/data.ts (outreach). Layer (c), serving/crm_outreach_sync.py, later lands
-- this into Delta so the lakehouse crm_touches_30d recomputes.
--
-- APPROVAL GATE: run against the Lakebase Postgres (databricks_postgres) as an admin
-- (psql + `databricks postgres generate-database-credential <endpoint>`). Until it
-- exists, the do-now Lakebase query falls back to the warehouse (no live exclusion),
-- and outreach() returns an in-memory ack.

CREATE TABLE IF NOT EXISTS public.crm_outreach_log (
  id         BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id    TEXT         NOT NULL,
  channel    TEXT         NOT NULL DEFAULT 'app',
  note       TEXT,
  logged_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS crm_outreach_log_user_time_idx
  ON public.crm_outreach_log (user_id, logged_at DESC);

COMMENT ON TABLE public.crm_outreach_log IS
  'Retention Cockpit outreach log — Lakebase is the system of record. App INSERTs on "Log outreach"; the do-now queue joins it to drop contacted users live; synced to Delta by serving/crm_outreach_sync.py.';

-- App SP needs INSERT (log) + SELECT (do-now join). Its Postgres role already exists
-- from app/lakebase_grants.sql (an IDENTITY column needs no separate sequence grant).
GRANT SELECT, INSERT ON public.crm_outreach_log TO "1768cda0-b24e-493f-8b2f-16fb8b8eda3a";
