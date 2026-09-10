"""Metadata for the metadata-driven ingestion pipeline.

One dict per source table. `md_transformation.py` loops over ``TABLES`` and
generates a bronze (Auto Loader) + silver (typed, quality-checked, GOVERNED) pair
for each, so adding a source is a config entry here rather than new code.

Per-entry keys:
  name         target table stem -> dev_churn.bronze.<name>_raw / dev_churn.silver.<name>
  format       Auto Loader file format in the landing Volume (parquet here)
  comment      silver TABLE comment (governance: what the table is)
  columns      silver projection as {expr, name, type, comment}: expr is the CAST,
               name the output column, type its SQL type, comment the UC column
               comment. md_transformation builds a schema DDL (name TYPE COMMENT ...)
               from these so the column comments are set by the owning pipeline
               (DataFrame column metadata does NOT propagate to a Lakeflow streaming
               table's UC comments; an explicit schema does).
  expect_drop  expectations that DROP violating rows (unusable records)
  expect_keep  expectations that only RECORD violations as metrics (rows kept)

Governance is embedded here (per-stage model) rather than ALTER-ed onto the
Lakeflow-owned tables afterward. Casts, types and comments are derived from
`src/datagen/schemas.py`, the generator's single source of truth. This pipeline
owns `usage_events` too: the standalone `usage_events_ingest` pipeline is retired.
"""

