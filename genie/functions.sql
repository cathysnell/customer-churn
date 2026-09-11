-- Stage 5 ontology — Unity Catalog functions registered as Genie TRUSTED ASSETS.
--
-- Parameterized, verified table functions. When Genie answers a matching question it
-- CALLS these (exact logic) instead of inferring SQL — the highest-trust answer path.
-- Register each in the Genie space under Trusted assets / SQL functions.
-- Verified syntax on fevm-serverless-stable-yuzk83 2026-09-10.

-- Currently-subscribed users at or above a churn-score threshold, highest first, with
-- the profile the CRM play needs. A score threshold (not a top-N LIMIT) is used
-- because a SQL function's LIMIT must be constant and a param can't be referenced in a
-- QUALIFY window filter — and "riskier than X" is the natural NL ask anyway.
CREATE OR REPLACE FUNCTION dev_churn.gold.at_risk_users(min_score DOUBLE DEFAULT 0.8)
RETURNS TABLE (
  user_id STRING, churn_score DOUBLE, churn_risk_band STRING,
  geo STRING, persona STRING, tier STRING, mrr_usd DOUBLE,
  coding_hours_trend_30d DOUBLE, crm_touches_30d BIGINT
)
COMMENT 'Currently-subscribed users with churn score >= min_score (default 0.8), profile and MRR, highest score first. Use for "who are our most at-risk subscribers / who should we contact".'
RETURN
  SELECT p.user_id, p.churn_score, p.churn_risk_band,
         s.geo, s.persona, s.tier, s.mrr_usd,
         s.coding_hours_trend_30d, s.crm_touches_30d
  FROM dev_churn.gold.churn_predictions p
  JOIN dev_churn.gold.churn_serving s USING (user_id)
  WHERE s.is_currently_subscribed = TRUE
    AND p.churn_score >= min_score
  ORDER BY p.churn_score DESC;

-- Currently-subscribed users in a given risk band who have had NO CRM touch in 30
-- days — the actionable retention gap. band in ('high','medium','low').
CREATE OR REPLACE FUNCTION dev_churn.gold.untouched_at_risk_users(band STRING DEFAULT 'high')
RETURNS TABLE (
  user_id STRING, churn_score DOUBLE, geo STRING, persona STRING, mrr_usd DOUBLE
)
COMMENT 'Currently-subscribed users in the given risk band with zero CRM touches in the last 30 days, by MRR desc. Use for "at-risk revenue with no recent outreach".'
RETURN
  SELECT p.user_id, p.churn_score, s.geo, s.persona, s.mrr_usd
  FROM dev_churn.gold.churn_predictions p
  JOIN dev_churn.gold.churn_serving s USING (user_id)
  WHERE p.churn_risk_band = band
    AND s.is_currently_subscribed = TRUE
    AND s.crm_touches_30d = 0
  ORDER BY s.mrr_usd DESC;
