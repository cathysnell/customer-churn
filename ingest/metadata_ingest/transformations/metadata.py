"""Metadata for the metadata-driven ingestion pipeline.

One dict per source table. `md_transformation.py` loops over ``TABLES`` and
generates a bronze (Auto Loader) + silver (typed, quality-checked) pair for each,
so adding a source is a config entry here rather than new code.

Per-entry keys:
  name         target table stem -> dev_churn.bronze.<name>_raw / dev_churn.silver.<name>
  format       Auto Loader file format in the landing Volume (parquet here)
  select       silver projection: the CAST/rename list applied to the bronze rows
  expect_drop  expectations that DROP violating rows (unusable records)
  expect_keep  expectations that only RECORD violations as metrics (rows kept)

The `select` cast lists are derived from `src/datagen/schemas.py` (the generator's
single source of truth), so silver types stay in lockstep with the emitted data.
`usage_events` is kept identical to the hard-coded `usage_events_ingest` pipeline's
curated silver, because both pipelines write the same `dev_churn.silver.usage_events`.
"""

TABLES = [
    {
        "name": "users",
        "format": "parquet",
        "select": [
            "CAST(user_id AS STRING) AS user_id",
            "CAST(signup_date AS DATE) AS signup_date",
            "CAST(geo AS STRING) AS geo",
            "CAST(country AS STRING) AS country",
            "CAST(plan AS STRING) AS plan",
            "CAST(tier AS STRING) AS tier",
            "CAST(persona AS STRING) AS persona",
            "CAST(company_size AS STRING) AS company_size",
            "CAST(acquisition_channel AS STRING) AS acquisition_channel",
            "CAST(primary_language AS STRING) AS primary_language",
            "CAST(ide_theme AS STRING) AS ide_theme",
            "CAST(power_user_flag AS BOOLEAN) AS power_user_flag",
            "CAST(tenure_days_at_window_end AS BIGINT) AS tenure_days_at_window_end",
        ],
        "expect_drop": {"valid_user": "user_id IS NOT NULL"},
        "expect_keep": {
            "valid_geo": "geo IN ('NA','EMEA','APAC','LATAM','MEA','ANZ')",
            "valid_tier": "tier = 'pro'",
        },
    },
    {
        "name": "subscriptions",
        "format": "parquet",
        "select": [
            "CAST(subscription_id AS STRING) AS subscription_id",
            "CAST(user_id AS STRING) AS user_id",
            "CAST(plan_id AS STRING) AS plan_id",
            "CAST(plan_name AS STRING) AS plan_name",
            "CAST(tier AS STRING) AS tier",
            "CAST(billing_period AS STRING) AS billing_period",
            "CAST(mrr_usd AS DOUBLE) AS mrr_usd",
            "CAST(list_price_usd AS DOUBLE) AS list_price_usd",
            "CAST(term_start_date AS DATE) AS term_start_date",
            "CAST(term_end_date AS DATE) AS term_end_date",
            "CAST(term_index AS BIGINT) AS term_index",
            "CAST(status AS STRING) AS status",
            "CAST(renewals_count AS BIGINT) AS renewals_count",
            "CAST(payment_failures AS BIGINT) AS payment_failures",
            "CAST(is_downgrade AS BOOLEAN) AS is_downgrade",
            "CAST(is_reactivation AS BOOLEAN) AS is_reactivation",
            "CAST(cancel_date AS DATE) AS cancel_date",
            "CAST(cancel_reason AS STRING) AS cancel_reason",
            "CAST(revenue_usd AS DOUBLE) AS revenue_usd",
        ],
        "expect_drop": {"valid_subscription": "subscription_id IS NOT NULL"},
        "expect_keep": {
            "valid_mrr": "mrr_usd >= 0",
            "valid_billing": "billing_period IN ('monthly','annual')",
        },
    },
    {
        # Kept identical to the hard-coded usage_events_ingest pipeline's silver:
        # both write dev_churn.silver.usage_events, so the projection must match.
        "name": "usage_events",
        "format": "parquet",
        "select": [
            "CAST(user_id AS STRING) AS user_id",
            "CAST(event_date AS DATE) AS event_date",
            "CAST(coding_hours AS DOUBLE) AS coding_hours",
            "CAST(ai_suggestion_acceptance_rate AS DOUBLE) AS ai_acceptance_rate",
            "CAST(session_frequency AS INT) AS session_frequency",
            "geo",
        ],
        "expect_drop": {"valid_user": "user_id IS NOT NULL"},
        "expect_keep": {
            "valid_hours": "coding_hours BETWEEN 0 AND 24",
            "valid_accept": "ai_acceptance_rate BETWEEN 0 AND 1",
        },
    },
    {
        "name": "feature_adoption",
        "format": "parquet",
        "select": [
            "CAST(month_start AS DATE) AS month_start",
            "CAST(user_id AS STRING) AS user_id",
            "CAST(feature_key AS STRING) AS feature_key",
            "CAST(feature_name AS STRING) AS feature_name",
            "CAST(feature_family AS STRING) AS feature_family",
            "CAST(is_adopted AS BOOLEAN) AS is_adopted",
            "CAST(first_activation_date AS DATE) AS first_activation_date",
            "CAST(activation_count AS BIGINT) AS activation_count",
            "CAST(active_days AS BIGINT) AS active_days",
            "CAST(depth_score AS DOUBLE) AS depth_score",
        ],
        "expect_drop": {"valid_user": "user_id IS NOT NULL"},
        "expect_keep": {
            "valid_depth": "depth_score BETWEEN 0 AND 1",
            "valid_active_days": "active_days >= 0",
        },
    },
    {
        "name": "support_tickets",
        "format": "parquet",
        "select": [
            "CAST(ticket_id AS STRING) AS ticket_id",
            "CAST(user_id AS STRING) AS user_id",
            "CAST(created_date AS DATE) AS created_date",
            "CAST(channel AS STRING) AS channel",
            "CAST(category AS STRING) AS category",
            "CAST(priority AS STRING) AS priority",
            "CAST(chat_message_count AS BIGINT) AS chat_message_count",
            "CAST(first_response_minutes AS BIGINT) AS first_response_minutes",
            "CAST(resolution_hours AS DOUBLE) AS resolution_hours",
            "CAST(reopened_count AS BIGINT) AS reopened_count",
            "CAST(is_escalated AS BOOLEAN) AS is_escalated",
            "CAST(csat_score AS DOUBLE) AS csat_score",
            "CAST(resolved AS BOOLEAN) AS resolved",
        ],
        "expect_drop": {"valid_ticket": "ticket_id IS NOT NULL"},
        # csat_score is nullable (no response) — a NULL predicate is not FALSE, so
        # unanswered tickets pass rather than getting flagged.
        "expect_keep": {
            "valid_csat": "csat_score BETWEEN 1 AND 5",
            "valid_resolution": "resolution_hours >= 0",
        },
    },
    {
        "name": "crm_campaigns",
        "format": "parquet",
        "select": [
            "CAST(campaign_id AS STRING) AS campaign_id",
            "CAST(campaign_name AS STRING) AS campaign_name",
            "CAST(objective AS STRING) AS objective",
            "CAST(channel AS STRING) AS channel",
            "CAST(target_segment AS STRING) AS target_segment",
            "CAST(offer_type AS STRING) AS offer_type",
            "CAST(budget_usd AS DOUBLE) AS budget_usd",
            "CAST(start_date AS DATE) AS start_date",
            "CAST(end_date AS DATE) AS end_date",
            "CAST(is_active_at_window_end AS BOOLEAN) AS is_active_at_window_end",
        ],
        "expect_drop": {"valid_campaign": "campaign_id IS NOT NULL"},
        "expect_keep": {
            "valid_budget": "budget_usd >= 0",
            "valid_objective": "objective IN ('retention','winback','adoption','expansion')",
        },
    },
    {
        "name": "crm_touches",
        "format": "parquet",
        "select": [
            "CAST(touch_id AS STRING) AS touch_id",
            "CAST(campaign_id AS STRING) AS campaign_id",
            "CAST(user_id AS STRING) AS user_id",
            "CAST(touch_date AS DATE) AS touch_date",
            "CAST(channel AS STRING) AS channel",
            "CAST(message_variant AS STRING) AS message_variant",
            "CAST(delivered AS BOOLEAN) AS delivered",
            "CAST(opened AS BOOLEAN) AS opened",
            "CAST(clicked AS BOOLEAN) AS clicked",
            "CAST(outcome AS STRING) AS outcome",
            "CAST(reactivated AS BOOLEAN) AS reactivated",
            "CAST(user_state_at_touch AS STRING) AS user_state_at_touch",
            "CAST(cost_usd AS DOUBLE) AS cost_usd",
        ],
        "expect_drop": {"valid_touch": "touch_id IS NOT NULL"},
        "expect_keep": {
            "valid_outcome": "outcome IN ('reactivated','engaged_no_conversion','no_response','unsubscribed')",
            "valid_cost": "cost_usd >= 0",
        },
    },
    {
        # Derived/gold label. In a real build this would be a batch materialized
        # view over silver, not an Auto Loader stream; here it lands in the same
        # Volume as parquet, so the uniform file pattern ingests it too.
        "name": "churn_labels",
        "format": "parquet",
        "select": [
            "CAST(month_start AS DATE) AS month_start",
            "CAST(user_id AS STRING) AS user_id",
            "CAST(geo AS STRING) AS geo",
            "CAST(churned AS BOOLEAN) AS churned",
            "CAST(churn_date AS DATE) AS churn_date",
            "CAST(tenure_months AS BIGINT) AS tenure_months",
            "CAST(is_power_user_month AS BOOLEAN) AS is_power_user_month",
            "CAST(active_days AS BIGINT) AS active_days",
            "CAST(avg_coding_hours AS DOUBLE) AS avg_coding_hours",
            "CAST(avg_acceptance_rate AS DOUBLE) AS avg_acceptance_rate",
            "CAST(avg_session_frequency AS DOUBLE) AS avg_session_frequency",
            "CAST(coding_hours_trend_30d AS DOUBLE) AS coding_hours_trend_30d",
            "CAST(support_tickets_30d AS BIGINT) AS support_tickets_30d",
            "CAST(features_adopted AS BIGINT) AS features_adopted",
            "CAST(crm_touches_30d AS BIGINT) AS crm_touches_30d",
        ],
        "expect_drop": {"valid_user": "user_id IS NOT NULL"},
        "expect_keep": {"valid_tenure": "tenure_months >= 0"},
    },
]
