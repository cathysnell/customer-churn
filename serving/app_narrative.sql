-- Stage 5 (Genie "So what?" narrative cache) — Lakebase-native Postgres table.
--
-- Lakebase is the SYSTEM OF RECORD for the app's own cached text: this table is
-- created directly in Lakebase Postgres (NOT synced from Delta). The Overview
-- "So what?" box reads a Genie-authored qualitative narrative from here and
-- refreshes it on a ~weekly window (stale-while-revalidate); see
-- app/server/data.ts (getSoWhat) and app/server/lakebase.ts (readNarrative/writeNarrative).
--
-- The authoritative FIGURES in the box are NOT stored here — they render live from
-- the governed KPI / geo / do-now warehouse endpoints, so numbers can never drift.
-- This table holds only the qualitative narrative string + provenance.
--
-- APPROVAL GATE: run against the Lakebase Postgres database (databricks_postgres)
-- as an admin, e.g. psql with an OAuth token. Until it exists, the app degrades to
-- the templated fallback narrative (no "Powered by Genie" pill), so nothing breaks.

CREATE TABLE IF NOT EXISTS public.app_narrative (
  cache_key    TEXT        PRIMARY KEY,
  body         TEXT        NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  source       TEXT        NOT NULL CHECK (source IN ('genie', 'fallback'))
);

COMMENT ON TABLE public.app_narrative IS
  'Retention Cockpit app cache: Genie-authored qualitative narratives (e.g. the Overview "So what?" box), refreshed ~weekly. Lakebase is the system of record; not synced from Delta.';

-- Grant the app service principal read + upsert. Replace <APP_SP_ROLE> with the
-- Postgres role the Databricks App connects as (the app SP's identity in Lakebase).
-- GRANT SELECT, INSERT, UPDATE ON public.app_narrative TO "<APP_SP_ROLE>";
