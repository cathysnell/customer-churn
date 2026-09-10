-- Stage 3 (Lakebase serving) — gold serving table.
--
-- One row per user with current churn state, built from the governed silver
-- tables. This is the SOURCE that gets synced to Lakebase Postgres for
-- low-latency operational reads (the CRM trigger / app read the Postgres copy).
--
-- A primary key (user_id) is required for the UC synced table.

CREATE SCHEMA IF NOT EXISTS dev_churn.gold
  COMMENT 'Serving/derived gold layer: per-user operational state + (later) model predictions.';

CREATE OR REPLACE TABLE dev_churn.gold.churn_serving
COMMENT 'Per-user current churn state for low-latency operational serving (Lakebase). One row per user: identity, current subscription status, and the latest observed monthly engagement/label. Synced to Lakebase; the CRM trigger and app read it here.'
AS
WITH latest_label AS (
  SELECT * EXCEPT(rn) FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY month_start DESC) rn
    FROM dev_churn.silver.churn_labels
  ) WHERE rn = 1
),
latest_sub AS (
  SELECT * EXCEPT(rn) FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY term_index DESC) rn
    FROM dev_churn.silver.subscriptions
  ) WHERE rn = 1
)
SELECT
  u.user_id,
  u.geo,
  u.plan,
  u.tier,
  u.persona,
  u.power_user_flag,
  u.signup_date,
  u.tenure_days_at_window_end,
  ls.status                              AS subscription_status,
  (ls.status IN ('active','downgraded')) AS is_currently_subscribed,
  ls.billing_period,
  ls.mrr_usd,
  ll.month_start                         AS as_of_month,
  ll.churned                             AS churned_latest_month,
  ll.tenure_months,
  ll.is_power_user_month,
  ll.active_days,
  ll.avg_coding_hours,
  ll.avg_acceptance_rate,
  ll.avg_session_frequency,
  ll.coding_hours_trend_30d,
  ll.support_tickets_30d,
  ll.features_adopted,
  ll.crm_touches_30d
FROM dev_churn.silver.users u
LEFT JOIN latest_label ll ON u.user_id = ll.user_id
LEFT JOIN latest_sub   ls ON u.user_id = ls.user_id;

ALTER TABLE dev_churn.gold.churn_serving ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE dev_churn.gold.churn_serving ADD CONSTRAINT churn_serving_pk PRIMARY KEY (user_id);
