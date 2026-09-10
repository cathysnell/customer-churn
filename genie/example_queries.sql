-- Genie space — curated example (trusted) SQL queries.
--
-- SYNCED FROM THE LIVE SPACE (space_id 01f1ad360e121f099e3070de938cd8cb) 2026-09-10.
-- Genie routes to the metric views / trusted functions where possible; the
-- remaining raw-table queries are aggregations Genie resolves directly. Each -- Q:
-- line is the question Genie shows. Source of truth = the live space; re-sync with
--   databricks genie get-space <id> --include-serialized-space

-- Q: What is the latest monthly churn rate?
SELECT MEASURE(`Churn rate`) AS churn_rate
 FROM dev_churn.gold.churn_metrics_monthly
 WHERE `Month` = (SELECT MAX(`Month`) FROM dev_churn.gold.churn_metrics_monthly);

-- Q: How has the monthly churn rate trended over time?
SELECT `Month`, MEASURE(`Churn rate`) AS churn_rate
 FROM dev_churn.gold.churn_metrics_monthly
 GROUP BY `Month`
 ORDER BY `Month`;

-- Q: How many users fall into each churn risk band?
SELECT churn_risk_band,
        COUNT(*) AS users,
        ROUND(AVG(churn_score), 3) AS avg_score
 FROM dev_churn.gold.churn_predictions
 GROUP BY churn_risk_band
 ORDER BY avg_score DESC;

-- Q: Who are the highest-risk Pro subscribers we should contact now?
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
SELECT `Geo`, MEASURE(`Churn rate`) AS churn_rate
 FROM dev_churn.gold.churn_metrics_monthly
 WHERE `Month` = (SELECT MAX(`Month`) FROM dev_churn.gold.churn_metrics_monthly)
 GROUP BY `Geo`
 ORDER BY churn_rate DESC;

-- Q: Do high-risk users show declining engagement vs low-risk users?
SELECT `Risk band`, MEASURE(`Avg coding hours trend`) AS avg_coding_trend
 FROM dev_churn.gold.churn_metrics_current
 GROUP BY `Risk band`
 ORDER BY avg_coding_trend;

-- Q: Which high-risk subscribers have received no CRM outreach recently?
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
SELECT `Is power user`, MEASURE(`Avg churn score`) AS avg_churn_score
 FROM dev_churn.gold.churn_metrics_current
 GROUP BY `Is power user`;

-- Q: Who are our most at-risk subscribers?
SELECT *
 FROM dev_churn.gold.at_risk_users(0.9);
