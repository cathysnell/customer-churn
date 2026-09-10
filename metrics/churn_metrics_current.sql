-- Stage 5 ontology — CURRENT-STATE metric view (one row per user).
--
-- A Unity Catalog metric view: a governed, certified semantic layer over the
-- current per-user state (gold.churn_serving joined to gold.churn_predictions on
-- user_id). Genie resolves measures from THIS definition instead of inferring the
-- join/aggregation from prose, so answers about the current base are deterministic.
--
-- Query it with MEASURE():  SELECT risk_band, MEASURE(mrr_at_risk) FROM ... GROUP BY risk_band
-- Deploy on a SQL warehouse.  Verified syntax on fevm-serverless-stable-yuzk83 2026-09-10.

CREATE OR REPLACE VIEW dev_churn.gold.churn_metrics_current
WITH METRICS
LANGUAGE YAML
COMMENT 'Certified current-state churn metrics (one row per user): risk bands, MRR at risk, and engagement, joined from churn_serving + churn_predictions. Genie/BI semantic layer.'
AS $$
version: 0.1
source: |
  SELECT
    s.geo, s.persona, s.tier, s.plan, s.power_user_flag,
    s.subscription_status, s.is_currently_subscribed, s.mrr_usd,
    p.churn_risk_band, p.churn_score,
    s.avg_coding_hours, s.coding_hours_trend_30d,
    s.avg_acceptance_rate, s.avg_session_frequency, s.active_days
  FROM dev_churn.gold.churn_serving s
  JOIN dev_churn.gold.churn_predictions p USING (user_id)
dimensions:
  - name: Geo
    expr: geo
  - name: Persona
    expr: persona
  - name: Tier
    expr: tier
  - name: Plan
    expr: plan
  - name: Risk band
    expr: churn_risk_band
  - name: Subscription status
    expr: subscription_status
  - name: Is currently subscribed
    expr: is_currently_subscribed
  - name: Is power user
    expr: power_user_flag
measures:
  - name: Users
    expr: COUNT(1)
  - name: Currently subscribed users
    expr: COUNT_IF(is_currently_subscribed)
  - name: High risk users
    expr: COUNT_IF(churn_risk_band = 'high')
  - name: Total MRR
    expr: SUM(mrr_usd)
  # MRR of currently-subscribed users — slice by the Risk band dimension for
  # "MRR at risk". Use this rather than reading churn_score as a probability.
  - name: MRR at risk
    expr: SUM(mrr_usd) FILTER (WHERE is_currently_subscribed)
  - name: Avg churn score
    expr: AVG(churn_score)
  - name: Avg coding hours trend
    expr: AVG(coding_hours_trend_30d)
  - name: Avg acceptance rate
    expr: AVG(avg_acceptance_rate)
  - name: Avg session frequency
    expr: AVG(avg_session_frequency)
$$
