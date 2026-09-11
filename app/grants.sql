-- Stage 6 — Unity Catalog grants for the Retention Cockpit app's service principal.
--
-- The warehouse CAN_USE grant is handled by the bundle (app resource). These UC
-- grants are NOT auto-granted, so run this once after `databricks bundle run cockpit`
-- creates the app + its SP. Get the SP's application id from:
--   databricks apps get retention-cockpit  ->  .service_principal_client_id
--
-- Replace :app_sp below with that application id (a UUID), keeping the backticks.
-- Run on the same warehouse as the app (128c306447d9ef00), as a user who can grant.

-- Catalog / schema traversal (required before table/function grants resolve).
GRANT USE CATALOG ON CATALOG dev_churn TO `:app_sp`;
GRANT USE SCHEMA  ON SCHEMA  dev_churn.gold   TO `:app_sp`;
GRANT USE SCHEMA  ON SCHEMA  dev_churn.silver TO `:app_sp`;

-- Governed tables the app reads.
GRANT SELECT ON TABLE dev_churn.gold.churn_serving     TO `:app_sp`;
GRANT SELECT ON TABLE dev_churn.gold.churn_predictions TO `:app_sp`;
GRANT SELECT ON TABLE dev_churn.silver.churn_labels    TO `:app_sp`;

-- Certified metric views (the KPI / trend / MRR-by-band semantic layer).
GRANT SELECT ON VIEW dev_churn.gold.churn_metrics_current TO `:app_sp`;
GRANT SELECT ON VIEW dev_churn.gold.churn_metrics_monthly TO `:app_sp`;

-- Trusted functions (worklist / do-now fallback).
GRANT EXECUTE ON FUNCTION dev_churn.gold.at_risk_users            TO `:app_sp`;
GRANT EXECUTE ON FUNCTION dev_churn.gold.untouched_at_risk_users  TO `:app_sp`;

-- Verify:
--   SHOW GRANTS `:app_sp` ON TABLE dev_churn.gold.churn_serving;
