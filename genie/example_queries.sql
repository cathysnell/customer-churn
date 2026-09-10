-- Genie space — curated example (trusted) SQL queries.
--
-- Add these in the Genie space under "SQL queries" / example queries. They teach
-- Genie the joins and the business definitions in instructions.md, and double as the
-- demo's benchmark questions. Each is paired with a natural-language title Genie
-- shows to users. All target the governed dev_churn tables.

-- Q: What is the latest monthly churn rate?
-- The churn_labels grain is one at-risk row per user per month, so AVG(churned) is
-- the churn rate directly.
SELECT ROUND(AVG(CAST(churned AS INT)), 4) AS monthly_churn_rate
FROM dev_churn.silver.churn_labels
WHERE month_start = (SELECT MAX(month_start) FROM dev_churn.silver.churn_labels);

-- Q: How has the monthly churn rate trended over time?
SELECT month_start,
       ROUND(AVG(CAST(churned AS INT)), 4) AS churn_rate,
       COUNT(*) AS at_risk_users
FROM dev_churn.silver.churn_labels
GROUP BY month_start
ORDER BY month_start;

-- Q: How many users fall into each churn risk band?
SELECT churn_risk_band,
       COUNT(*) AS users,
       ROUND(AVG(churn_score), 3) AS avg_score
FROM dev_churn.gold.churn_predictions
GROUP BY churn_risk_band
ORDER BY avg_score DESC;

-- Q: Who are the highest-risk Pro subscribers we should contact now?
-- High-risk AND currently paying, with the profile the CRM play needs.
SELECT p.user_id,
       ROUND(p.churn_score, 3) AS churn_score,
       s.geo, s.persona, s.tier, s.mrr_usd,
       ROUND(s.coding_hours_trend_30d, 2) AS coding_hours_trend_30d,
       s.crm_touches_30d
FROM dev_churn.gold.churn_predictions p
JOIN dev_churn.gold.churn_serving s USING (user_id)
WHERE p.churn_risk_band = 'high'
  AND s.is_currently_subscribed = TRUE
ORDER BY p.churn_score DESC
LIMIT 50;

-- Q: How much monthly recurring revenue is at risk from high-risk subscribers?
SELECT p.churn_risk_band,
       COUNT(*) AS users,
       ROUND(SUM(s.mrr_usd), 2) AS mrr_at_risk
FROM dev_churn.gold.churn_predictions p
JOIN dev_churn.gold.churn_serving s USING (user_id)
WHERE s.is_currently_subscribed = TRUE
GROUP BY p.churn_risk_band
ORDER BY mrr_at_risk DESC;

-- Q: Which regions have the highest churn?
SELECT geo,
       ROUND(AVG(CAST(churned AS INT)), 4) AS churn_rate,
       COUNT(*) AS at_risk_users
FROM dev_churn.silver.churn_labels
WHERE month_start = (SELECT MAX(month_start) FROM dev_churn.silver.churn_labels)
GROUP BY geo
ORDER BY churn_rate DESC;

-- Q: Do high-risk users show declining engagement vs low-risk users?
-- Confirms the headline signal: high-risk users code less and accept fewer suggestions.
SELECT p.churn_risk_band,
       ROUND(AVG(s.avg_coding_hours), 2)       AS avg_coding_hours,
       ROUND(AVG(s.coding_hours_trend_30d), 2) AS avg_coding_trend,
       ROUND(AVG(s.avg_acceptance_rate), 3)    AS avg_acceptance_rate,
       ROUND(AVG(s.avg_session_frequency), 2)  AS avg_session_frequency
FROM dev_churn.gold.churn_predictions p
JOIN dev_churn.gold.churn_serving s USING (user_id)
GROUP BY p.churn_risk_band
ORDER BY avg_coding_trend;

-- Q: Which high-risk subscribers have received no CRM outreach recently?
-- The actionable gap: at-risk revenue with no recent touch.
SELECT p.user_id, ROUND(p.churn_score, 3) AS churn_score,
       s.geo, s.persona, s.mrr_usd
FROM dev_churn.gold.churn_predictions p
JOIN dev_churn.gold.churn_serving s USING (user_id)
WHERE p.churn_risk_band = 'high'
  AND s.is_currently_subscribed = TRUE
  AND s.crm_touches_30d = 0
ORDER BY s.mrr_usd DESC
LIMIT 50;

-- Q: How does churn risk break down by persona and tier?
SELECT s.persona, s.tier,
       COUNT(*) AS users,
       SUM(CASE WHEN p.churn_risk_band = 'high' THEN 1 ELSE 0 END) AS high_risk_users
FROM dev_churn.gold.churn_serving s
JOIN dev_churn.gold.churn_predictions p USING (user_id)
WHERE s.is_currently_subscribed = TRUE
GROUP BY s.persona, s.tier
ORDER BY high_risk_users DESC;

-- Q: Are power users less likely to be high risk than non-power users?
SELECT s.power_user_flag,
       COUNT(*) AS users,
       ROUND(AVG(p.churn_score), 3) AS avg_churn_score
FROM dev_churn.gold.churn_serving s
JOIN dev_churn.gold.churn_predictions p USING (user_id)
GROUP BY s.power_user_flag;
