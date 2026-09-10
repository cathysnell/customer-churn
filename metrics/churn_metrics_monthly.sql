-- Stage 5 ontology — MONTHLY metric view (one row per user per month).
--
-- Certified historical churn metrics over dev_churn.silver.churn_labels. This is the
-- grain for "churn rate over time / by region" questions — separate from the
-- current-state view because the grains differ (monthly here vs one-row-per-user).
--
-- churn_rate is AVG of the 0/1 churned flag, which is the churn rate at any grouping
-- (the table holds one at-risk row per user per month, so no denominator adjustment).
-- Verified syntax on fevm-serverless-stable-yuzk83 2026-09-10.

CREATE OR REPLACE VIEW dev_churn.gold.churn_metrics_monthly
WITH METRICS
LANGUAGE YAML
COMMENT 'Certified monthly churn metrics (one row per user per month) over silver.churn_labels: churn rate and engagement over time, by region. Genie/BI semantic layer.'
AS $$
version: 0.1
source: dev_churn.silver.churn_labels
dimensions:
  - name: Month
    expr: month_start
  - name: Geo
    expr: geo
  - name: Is power user month
    expr: is_power_user_month
measures:
  - name: At risk users
    expr: COUNT(1)
  - name: Churned users
    expr: COUNT_IF(churned)
  - name: Churn rate
    expr: AVG(CAST(churned AS INT))
  - name: Avg coding hours
    expr: AVG(avg_coding_hours)
  - name: Avg coding hours trend
    expr: AVG(coding_hours_trend_30d)
  - name: Avg acceptance rate
    expr: AVG(avg_acceptance_rate)
$$
