-- Stage 6 (closed loop, layer c) — Delta landing table for outreach events synced
-- BACK from Lakebase. This is the reverse direction of the Stage-3 gold→Lakebase sync:
-- Lakebase is the system of record for operational writes, and this brings them into
-- the lakehouse so the governed crm_touches_30d can recompute.
--
-- Populated by serving/crm_outreach_sync.py (a serverless PG→Delta notebook job).
-- Run on a SQL warehouse. NOT yet applied — layer (c) is committed as artifacts and
-- deployed in a follow-up PR.

CREATE SCHEMA IF NOT EXISTS dev_churn.gold;

CREATE TABLE IF NOT EXISTS dev_churn.gold.crm_outreach_log (
  id        BIGINT   NOT NULL,
  user_id   STRING   NOT NULL,
  channel   STRING,
  note      STRING,
  logged_at TIMESTAMP
)
COMMENT 'Outreach events synced from the Lakebase system-of-record (public.crm_outreach_log) via serving/crm_outreach_sync.py. Feeds the governed crm_touches_30d recompute — the analytical half of the closed loop.';

-- Downstream (out of scope here): the labels/serving pipeline recomputes
-- crm_touches_30d from a 30-day window over this table, closing the loop back into
-- dev_churn.gold.churn_serving → the Lakebase serving copy.