TABLES = [
    {
        "name": "users",
        "format": "parquet",
        "comment": "The Pro-tier user dimension: signup, geography, persona and the power-user flag derived from observed daily engagement.",
        "columns": [
            {"expr": "CAST(user_id AS STRING)", "name": "user_id", "type": "STRING", "comment": "Synthetic surrogate user key, `USR-########`."},
            {"expr": "CAST(signup_date AS DATE)", "name": "signup_date", "type": "DATE", "comment": "Date the user first became a Pro subscriber."},
            {"expr": "CAST(geo AS STRING)", "name": "geo", "type": "STRING", "comment": "Region code: NA, EMEA, APAC, LATAM, MEA, ANZ."},
            {"expr": "CAST(country AS STRING)", "name": "country", "type": "STRING", "comment": "ISO-3166 alpha-2 country within the region."},
            {"expr": "CAST(plan AS STRING)", "name": "plan", "type": "STRING", "comment": "Plan at signup (see `subscriptions.plan_id`)."},
            {"expr": "CAST(tier AS STRING)", "name": "tier", "type": "STRING", "comment": "Subscription tier; always `pro` in this dataset."},
            {"expr": "CAST(persona AS STRING)", "name": "persona", "type": "STRING", "comment": "Value-add persona label for CRM targeting."},
            {"expr": "CAST(company_size AS STRING)", "name": "company_size", "type": "STRING", "comment": "Self-reported company-size bucket."},
            {"expr": "CAST(acquisition_channel AS STRING)", "name": "acquisition_channel", "type": "STRING", "comment": "How the user was acquired."},
            {"expr": "CAST(primary_language AS STRING)", "name": "primary_language", "type": "STRING", "comment": "Most-used programming language."},
            {"expr": "CAST(ide_theme AS STRING)", "name": "ide_theme", "type": "STRING", "comment": "Cosmetic preference; a deliberate non-signal."},
            {"expr": "CAST(power_user_flag AS BOOLEAN)", "name": "power_user_flag", "type": "BOOLEAN", "comment": "TRUE for SUSTAINED power users. A week qualifies when the user hit >=4 coding hours/day on >=5 days; a month qualifies when it contains a qualifying week. The flag is TRUE when qualifying months are at least half of the months the user was active, over >=2 active months. Note this is stricter than 'ever qualified once' (which would flag ~37% of an 18-month population, including now-dormant users). Recomputable from usage_events."},
            {"expr": "CAST(tenure_days_at_window_end AS BIGINT)", "name": "tenure_days_at_window_end", "type": "BIGINT", "comment": "Days from signup to the end of the observation window."},
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
        "comment": "Subscription lifecycle and billing history: signup, renewals, downgrades and cancellation, with recognised revenue per term.",
        "columns": [
            {"expr": "CAST(subscription_id AS STRING)", "name": "subscription_id", "type": "STRING", "comment": "Surrogate key, `SUB-#########`."},
            {"expr": "CAST(user_id AS STRING)", "name": "user_id", "type": "STRING", "comment": "FK to `users.user_id`."},
            {"expr": "CAST(plan_id AS STRING)", "name": "plan_id", "type": "STRING", "comment": "Plan held during this term."},
            {"expr": "CAST(plan_name AS STRING)", "name": "plan_name", "type": "STRING", "comment": "Human-readable plan name."},
            {"expr": "CAST(tier AS STRING)", "name": "tier", "type": "STRING", "comment": "Tier of the plan held (`pro`)."},
            {"expr": "CAST(billing_period AS STRING)", "name": "billing_period", "type": "STRING", "comment": "`monthly` or `annual`."},
            {"expr": "CAST(mrr_usd AS DOUBLE)", "name": "mrr_usd", "type": "DOUBLE", "comment": "Monthly recurring revenue for this term."},
            {"expr": "CAST(list_price_usd AS DOUBLE)", "name": "list_price_usd", "type": "DOUBLE", "comment": "Sticker price per billing period."},
            {"expr": "CAST(term_start_date AS DATE)", "name": "term_start_date", "type": "DATE", "comment": "First day the user held this plan."},
            {"expr": "CAST(term_end_date AS DATE)", "name": "term_end_date", "type": "DATE", "comment": "Last day of the term; NULL while the term is still open."},
            {"expr": "CAST(term_index AS BIGINT)", "name": "term_index", "type": "BIGINT", "comment": "0-based sequence of terms for the user."},
            {"expr": "CAST(status AS STRING)", "name": "status", "type": "STRING", "comment": "`active`, `downgraded`, `canceled`, or `churned_after_reactivation`."},
            {"expr": "CAST(renewals_count AS BIGINT)", "name": "renewals_count", "type": "BIGINT", "comment": "Successful renewals billed in this term."},
            {"expr": "CAST(payment_failures AS BIGINT)", "name": "payment_failures", "type": "BIGINT", "comment": "Failed payment attempts in this term."},
            {"expr": "CAST(is_downgrade AS BOOLEAN)", "name": "is_downgrade", "type": "BOOLEAN", "comment": "TRUE if this term began as a downgrade."},
            {"expr": "CAST(is_reactivation AS BOOLEAN)", "name": "is_reactivation", "type": "BOOLEAN", "comment": "TRUE if this term began as a winback."},
            {"expr": "CAST(cancel_date AS DATE)", "name": "cancel_date", "type": "DATE", "comment": "Date the subscription was canceled; NULL if not canceled."},
            {"expr": "CAST(cancel_reason AS STRING)", "name": "cancel_reason", "type": "STRING", "comment": "Reason code for cancellation; NULL if not canceled."},
            {"expr": "CAST(revenue_usd AS DOUBLE)", "name": "revenue_usd", "type": "DOUBLE", "comment": "Revenue recognised over the term."},
        ],
        "expect_drop": {"valid_subscription": "subscription_id IS NOT NULL"},
        "expect_keep": {
            "valid_mrr": "mrr_usd >= 0",
            "valid_billing": "billing_period IN ('monthly','annual')",
        },
    },
    {
        "name": "feature_adoption",
        "format": "parquet",
        "comment": "Monthly adoption and activation intensity for the stickiness features. Adoption suppresses churn hazard, so this is a first-class model input.",
        "columns": [
            {"expr": "CAST(month_start AS DATE)", "name": "month_start", "type": "DATE", "comment": "First day of the calendar month."},
            {"expr": "CAST(user_id AS STRING)", "name": "user_id", "type": "STRING", "comment": "FK to `users.user_id`."},
            {"expr": "CAST(feature_key AS STRING)", "name": "feature_key", "type": "STRING", "comment": "Stable feature identifier."},
            {"expr": "CAST(feature_name AS STRING)", "name": "feature_name", "type": "STRING", "comment": "Human-readable feature name."},
            {"expr": "CAST(feature_family AS STRING)", "name": "feature_family", "type": "STRING", "comment": "Feature grouping for rollups."},
            {"expr": "CAST(is_adopted AS BOOLEAN)", "name": "is_adopted", "type": "BOOLEAN", "comment": "TRUE if the user had activated it by then."},
            {"expr": "CAST(first_activation_date AS DATE)", "name": "first_activation_date", "type": "DATE", "comment": "Date of first activation; NULL if never adopted."},
            {"expr": "CAST(activation_count AS BIGINT)", "name": "activation_count", "type": "BIGINT", "comment": "Times the feature was used that month."},
            {"expr": "CAST(active_days AS BIGINT)", "name": "active_days", "type": "BIGINT", "comment": "Days that month the feature was used."},
            {"expr": "CAST(depth_score AS DOUBLE)", "name": "depth_score", "type": "DOUBLE", "comment": "0-1 usage depth: how heavily the feature was used when available."},
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
        "comment": "Support friction as a churn signal: ticket volume, chat message volume, handling time and CSAT. Volume rises as engagement declines.",
        "columns": [
            {"expr": "CAST(ticket_id AS STRING)", "name": "ticket_id", "type": "STRING", "comment": "Surrogate key, `TCK-#########`."},
            {"expr": "CAST(user_id AS STRING)", "name": "user_id", "type": "STRING", "comment": "FK to `users.user_id`."},
            {"expr": "CAST(created_date AS DATE)", "name": "created_date", "type": "DATE", "comment": "Date the ticket was opened."},
            {"expr": "CAST(channel AS STRING)", "name": "channel", "type": "STRING", "comment": "Contact channel used."},
            {"expr": "CAST(category AS STRING)", "name": "category", "type": "STRING", "comment": "Issue category."},
            {"expr": "CAST(priority AS STRING)", "name": "priority", "type": "STRING", "comment": "Triaged priority, `P0_urgent`..`P3_low`."},
            {"expr": "CAST(chat_message_count AS BIGINT)", "name": "chat_message_count", "type": "BIGINT", "comment": "Messages exchanged on the ticket."},
            {"expr": "CAST(first_response_minutes AS BIGINT)", "name": "first_response_minutes", "type": "BIGINT", "comment": "Minutes to first agent reply."},
            {"expr": "CAST(resolution_hours AS DOUBLE)", "name": "resolution_hours", "type": "DOUBLE", "comment": "Hours from open to resolution."},
            {"expr": "CAST(reopened_count AS BIGINT)", "name": "reopened_count", "type": "BIGINT", "comment": "Times the ticket was reopened."},
            {"expr": "CAST(is_escalated AS BOOLEAN)", "name": "is_escalated", "type": "BOOLEAN", "comment": "TRUE if escalated beyond tier-1 support."},
            {"expr": "CAST(csat_score AS DOUBLE)", "name": "csat_score", "type": "DOUBLE", "comment": "1-5 satisfaction score; NULL when the user did not respond."},
            {"expr": "CAST(resolved AS BOOLEAN)", "name": "resolved", "type": "BOOLEAN", "comment": "TRUE if the ticket reached a resolved state."},
        ],
        "expect_drop": {"valid_ticket": "ticket_id IS NOT NULL"},
        "expect_keep": {
            "valid_csat": "csat_score IS NULL OR csat_score BETWEEN 1 AND 5",
            "valid_resolution": "resolution_hours >= 0",
        },
    },
    {
        "name": "crm_campaigns",
        "format": "parquet",
        "comment": "Campaign dimension: objective, channel, target segment, budget, run dates.",
        "columns": [
            {"expr": "CAST(campaign_id AS STRING)", "name": "campaign_id", "type": "STRING", "comment": "Campaign key, `CMP-###`."},
            {"expr": "CAST(campaign_name AS STRING)", "name": "campaign_name", "type": "STRING", "comment": "Human-readable campaign name."},
            {"expr": "CAST(objective AS STRING)", "name": "objective", "type": "STRING", "comment": "`retention`, `winback`, `adoption` or `expansion`."},
            {"expr": "CAST(channel AS STRING)", "name": "channel", "type": "STRING", "comment": "`email`, `in_app` or `push`."},
            {"expr": "CAST(target_segment AS STRING)", "name": "target_segment", "type": "STRING", "comment": "Rule describing who is eligible."},
            {"expr": "CAST(offer_type AS STRING)", "name": "offer_type", "type": "STRING", "comment": "What the touch offers the user."},
            {"expr": "CAST(budget_usd AS DOUBLE)", "name": "budget_usd", "type": "DOUBLE", "comment": "Planned campaign budget."},
            {"expr": "CAST(start_date AS DATE)", "name": "start_date", "type": "DATE", "comment": "First day the campaign was live."},
            {"expr": "CAST(end_date AS DATE)", "name": "end_date", "type": "DATE", "comment": "Last day the campaign was live."},
            {"expr": "CAST(is_active_at_window_end AS BOOLEAN)", "name": "is_active_at_window_end", "type": "BOOLEAN", "comment": "TRUE if still live on the last day."},
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
        "comment": "Individual campaign sends and their outcome. `outcome = 'reactivated'` is the numerator of the CRM reactivation-rate KPI.",
        "columns": [
            {"expr": "CAST(touch_id AS STRING)", "name": "touch_id", "type": "STRING", "comment": "Surrogate key, `TCH-##########`."},
            {"expr": "CAST(campaign_id AS STRING)", "name": "campaign_id", "type": "STRING", "comment": "FK to `crm_campaigns.campaign_id`."},
            {"expr": "CAST(user_id AS STRING)", "name": "user_id", "type": "STRING", "comment": "FK to `users.user_id`."},
            {"expr": "CAST(touch_date AS DATE)", "name": "touch_date", "type": "DATE", "comment": "Date the touch was sent."},
            {"expr": "CAST(channel AS STRING)", "name": "channel", "type": "STRING", "comment": "Channel the touch went out on."},
            {"expr": "CAST(message_variant AS STRING)", "name": "message_variant", "type": "STRING", "comment": "A/B/C message variant."},
            {"expr": "CAST(delivered AS BOOLEAN)", "name": "delivered", "type": "BOOLEAN", "comment": "TRUE if the touch was delivered."},
            {"expr": "CAST(opened AS BOOLEAN)", "name": "opened", "type": "BOOLEAN", "comment": "TRUE if the user opened it."},
            {"expr": "CAST(clicked AS BOOLEAN)", "name": "clicked", "type": "BOOLEAN", "comment": "TRUE if the user clicked through."},
            {"expr": "CAST(outcome AS STRING)", "name": "outcome", "type": "STRING", "comment": "`reactivated`, `engaged_no_conversion`, `no_response` or `unsubscribed`."},
            {"expr": "CAST(reactivated AS BOOLEAN)", "name": "reactivated", "type": "BOOLEAN", "comment": "Convenience flag: outcome == 'reactivated'."},
            {"expr": "CAST(user_state_at_touch AS STRING)", "name": "user_state_at_touch", "type": "STRING", "comment": "`active`, `at_risk` or `lapsed` when the touch was sent."},
            {"expr": "CAST(cost_usd AS DOUBLE)", "name": "cost_usd", "type": "DOUBLE", "comment": "Marginal cost of the touch."},
        ],
        "expect_drop": {"valid_touch": "touch_id IS NOT NULL"},
        "expect_keep": {
            "valid_outcome": "outcome IN ('reactivated','engaged_no_conversion','no_response','unsubscribed')",
            "valid_cost": "cost_usd >= 0",
        },
    },
    {
        "name": "churn_labels",
        "format": "parquet",
        "comment": "Per-user monthly churn label. `churned = TRUE` means the user was an active subscriber on the first day of the month and canceled during it. Rows only exist for months the user was at risk, so AVG(churned) is the monthly churn rate directly.",
        "columns": [
            {"expr": "CAST(month_start AS DATE)", "name": "month_start", "type": "DATE", "comment": "First day of the observation month."},
            {"expr": "CAST(user_id AS STRING)", "name": "user_id", "type": "STRING", "comment": "FK to `users.user_id`."},
            {"expr": "CAST(geo AS STRING)", "name": "geo", "type": "STRING", "comment": "Denormalised region code."},
            {"expr": "CAST(churned AS BOOLEAN)", "name": "churned", "type": "BOOLEAN", "comment": "THE LABEL: TRUE if the user canceled during this month."},
            {"expr": "CAST(churn_date AS DATE)", "name": "churn_date", "type": "DATE", "comment": "Cancellation date when churned; NULL otherwise."},
            {"expr": "CAST(tenure_months AS BIGINT)", "name": "tenure_months", "type": "BIGINT", "comment": "Whole months from signup to month start."},
            {"expr": "CAST(is_power_user_month AS BOOLEAN)", "name": "is_power_user_month", "type": "BOOLEAN", "comment": "TRUE if the power-user bar was met."},
            {"expr": "CAST(active_days AS BIGINT)", "name": "active_days", "type": "BIGINT", "comment": "Active days observed that month."},
            {"expr": "CAST(avg_coding_hours AS DOUBLE)", "name": "avg_coding_hours", "type": "DOUBLE", "comment": "Mean coding hours over active days."},
            {"expr": "CAST(avg_acceptance_rate AS DOUBLE)", "name": "avg_acceptance_rate", "type": "DOUBLE", "comment": "Mean AI-acceptance over active days."},
            {"expr": "CAST(avg_session_frequency AS DOUBLE)", "name": "avg_session_frequency", "type": "DOUBLE", "comment": "Mean sessions/day over active days."},
            {"expr": "CAST(coding_hours_trend_30d AS DOUBLE)", "name": "coding_hours_trend_30d", "type": "DOUBLE", "comment": "Ratio of this month's mean coding hours to the prior month's (1.0 = flat, <1 = declining). The headline decline feature."},
            {"expr": "CAST(support_tickets_30d AS BIGINT)", "name": "support_tickets_30d", "type": "BIGINT", "comment": "Tickets opened during the month."},
            {"expr": "CAST(features_adopted AS BIGINT)", "name": "features_adopted", "type": "BIGINT", "comment": "Distinct stickiness features adopted."},
            {"expr": "CAST(crm_touches_30d AS BIGINT)", "name": "crm_touches_30d", "type": "BIGINT", "comment": "CRM touches received during the month."},
        ],
        "expect_drop": {"valid_user": "user_id IS NOT NULL"},
        "expect_keep": {
            "valid_tenure": "tenure_months >= 0",
        },
    },
    {
        # usage_events: curated serving columns; kept identical to the
        # already-materialised dev_churn.silver.usage_events.
        "name": "usage_events",
        "format": "parquet",
        "comment": "The daily behavioural signal and the Structured Streaming / Lakeflow ingest source: active coding hours, AI-suggestion acceptance rate and session frequency. Only active days are emitted, so row count is well below users x days.",
        "columns": [
            {"expr": "CAST(user_id AS STRING)", "name": "user_id", "type": "STRING", "comment": "FK to `users.user_id`."},
            {"expr": "CAST(event_date AS DATE)", "name": "event_date", "type": "DATE", "comment": "Activity date (partition column)."},
            {"expr": "CAST(coding_hours AS DOUBLE)", "name": "coding_hours", "type": "DOUBLE", "comment": "Active coding hours that day (editor-focused time), 0.05-16."},
            {"expr": "CAST(ai_suggestion_acceptance_rate AS DOUBLE)", "name": "ai_acceptance_rate", "type": "DOUBLE", "comment": "Accepted AI suggestions / suggestions shown that day, 0-1."},
            {"expr": "CAST(session_frequency AS INT)", "name": "session_frequency", "type": "INT", "comment": "Distinct editor sessions started that day."},
            {"expr": "CAST(geo AS STRING)", "name": "geo", "type": "STRING", "comment": "Denormalised region code for partition pruning."},
        ],
        "expect_drop": {"valid_user": "user_id IS NOT NULL"},
        "expect_keep": {
            "valid_hours": "coding_hours BETWEEN 0 AND 24",
            "valid_accept": "ai_acceptance_rate BETWEEN 0 AND 1",
        },
    },
]
