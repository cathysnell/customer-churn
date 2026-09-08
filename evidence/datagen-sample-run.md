# Stage 0 — Synthetic dataset generation: execution evidence

> **Synthetic data only. Zero real customer data.** Every value in this
> document was produced by `src/datagen` from committed code and the
> committed random seed **1729**. Nothing here derives from a real
> company, user, or telemetry stream.

This file is **text execution evidence** for the dataset-generation stage:
it records the exact command that ran, the resulting schema, row counts,
`head()` previews and summary statistics. Regenerating with the same seed
reproduces it byte-for-byte (see the checksums at the end).

**Command that produced this file**

```console
$ python -m datagen --sample-frac 0.004 --months 18 --out data/sample --format parquet --no-partitions --verify-reproducible --evidence evidence/datagen-sample-run.md
```

## 1. Run configuration

| Knob | Value |
| --- | --- |
| seed | `1729` |
| users_requested | `50000` |
| sample_frac | `0.004` |
| users_effective | `200` |
| months | `18` |
| window_start | `2025-03-01` |
| window_end | `2026-08-31` |
| days | `549` |
| target_monthly_churn_rate | `0.047` |
| target_reactivation_rate | `0.08` |
| power_user_bar | `>=4.0 coding hours/day on >=5 days/week` |
| campaigns | `5` |
| output_format | `parquet` |
| partitioned | `False` |
| out_dir | `data/sample` |

Hazard calibration: intercept **-2.20312** found in
**10** bisection steps, giving a realised
monthly churn rate of **0.046965**
(4.6965%) against the configured
target of **0.047000** (4.7000%).

## 2. Row counts

| Table | Data asset | Layer | Rows | Grain |
| --- | --- | --- | --- | --- |
| `users` | VA (identity / persona / entitlements) | bronze | 200 | one row per Pro-tier user |
| `subscriptions` | A03 — subscription plans & billing history | bronze | 220 | one row per subscription term (a plan a user held for a period) |
| `usage_events` | A06 — raw product usage events & telemetry | bronze | 43,514 | one row per user per ACTIVE day (inactive days are not emitted) |
| `feature_adoption` | A07 — feature adoption & activation metrics | bronze | 13,620 | one row per user per feature per month |
| `support_tickets` | A14 — support tickets, chat logs & CSAT | bronze | 223 | one row per support ticket |
| `crm_campaigns` | VA (marketing saturation / campaign metadata) | bronze | 5 | one row per CRM campaign |
| `crm_touches` | VA (CRM touch + reactivation outcome) | bronze | 1,098 | one row per campaign touch sent to a user |
| `churn_labels` | derived label (gold) — supervised training target | gold | 2,257 | one row per user per month the user was a subscriber at month start |
| **TOTAL** | | | **61,137** | |

## 3. Headline KPIs realised in the generated data

All targets below are the **illustrative** baselines from
`docs/project-brief.md` — chosen for this demo, not real Anysphere figures.

Every rate is shown as the explicit fraction that produces it, so the
arithmetic is checkable rather than asserted.

| KPI | Target (illustrative) | Realised in this run | Numerator / denominator |
| --- | --- | --- | --- |
| Pro monthly churn rate | 4.70% | **4.6965%** (`0.046965`) | 106 churn events / 2,257 at-risk user-months |
| CRM winback reactivation rate | 8.00% | **8.0745%** (`0.080745`) | 13 reactivated / 161 delivered winback touches |
| Power-user share (sustained: >=4 hrs/day on >=5 days/wk, in >=50% of >=2 active months) | segment definition | **29.5000%** | 59 flagged / 200 users |
| Users who churned at least once in the window | — | **48.5000%** | over 200 users |
| `usage_events` density (rows / (users x days)) | active days only | **39.6302%** | 43,514 rows / (200 x 549) |

## 4. Data dictionary / schema printout

Rendered directly from `src/datagen/schemas.py`, which is the single
source of truth: the generator refuses to emit a frame that does not
match these columns and dtypes (`datagen.pipeline.conform`). The SQL
types are Databricks types, and the same specs generate the Unity
Catalog DDL at `_unity_catalog.sql` (target
`dev_behavior.bronze` for bronze, `dev_behavior.gold`
for gold).

### `users`

- **Data asset:** VA (identity / persona / entitlements)
- **Medallion layer:** bronze
- **Grain:** one row per Pro-tier user
- **Primary key:** `user_id`
- **Foreign keys:** —
- **Partitioned by:** `geo`

The Pro-tier user dimension: signup, geography, persona and the power-user flag derived from observed daily engagement.

| Column | pandas dtype | Databricks type | Nullable | Description |
| --- | --- | --- | --- | --- |
| `user_id` | `string` | `STRING` | no | Synthetic surrogate user key, `USR-########`. |
| `signup_date` | `date` | `DATE` | no | Date the user first became a Pro subscriber. |
| `geo` | `string` | `STRING` | no | Region code: NA, EMEA, APAC, LATAM, MEA, ANZ. |
| `country` | `string` | `STRING` | no | ISO-3166 alpha-2 country within the region. |
| `plan` | `string` | `STRING` | no | Plan at signup (see `subscriptions.plan_id`). |
| `tier` | `string` | `STRING` | no | Subscription tier; always `pro` in this dataset. |
| `persona` | `string` | `STRING` | no | Value-add persona label for CRM targeting. |
| `company_size` | `string` | `STRING` | no | Self-reported company-size bucket. |
| `acquisition_channel` | `string` | `STRING` | no | How the user was acquired. |
| `primary_language` | `string` | `STRING` | no | Most-used programming language. |
| `ide_theme` | `string` | `STRING` | no | Cosmetic preference; a deliberate non-signal. |
| `power_user_flag` | `bool` | `BOOLEAN` | no | TRUE for SUSTAINED power users. A week qualifies when the user hit >=4 coding hours/day on >=5 days; a month qualifies when it contains a qualifying week. The flag is TRUE when qualifying months are at least half of the months the user was active, over >=2 active months. Note this is stricter than 'ever qualified once' (which would flag ~37% of an 18-month population, including now-dormant users). Recomputable from usage_events. |
| `tenure_days_at_window_end` | `int64` | `BIGINT` | no | Days from signup to the end of the observation window. |

### `subscriptions`

- **Data asset:** A03 — subscription plans & billing history
- **Medallion layer:** bronze
- **Grain:** one row per subscription term (a plan a user held for a period)
- **Primary key:** `subscription_id`
- **Foreign keys:** `user_id` → `users.user_id`
- **Partitioned by:** — (single file)

Subscription lifecycle and billing history: signup, renewals, downgrades and cancellation, with recognised revenue per term.

| Column | pandas dtype | Databricks type | Nullable | Description |
| --- | --- | --- | --- | --- |
| `subscription_id` | `string` | `STRING` | no | Surrogate key, `SUB-#########`. |
| `user_id` | `string` | `STRING` | no | FK to `users.user_id`. |
| `plan_id` | `string` | `STRING` | no | Plan held during this term. |
| `plan_name` | `string` | `STRING` | no | Human-readable plan name. |
| `tier` | `string` | `STRING` | no | Tier of the plan held (`pro`). |
| `billing_period` | `string` | `STRING` | no | `monthly` or `annual`. |
| `mrr_usd` | `float64` | `DOUBLE` | no | Monthly recurring revenue for this term. |
| `list_price_usd` | `float64` | `DOUBLE` | no | Sticker price per billing period. |
| `term_start_date` | `date` | `DATE` | no | First day the user held this plan. |
| `term_end_date` | `date` | `DATE` | yes | Last day of the term; NULL while the term is still open. |
| `term_index` | `int64` | `BIGINT` | no | 0-based sequence of terms for the user. |
| `status` | `string` | `STRING` | no | `active`, `downgraded`, `canceled`, or `churned_after_reactivation`. |
| `renewals_count` | `int64` | `BIGINT` | no | Successful renewals billed in this term. |
| `payment_failures` | `int64` | `BIGINT` | no | Failed payment attempts in this term. |
| `is_downgrade` | `bool` | `BOOLEAN` | no | TRUE if this term began as a downgrade. |
| `is_reactivation` | `bool` | `BOOLEAN` | no | TRUE if this term began as a winback. |
| `cancel_date` | `date` | `DATE` | yes | Date the subscription was canceled; NULL if not canceled. |
| `cancel_reason` | `string` | `STRING` | yes | Reason code for cancellation; NULL if not canceled. |
| `revenue_usd` | `float64` | `DOUBLE` | no | Revenue recognised over the term. |

### `usage_events`

- **Data asset:** A06 — raw product usage events & telemetry
- **Medallion layer:** bronze
- **Grain:** one row per user per ACTIVE day (inactive days are not emitted)
- **Primary key:** `user_id`, `event_date`
- **Foreign keys:** `user_id` → `users.user_id`
- **Partitioned by:** `event_date`

The daily behavioural signal and the Structured Streaming / Lakeflow ingest source: active coding hours, AI-suggestion acceptance rate and session frequency. Only active days are emitted, so row count is well below users x days.

| Column | pandas dtype | Databricks type | Nullable | Description |
| --- | --- | --- | --- | --- |
| `event_date` | `date` | `DATE` | no | Activity date (partition column). |
| `user_id` | `string` | `STRING` | no | FK to `users.user_id`. |
| `geo` | `string` | `STRING` | no | Denormalised region code for partition pruning. |
| `coding_hours` | `float64` | `DOUBLE` | no | Active coding hours that day (editor-focused time), 0.05-16. |
| `ai_suggestion_acceptance_rate` | `float64` | `DOUBLE` | no | Accepted AI suggestions / suggestions shown that day, 0-1. |
| `session_frequency` | `int64` | `BIGINT` | no | Distinct editor sessions started that day. |
| `suggestions_shown` | `int64` | `BIGINT` | no | AI suggestions surfaced that day. |
| `suggestions_accepted` | `int64` | `BIGINT` | no | AI suggestions accepted that day. |
| `lines_of_code_written` | `int64` | `BIGINT` | no | Net lines written that day. |
| `files_touched` | `int64` | `BIGINT` | no | Distinct files edited that day. |
| `ai_requests` | `int64` | `BIGINT` | no | Chat / agent requests issued that day. |
| `is_weekend` | `bool` | `BOOLEAN` | no | TRUE for Saturday/Sunday activity. |

### `feature_adoption`

- **Data asset:** A07 — feature adoption & activation metrics
- **Medallion layer:** bronze
- **Grain:** one row per user per feature per month
- **Primary key:** `user_id`, `feature_key`, `month_start`
- **Foreign keys:** `user_id` → `users.user_id`
- **Partitioned by:** `month_start`

Monthly adoption and activation intensity for the stickiness features. Adoption suppresses churn hazard, so this is a first-class model input.

| Column | pandas dtype | Databricks type | Nullable | Description |
| --- | --- | --- | --- | --- |
| `month_start` | `date` | `DATE` | no | First day of the calendar month. |
| `user_id` | `string` | `STRING` | no | FK to `users.user_id`. |
| `feature_key` | `string` | `STRING` | no | Stable feature identifier. |
| `feature_name` | `string` | `STRING` | no | Human-readable feature name. |
| `feature_family` | `string` | `STRING` | no | Feature grouping for rollups. |
| `is_adopted` | `bool` | `BOOLEAN` | no | TRUE if the user had activated it by then. |
| `first_activation_date` | `date` | `DATE` | yes | Date of first activation; NULL if never adopted. |
| `activation_count` | `int64` | `BIGINT` | no | Times the feature was used that month. |
| `active_days` | `int64` | `BIGINT` | no | Days that month the feature was used. |
| `depth_score` | `float64` | `DOUBLE` | no | 0-1 usage depth: how heavily the feature was used when available. |

### `support_tickets`

- **Data asset:** A14 — support tickets, chat logs & CSAT
- **Medallion layer:** bronze
- **Grain:** one row per support ticket
- **Primary key:** `ticket_id`
- **Foreign keys:** `user_id` → `users.user_id`
- **Partitioned by:** — (single file)

Support friction as a churn signal: ticket volume, chat message volume, handling time and CSAT. Volume rises as engagement declines.

| Column | pandas dtype | Databricks type | Nullable | Description |
| --- | --- | --- | --- | --- |
| `ticket_id` | `string` | `STRING` | no | Surrogate key, `TCK-#########`. |
| `user_id` | `string` | `STRING` | no | FK to `users.user_id`. |
| `created_date` | `date` | `DATE` | no | Date the ticket was opened. |
| `channel` | `string` | `STRING` | no | Contact channel used. |
| `category` | `string` | `STRING` | no | Issue category. |
| `priority` | `string` | `STRING` | no | Triaged priority, `P0_urgent`..`P3_low`. |
| `chat_message_count` | `int64` | `BIGINT` | no | Messages exchanged on the ticket. |
| `first_response_minutes` | `int64` | `BIGINT` | no | Minutes to first agent reply. |
| `resolution_hours` | `float64` | `DOUBLE` | no | Hours from open to resolution. |
| `reopened_count` | `int64` | `BIGINT` | no | Times the ticket was reopened. |
| `is_escalated` | `bool` | `BOOLEAN` | no | TRUE if escalated beyond tier-1 support. |
| `csat_score` | `float64` | `DOUBLE` | yes | 1-5 satisfaction score; NULL when the user did not respond. |
| `resolved` | `bool` | `BOOLEAN` | no | TRUE if the ticket reached a resolved state. |

### `crm_campaigns`

- **Data asset:** VA (marketing saturation / campaign metadata)
- **Medallion layer:** bronze
- **Grain:** one row per CRM campaign
- **Primary key:** `campaign_id`
- **Foreign keys:** —
- **Partitioned by:** — (single file)

Campaign dimension: objective, channel, target segment, budget, run dates.

| Column | pandas dtype | Databricks type | Nullable | Description |
| --- | --- | --- | --- | --- |
| `campaign_id` | `string` | `STRING` | no | Campaign key, `CMP-###`. |
| `campaign_name` | `string` | `STRING` | no | Human-readable campaign name. |
| `objective` | `string` | `STRING` | no | `retention`, `winback`, `adoption` or `expansion`. |
| `channel` | `string` | `STRING` | no | `email`, `in_app` or `push`. |
| `target_segment` | `string` | `STRING` | no | Rule describing who is eligible. |
| `offer_type` | `string` | `STRING` | no | What the touch offers the user. |
| `budget_usd` | `float64` | `DOUBLE` | no | Planned campaign budget. |
| `start_date` | `date` | `DATE` | no | First day the campaign was live. |
| `end_date` | `date` | `DATE` | no | Last day the campaign was live. |
| `is_active_at_window_end` | `bool` | `BOOLEAN` | no | TRUE if still live on the last day. |

### `crm_touches`

- **Data asset:** VA (CRM touch + reactivation outcome)
- **Medallion layer:** bronze
- **Grain:** one row per campaign touch sent to a user
- **Primary key:** `touch_id`
- **Foreign keys:** `user_id` → `users.user_id`, `campaign_id` → `crm_campaigns.campaign_id`
- **Partitioned by:** `touch_date`

Individual campaign sends and their outcome. `outcome = 'reactivated'` is the numerator of the CRM reactivation-rate KPI.

| Column | pandas dtype | Databricks type | Nullable | Description |
| --- | --- | --- | --- | --- |
| `touch_id` | `string` | `STRING` | no | Surrogate key, `TCH-##########`. |
| `campaign_id` | `string` | `STRING` | no | FK to `crm_campaigns.campaign_id`. |
| `user_id` | `string` | `STRING` | no | FK to `users.user_id`. |
| `touch_date` | `date` | `DATE` | no | Date the touch was sent. |
| `channel` | `string` | `STRING` | no | Channel the touch went out on. |
| `message_variant` | `string` | `STRING` | no | A/B/C message variant. |
| `delivered` | `bool` | `BOOLEAN` | no | TRUE if the touch was delivered. |
| `opened` | `bool` | `BOOLEAN` | no | TRUE if the user opened it. |
| `clicked` | `bool` | `BOOLEAN` | no | TRUE if the user clicked through. |
| `outcome` | `string` | `STRING` | no | `reactivated`, `engaged_no_conversion`, `no_response` or `unsubscribed`. |
| `reactivated` | `bool` | `BOOLEAN` | no | Convenience flag: outcome == 'reactivated'. |
| `user_state_at_touch` | `string` | `STRING` | no | `active`, `at_risk` or `lapsed` when the touch was sent. |
| `cost_usd` | `float64` | `DOUBLE` | no | Marginal cost of the touch. |

### `churn_labels`

- **Data asset:** derived label (gold) — supervised training target
- **Medallion layer:** gold
- **Grain:** one row per user per month the user was a subscriber at month start
- **Primary key:** `user_id`, `month_start`
- **Foreign keys:** `user_id` → `users.user_id`
- **Partitioned by:** `month_start`

Per-user monthly churn label. `churned = TRUE` means the user was an active subscriber on the first day of the month and canceled during it. Rows only exist for months the user was at risk, so AVG(churned) is the monthly churn rate directly.

| Column | pandas dtype | Databricks type | Nullable | Description |
| --- | --- | --- | --- | --- |
| `month_start` | `date` | `DATE` | no | First day of the observation month. |
| `user_id` | `string` | `STRING` | no | FK to `users.user_id`. |
| `geo` | `string` | `STRING` | no | Denormalised region code. |
| `churned` | `bool` | `BOOLEAN` | no | THE LABEL: TRUE if the user canceled during this month. |
| `churn_date` | `date` | `DATE` | yes | Cancellation date when churned; NULL otherwise. |
| `tenure_months` | `int64` | `BIGINT` | no | Whole months from signup to month start. |
| `is_power_user_month` | `bool` | `BOOLEAN` | no | TRUE if the power-user bar was met. |
| `active_days` | `int64` | `BIGINT` | no | Active days observed that month. |
| `avg_coding_hours` | `float64` | `DOUBLE` | no | Mean coding hours over active days. |
| `avg_acceptance_rate` | `float64` | `DOUBLE` | no | Mean AI-acceptance over active days. |
| `avg_session_frequency` | `float64` | `DOUBLE` | no | Mean sessions/day over active days. |
| `coding_hours_trend_30d` | `float64` | `DOUBLE` | no | Ratio of this month's mean coding hours to the prior month's (1.0 = flat, <1 = declining). The headline decline feature. |
| `support_tickets_30d` | `int64` | `BIGINT` | no | Tickets opened during the month. |
| `features_adopted` | `int64` | `BIGINT` | no | Distinct stickiness features adopted. |
| `crm_touches_30d` | `int64` | `BIGINT` | no | CRM touches received during the month. |

## 5. `head(5)` previews per table

Real rows from this run, printed with `DataFrame.head().to_string()`.

### `users` — 200 rows

```text
     user_id signup_date  geo country             plan tier         persona company_size acquisition_channel primary_language     ide_theme  power_user_flag  tenure_days_at_window_end
USR-00000001  2024-12-04 APAC      JP      pro_monthly  pro         student            1      organic_search       typescript          dark            False                        635
USR-00000002  2025-09-17 EMEA      FR pro_team_monthly  pro  individual_dev       51-200      organic_search       typescript         light             True                        348
USR-00000003  2024-10-17   NA      CA      pro_monthly  pro       team_lead        11-50      organic_search           python         light            False                        683
USR-00000004  2024-10-17 EMEA      SE       pro_annual  pro       team_lead         2-10      organic_search               go          dark            False                        683
USR-00000005  2025-08-06   NA      MX      pro_monthly  pro startup_founder        1000+         paid_search           python high_contrast             True                        390
```

<details><summary>dtypes</summary>

```text
user_id                              object
signup_date                  datetime64[ns]
geo                                  object
country                              object
plan                                 object
tier                                 object
persona                              object
company_size                         object
acquisition_channel                  object
primary_language                     object
ide_theme                            object
power_user_flag                        bool
tenure_days_at_window_end             int64
```

</details>

### `subscriptions` — 220 rows

```text
subscription_id      user_id          plan_id        plan_name tier billing_period  mrr_usd  list_price_usd term_start_date term_end_date  term_index   status  renewals_count  payment_failures  is_downgrade  is_reactivation cancel_date cancel_reason  revenue_usd
  SUB-000000001 USR-00000001      pro_monthly      Pro Monthly  pro        monthly     20.0            20.0      2024-12-04    2026-07-08           0 canceled              16                 0         False            False  2026-07-08 too_expensive       330.00
  SUB-000000002 USR-00000002 pro_team_monthly Pro Team Monthly  pro        monthly     40.0            40.0      2025-09-17           NaT           0   active              11                 0         False            False         NaT          None       465.33
  SUB-000000003 USR-00000003      pro_monthly      Pro Monthly  pro        monthly     20.0            20.0      2024-10-17    2025-08-03           0 canceled               5                 0         False            False  2025-08-03 stopped_using       104.00
  SUB-000000004 USR-00000004       pro_annual       Pro Annual  pro         annual     16.0           192.0      2024-10-17           NaT           0   active               1                 0         False            False         NaT          None       292.80
  SUB-000000005 USR-00000005      pro_monthly      Pro Monthly  pro        monthly     20.0            20.0      2025-08-06           NaT           0   active              13                 0         False            False         NaT          None       260.67
```

<details><summary>dtypes</summary>

```text
subscription_id             object
user_id                     object
plan_id                     object
plan_name                   object
tier                        object
billing_period              object
mrr_usd                    float64
list_price_usd             float64
term_start_date     datetime64[ns]
term_end_date       datetime64[ns]
term_index                   int64
status                      object
renewals_count               int64
payment_failures             int64
is_downgrade                  bool
is_reactivation               bool
cancel_date         datetime64[ns]
cancel_reason               object
revenue_usd                float64
```

</details>

### `usage_events` — 43,514 rows

```text
event_date      user_id  geo  coding_hours  ai_suggestion_acceptance_rate  session_frequency  suggestions_shown  suggestions_accepted  lines_of_code_written  files_touched  ai_requests  is_weekend
2025-03-01 USR-00000001 APAC         1.096                         0.3721                  5                 43                    16                     66              4            5        True
2025-03-01 USR-00000003   NA         4.204                         0.3429                  1                140                    48                    238             13           15        True
2025-03-01 USR-00000011 EMEA         3.844                         0.3733                  5                150                    56                    226             17           12        True
2025-03-01 USR-00000013   NA         2.334                         0.4384                  3                 73                    32                    176             10            4        True
2025-03-01 USR-00000017 EMEA         1.934                         0.3594                  1                 64                    23                    125             12            9        True
```

<details><summary>dtypes</summary>

```text
event_date                       datetime64[ns]
user_id                                  object
geo                                      object
coding_hours                            float64
ai_suggestion_acceptance_rate           float64
session_frequency                         int64
suggestions_shown                         int64
suggestions_accepted                      int64
lines_of_code_written                     int64
files_touched                             int64
ai_requests                               int64
is_weekend                                 bool
```

</details>

### `feature_adoption` — 13,620 rows

```text
month_start      user_id     feature_key             feature_name feature_family  is_adopted first_activation_date  activation_count  active_days  depth_score
 2025-03-01 USR-00000001      agent_mode Agentic Multi-Step Edits        agentic       False                   NaT                 0            0       0.0000
 2025-03-01 USR-00000001   codebase_chat      Codebase-Aware Chat        core_ai       False                   NaT                 0            0       0.0000
 2025-03-01 USR-00000001 multi_file_edit          Multi-File Edit        agentic       False                   NaT                 0            0       0.0000
 2025-03-01 USR-00000001   project_rules      Project Rules Files  customization       False                   NaT                 0            0       0.0000
 2025-03-01 USR-00000001  tab_completion    Inline Tab Completion        core_ai        True            2025-03-01               310           14       0.7778
```

<details><summary>dtypes</summary>

```text
month_start              datetime64[ns]
user_id                          object
feature_key                      object
feature_name                     object
feature_family                   object
is_adopted                         bool
first_activation_date    datetime64[ns]
activation_count                  int64
active_days                       int64
depth_score                     float64
```

</details>

### `support_tickets` — 223 rows

```text
    ticket_id      user_id created_date         channel           category  priority  chat_message_count  first_response_minutes  resolution_hours  reopened_count  is_escalated  csat_score  resolved
TCK-000000001 USR-00000149   2025-03-06           email    feature_request P2_normal                   7                     194              4.46               0         False         NaN      True
TCK-000000002 USR-00000093   2025-03-07           email suggestion_quality P2_normal                   7                     162             54.53               1         False         NaN      True
TCK-000000003 USR-00000158   2025-03-08     in_app_chat   indexing_failure    P3_low                   5                     495             93.06               0         False         4.0      True
TCK-000000004 USR-00000032   2025-03-17 community_forum suggestion_quality P2_normal                   5                     180             43.31               0         False         5.0      True
TCK-000000005 USR-00000026   2025-03-20     in_app_chat suggestion_quality   P1_high                   7                      33              4.23               0          True         NaN      True
```

<details><summary>dtypes</summary>

```text
ticket_id                         object
user_id                           object
created_date              datetime64[ns]
channel                           object
category                          object
priority                          object
chat_message_count                 int64
first_response_minutes             int64
resolution_hours                 float64
reopened_count                     int64
is_escalated                        bool
csat_score                       float64
resolved                            bool
```

</details>

### `crm_campaigns` — 5 rows

```text
campaign_id                  campaign_name objective channel                  target_segment                  offer_type  budget_usd start_date   end_date  is_active_at_window_end
    CMP-001       At-Risk Behavioral Nudge retention   email     declining_engagement_active           usage_tips_digest    180000.0 2025-03-01 2026-08-31                     True
    CMP-002 Power User Retention Concierge retention  in_app declining_engagement_power_user   dedicated_success_session    240000.0 2025-05-01 2026-08-31                     True
    CMP-003             Lapsed Pro Winback   winback   email               lapsed_within_90d        two_months_50pct_off    210000.0 2025-04-01 2026-08-31                     True
    CMP-004     Agent Mode Adoption Series  adoption  in_app     low_feature_adoption_active          guided_walkthrough    120000.0 2025-07-01 2026-08-31                     True
    CMP-005      Annual Plan Upgrade Offer expansion    push         engaged_monthly_billers annual_switch_2_months_free     95000.0 2025-09-01 2026-08-31                     True
```

<details><summary>dtypes</summary>

```text
campaign_id                        object
campaign_name                      object
objective                          object
channel                            object
target_segment                     object
offer_type                         object
budget_usd                        float64
start_date                 datetime64[ns]
end_date                   datetime64[ns]
is_active_at_window_end              bool
```

</details>

### `crm_touches` — 1,098 rows

```text
      touch_id campaign_id      user_id touch_date channel message_variant  delivered  opened  clicked               outcome  reactivated user_state_at_touch  cost_usd
TCH-0000000001     CMP-003 USR-00000081 2025-04-03   email     C_incentive       True    True    False engaged_no_conversion        False              lapsed      0.04
TCH-0000000002     CMP-003 USR-00000129 2025-04-03   email     C_incentive       True   False    False           no_response        False              lapsed      0.04
TCH-0000000003     CMP-001 USR-00000163 2025-04-06   email     C_incentive       True   False    False           no_response        False             at_risk      0.04
TCH-0000000004     CMP-001 USR-00000198 2025-04-06   email     C_incentive       True   False    False           no_response        False             at_risk      0.04
TCH-0000000005     CMP-001 USR-00000167 2025-04-08   email  B_personalized       True   False    False           no_response        False             at_risk      0.04
```

<details><summary>dtypes</summary>

```text
touch_id                       object
campaign_id                    object
user_id                        object
touch_date             datetime64[ns]
channel                        object
message_variant                object
delivered                        bool
opened                           bool
clicked                          bool
outcome                        object
reactivated                      bool
user_state_at_touch            object
cost_usd                      float64
```

</details>

### `churn_labels` — 2,257 rows

```text
month_start      user_id  geo  churned churn_date  tenure_months  is_power_user_month  active_days  avg_coding_hours  avg_acceptance_rate  avg_session_frequency  coding_hours_trend_30d  support_tickets_30d  features_adopted  crm_touches_30d
 2025-03-01 USR-00000001 APAC    False        NaT              3                False           18             1.847               0.4368                  3.833                     1.0                    0                 1                0
 2025-03-01 USR-00000003   NA    False        NaT              5                False           20             3.828               0.3958                  2.900                     1.0                    0                 1                0
 2025-03-01 USR-00000004 EMEA    False        NaT              5                False           11             1.328               0.3055                  2.545                     1.0                    0                 0                0
 2025-03-01 USR-00000006 EMEA    False        NaT             20                False           22             5.087               0.3297                  6.545                     1.0                    0                 0                0
 2025-03-01 USR-00000007   NA    False        NaT              8                False           22             3.961               0.3059                  6.409                     1.0                    0                 1                0
```

<details><summary>dtypes</summary>

```text
month_start               datetime64[ns]
user_id                           object
geo                               object
churned                             bool
churn_date                datetime64[ns]
tenure_months                      int64
is_power_user_month                 bool
active_days                        int64
avg_coding_hours                 float64
avg_acceptance_rate              float64
avg_session_frequency            float64
coding_hours_trend_30d           float64
support_tickets_30d                int64
features_adopted                   int64
crm_touches_30d                    int64
```

</details>

## 6. Summary statistics

### Per-geography breakdown

```text
       users  power_users  at_risk_user_months  churn_events  monthly_churn_rate  avg_coding_hours  avg_acceptance_rate  avg_session_frequency  power_user_share
geo                                                                                                                                                             
NA        76           24                  862            38              0.0441            4.8072               0.3897                 4.5330            0.3158
EMEA      62           21                  780            29              0.0372            4.5439               0.3705                 4.4408            0.3387
APAC      35            6                  350            23              0.0657            4.4689               0.3850                 3.7437            0.1714
ANZ       10            4                  131             6              0.0458            5.0353               0.4056                 4.5379            0.4000
LATAM     10            2                  101             5              0.0495            4.8146               0.4043                 3.9364            0.2000
MEA        7            2                   33             5              0.1515            6.1624               0.4400                 5.8625            0.2857
```

### Per-month churn and engagement

```text
             at_risk_users  churn_events  monthly_churn_rate  avg_coding_hours  avg_acceptance_rate  avg_session_frequency  power_user_months
month_start                                                                                                                                  
2025-03-01             131             9              0.0687            3.6277               0.3462                 3.6227                 26
2025-04-01             122             3              0.0246            3.8332               0.3495                 3.6706                 23
2025-05-01             123             6              0.0488            3.8105               0.3480                 3.5459                 26
2025-06-01             123             9              0.0732            3.9117               0.3512                 3.7031                 32
2025-07-01             120             8              0.0667            3.8488               0.3489                 3.6833                 24
2025-08-01             124            10              0.0806            4.0719               0.3527                 3.8537                 32
2025-09-01             127             4              0.0315            4.5630               0.3707                 4.2746                 46
2025-10-01             132             6              0.0455            4.6604               0.3759                 4.3808                 56
2025-11-01             134             3              0.0224            4.6067               0.3785                 4.3014                 50
2025-12-01             136            10              0.0735            4.3502               0.3619                 4.1621                 46
2026-01-01             128             7              0.0547            5.0499               0.3988                 4.7126                 56
2026-02-01             128             2              0.0156            5.2036               0.4073                 4.8140                 55
2026-03-01             129             4              0.0310            5.3496               0.4192                 4.9075                 64
2026-04-01             129             6              0.0465            5.3550               0.4173                 4.9742                 56
2026-05-01             125             6              0.0480            5.3825               0.4214                 4.8703                 55
2026-06-01             119             4              0.0336            5.5573               0.4215                 5.0094                 64
2026-07-01             115             4              0.0348            5.7603               0.4303                 5.1640                 59
2026-08-01             112             5              0.0446            5.7899               0.4333                 5.1489                 56
```

### `usage_events` numeric distributions (the A06 behavioural signal)

```text
       coding_hours  ai_suggestion_acceptance_rate  session_frequency  suggestions_shown  suggestions_accepted  lines_of_code_written  files_touched  ai_requests
count   43,514.0000                    43,514.0000        43,514.0000        43,514.0000           43,514.0000            43,514.0000    43,514.0000  43,514.0000
mean         5.3211                         0.4098             4.8617           180.8768               82.2896               330.0294        23.4080      16.4951
std          3.8911                         0.1381             3.3443           132.9444               77.8976               241.9262        17.7647      12.7544
min          0.1150                         0.0000             1.0000             1.0000                0.0000                 5.0000         1.0000       0.0000
25%          2.3940                         0.3158             2.0000            81.0000               27.0000               148.0000        10.0000       7.0000
50%          4.2260                         0.4085             4.0000           144.0000               57.0000               263.0000        19.0000      13.0000
75%          7.1650                         0.5000             7.0000           243.7500              110.0000               445.0000        32.0000      22.0000
max         16.0000                         0.9208            24.0000           625.0000              523.0000             1,109.0000        99.0000      76.0000
```

### `users` categorical distributions

```text
       users
geo         
NA        76
EMEA      62
APAC      35
LATAM     10
ANZ       10
MEA        7

                 users
persona               
individual_dev      81
team_lead           36
student             29
freelancer          28
startup_founder     26

                  users
plan                   
pro_monthly         139
pro_annual           41
pro_team_monthly     20
```

### `subscriptions` (A03) lifecycle mix

```text
                            terms
status                           
active                        107
canceled                       97
churned_after_reactivation      9
downgraded                      7

                           cancellations
cancel_reason                           
stopped_using                         39
too_expensive                         29
missing_features                      14
switched_competitor                   11
quality_of_suggestions                 7
other                                  3
employer_provided_license              3

total recognised revenue in window: $49,073.98
terms per user: 1.100
downgrade terms: 7   reactivation terms: 13
```

### `feature_adoption` (A07) stickiness features

```text
                 rows  adoption_rate  avg_activations  avg_depth
feature_key                                                     
agent_mode       2270         0.3982          10.4674     0.2146
codebase_chat    2270         0.6035          47.0599     0.4041
multi_file_edit  2270         0.3762           7.3586     0.1996
project_rules    2270         0.1894           0.9652     0.0849
tab_completion   2270         0.7493         265.3793     0.5752
terminal_ai      2270         0.2687           8.3833     0.1350
```

### `support_tickets` (A14) volume, chat volume and CSAT

```text
                 tickets  avg_chat_messages  avg_csat  escalation_rate
channel                                                               
community_forum       26             6.8846    4.0588           0.1538
email                 72             6.5000    4.1053           0.0694
in_app_chat          103             6.6214    3.8254           0.1165
phone                 22             6.8636    4.0909           0.0909

                     tickets  avg_csat
category                              
account_login             27    4.2500
billing                   37    3.6471
feature_request           24    3.8824
indexing_failure          33    4.1667
integration               15    3.8182
performance_latency       42    3.8095
suggestion_quality        45    4.0690

overall mean CSAT: 3.9612 (response rate 57.85%)
total chat messages: 1,480
```

### `crm_touches` by campaign, outcome and user state at touch

```text
             touches  delivered_rate  open_rate  click_rate  reactivation_rate  cost_usd
campaign_id                                                                             
CMP-001          320          0.9812     0.3375      0.1062             0.0000   12.8000
CMP-002           33          1.0000     0.6970      0.2121             0.0000    0.3300
CMP-003          171          0.9415     0.3567      0.1111             0.0760    6.8400
CMP-004          321          1.0000     0.6168      0.2741             0.0000    3.2100
CMP-005          253          0.8617     0.3360      0.0672             0.0000    5.0600

                       touches
outcome                       
no_response                613
engaged_no_conversion      456
unsubscribed                16
reactivated                 13

                     touches
user_state_at_touch         
active                   489
at_risk                  438
lapsed                   171
```

### `crm_campaigns`

```text
  campaign_id                   campaign_name  objective channel                   target_segment                   offer_type   budget_usd start_date   end_date  is_active_at_window_end
0     CMP-001        At-Risk Behavioral Nudge  retention   email      declining_engagement_active            usage_tips_digest 180,000.0000 2025-03-01 2026-08-31                     True
1     CMP-002  Power User Retention Concierge  retention  in_app  declining_engagement_power_user    dedicated_success_session 240,000.0000 2025-05-01 2026-08-31                     True
2     CMP-003              Lapsed Pro Winback    winback   email                lapsed_within_90d         two_months_50pct_off 210,000.0000 2025-04-01 2026-08-31                     True
3     CMP-004      Agent Mode Adoption Series   adoption  in_app      low_feature_adoption_active           guided_walkthrough 120,000.0000 2025-07-01 2026-08-31                     True
4     CMP-005       Annual Plan Upgrade Offer  expansion    push          engaged_monthly_billers  annual_switch_2_months_free  95,000.0000 2025-09-01 2026-08-31                     True
```

## 7. Churn-signal realism check

The brief requires that **declining coding hours, falling AI-suggestion
acceptance and dropping session frequency correlate with higher churn
propensity.** The table below compares the last 3 at-risk months of
users who eventually churned against users who were retained.

```text
          users  avg_coding_hours  avg_acceptance_rate  avg_session_frequency  avg_active_days  avg_coding_hours_trend  avg_support_tickets
cohort                                                                                                                                     
retained    103            6.1949               0.4486                 5.4695          21.4531                  1.0011               0.1197
churned      97            1.9548               0.2750                 2.5216          11.3440                  0.9703               0.1680
```

### Monthly churn rate by coding-hours trend bucket

The core signal: churn rises steeply as the month-over-month coding-hours trend falls, from ~3% among growing users to a multiple of that among collapsing ones.

The highest `>1.25 (surging)` bucket is *not* the lowest-churn group, and that is expected rather than a defect: a large positive swing is usually a rebound off a very low prior month, so it mixes genuinely recovering users with erratic ones. The monotone part of the relationship is the decline side, which is what the churn model is meant to learn.

```text
                             user_months  churn_rate  avg_coding_hours  avg_acceptance_rate  avg_session_frequency
trend_bucket                                                                                                      
<=0.50 (collapsing)                    8      0.6250            0.4489               0.1544                 1.1952
0.50-0.75 (steep decline)            140      0.1000            2.4379               0.3150                 2.9587
0.75-0.90 (declining)                469      0.0533            3.8875               0.3644                 4.0260
0.90-1.00 (flat/slight dip)          563      0.0426            4.8544               0.3928                 4.5152
1.00-1.25 (growing)                  862      0.0290            5.3705               0.4034                 4.7143
>1.25 (surging)                      215      0.0605            4.9811               0.3862                 4.4153
```

### Pearson correlation of each behavioural feature with the churn label

Negative = higher values of the feature go with *less* churn.

```text
                        pearson_r_with_churned
avg_coding_hours                       -0.2035
avg_acceptance_rate                    -0.2144
avg_session_frequency                  -0.1708
coding_hours_trend_30d                 -0.0541
active_days                            -0.4214
support_tickets_30d                     0.1016
features_adopted                       -0.0957
tenure_months                          -0.0226
```

## 8. Internal consistency checks

Run by `datagen.pipeline.validate` on the frames emitted above.

```text
referential integrity subscriptions.user_id -> users.user_id: 0/200 distinct ids orphaned -> OK
referential integrity usage_events.user_id -> users.user_id: 0/199 distinct ids orphaned -> OK
referential integrity feature_adoption.user_id -> users.user_id: 0/200 distinct ids orphaned -> OK
referential integrity support_tickets.user_id -> users.user_id: 0/120 distinct ids orphaned -> OK
referential integrity crm_touches.user_id -> users.user_id: 0/196 distinct ids orphaned -> OK
referential integrity churn_labels.user_id -> users.user_id: 0/200 distinct ids orphaned -> OK
referential integrity crm_touches.campaign_id -> crm_campaigns.campaign_id: 0/5 orphaned -> OK
primary key users(user_id): 0/200 rows duplicated -> OK
primary key subscriptions(subscription_id): 0/220 rows duplicated -> OK
primary key usage_events(user_id, event_date): 0/43,514 rows duplicated -> OK
primary key feature_adoption(user_id, feature_key, month_start): 0/13,620 rows duplicated -> OK
primary key support_tickets(ticket_id): 0/223 rows duplicated -> OK
primary key crm_campaigns(campaign_id): 0/5 rows duplicated -> OK
primary key crm_touches(touch_id): 0/1,098 rows duplicated -> OK
primary key churn_labels(user_id, month_start): 0/2,257 rows duplicated -> OK
usage_events.event_date within window: OK
usage_events value ranges plausible: OK
monthly churn rate 0.0470 within +/-0.5pt of target 0.0470: OK
usage_events after cancellation (non-reactivated users): 0/7,377 rows outside -> OK
support_tickets.created_date inside an active subscription term: 0/223 tickets outside -> OK
reactivated touches (13) == reactivation terms (13): OK
reactivations per user <= MAX_REACTIVATIONS (1); observed max 1: OK
churn_labels.churn_date set whenever churned: OK
```

## 9. Determinism — what is guaranteed, and its SHA-256 digests

**The guaranteed invariant is deterministic logical content:** for a
fixed seed and config, every table's column names, column order, row
order and cell values are identical on every run. The digests below
are SHA-256 over a *canonical text rendering* of each table — the
header row followed by `DataFrame.to_csv(index=False)` — which is
exactly what `datagen.writer.checksum_frames` hashes and what
`tests/test_determinism.py::test_same_seed_produces_identical_content_checksums`
asserts. They are **not** hashes of the Parquet files.

This holds because no wall-clock time enters the data: the observation
window is anchored to a fixed `end_date` (default
`2026-08-31`), never `date.today()`.

### 9a. Canonical content digests (the guaranteed invariant)

```text
churn_labels         d37f134c19ccd6eca833eb8053c21be30a76788ee0e3a896a8f8a01fd4a75679
crm_campaigns        24a031ae365c958ae66b44d066a077fa0177b5a3dcc36487fa7dd1b3e25473ca
crm_touches          281fb13236b94f9221f35475b40f861d42b58962d798c25d0401b4d43e51b267
feature_adoption     aac908cce9914ca793191b8d926e08298ca77ec5febad52ab113731da3f402b8
subscriptions        0b0931cc7b28050111bd74eda91f44d0162ec3dace1863c26923065d5b03a8f9
support_tickets      1da136be8f0634251cb6c73baf0da8f9ed71e08a83d3483114df60739e28e196
usage_events         221d72cdba117e482c97e2784b891492beefd909659922f0fe7ddb6ff8ad5bc6
users                9e82fa0fc0410c3a5b5f2b3a54644ecbe5afd9fb22084404f8196b08b3cf9699
```

### 9b. Emitted Parquet file digests (verified across two runs)

SHA-256 of the actual files written to disk by this run. The generator
was run **twice** into different directories and these digests compared;
they matched, which is recorded in section 9c.

Note the scope: Parquet byte-equality is a property of the *writer*, not
of this generator — the file footer embeds the pyarrow version string, so
a pyarrow upgrade would change these bytes while leaving the data
identical. Treat 9b/9c as "the generator adds no nondeterminism of its
own, in a pinned environment"; treat 9a as the claim that always holds.

```text
users/part-00000.parquet                 c662643ba1abcbb3c06f8016bf6b7169f5e9b2ae7f2d3d0364c2f048f979f0d8
subscriptions/part-00000.parquet         501ccf574122c0e9ccdbfc6e8ce19ef8f9479f9e1600ea6596154642d26caac9
usage_events/part-00000.parquet          e53cc20e63f4015c7baa25d305d3030d71bbf00a223ecc5e0f1a0c17e601dce0
feature_adoption/part-00000.parquet      bab01582295c173aa7add050d329aa4962c8a91be7fe270bfa68a212bb2a403e
support_tickets/part-00000.parquet       1619b672b8c63e0b1f26aca8c124ba986e6cf07fba0b2a005ab1280fdc5ac0f8
crm_campaigns/part-00000.parquet         1e3eb2239eb0cfeeeba89f2e962ee514086dd4d19606dcf974ddfb2c4ce906c6
crm_touches/part-00000.parquet           77626f6ea673638d9ddb65c77e3865474db4cdd90a3c3c510bb65045ba1d39dc
churn_labels/part-00000.parquet          3daba07defbbf056fce2a3c678d62b8005114493f81fb81f17189dd6e523e338
```

## 9c. Two-run reproducibility check (committed proof)

The generator was executed a second time with the same seed and config into a separate output directory, and both the canonical content digests and the emitted Parquet bytes were compared. Result:

```text
run 1 output dir            : data/sample
run 2 output dir            : <temporary directory, removed after comparison>
tables compared             : 8
content digests match       : True
parquet files compared      : 8
parquet byte digests match  : True

combined SHA-256 over all canonical content digests:
  run 1: 44d157a1f647111b9c4dd69c572c8610cd6dc32905da6bbbea4736ba336056bf
  run 2: 44d157a1f647111b9c4dd69c572c8610cd6dc32905da6bbbea4736ba336056bf

combined SHA-256 over all emitted Parquet file digests:
  run 1: 4108d2c00408717848bcf7a14b06c8aa386a7ff854b283da9d1f651ca5655e0f
  run 2: 4108d2c00408717848bcf7a14b06c8aa386a7ff854b283da9d1f651ca5655e0f
```

## 10. Output manifest (`_manifest.json`)

Written alongside the data by the run. This is the handoff contract to the Lakeflow ingest stage (files + row counts) and the Unity Catalog stage (target catalog/schema + DDL file). It is reproduced here in full because the data directory itself is gitignored — the dataset is regenerated from the committed seed rather than committed.

```json
{
  "generator_version": "0.1.0",
  "config": {
    "seed": 1729,
    "users_requested": 50000,
    "sample_frac": 0.004,
    "users_effective": 200,
    "months": 18,
    "window_start": "2025-03-01",
    "window_end": "2026-08-31",
    "days": 549,
    "target_monthly_churn_rate": 0.047,
    "target_reactivation_rate": 0.08,
    "power_user_bar": ">=4.0 coding hours/day on >=5 days/week",
    "campaigns": 5,
    "output_format": "parquet",
    "partitioned": false,
    "out_dir": "data/sample"
  },
  "unity_catalog": {
    "catalog": "dev_behavior",
    "bronze_schema": "bronze",
    "gold_schema": "gold",
    "format_intent": "delta",
    "ddl_file": "_unity_catalog.sql"
  },
  "tables": [
    {
      "table": "users",
      "asset": "VA (identity / persona / entitlements)",
      "layer": "bronze",
      "grain": "one row per Pro-tier user",
      "rows": 200,
      "columns": [
        "user_id",
        "signup_date",
        "geo",
        "country",
        "plan",
        "tier",
        "persona",
        "company_size",
        "acquisition_channel",
        "primary_language",
        "ide_theme",
        "power_user_flag",
        "tenure_days_at_window_end"
      ],
      "partition_by": [
        "geo"
      ],
      "partitions_written": false,
      "files": [
        "users/part-00000.parquet"
      ],
      "bytes": 12763
    },
    {
      "table": "subscriptions",
      "asset": "A03 \u2014 subscription plans & billing history",
      "layer": "bronze",
      "grain": "one row per subscription term (a plan a user held for a period)",
      "rows": 220,
      "columns": [
        "subscription_id",
        "user_id",
        "plan_id",
        "plan_name",
        "tier",
        "billing_period",
        "mrr_usd",
        "list_price_usd",
        "term_start_date",
        "term_end_date",
        "term_index",
        "status",
        "renewals_count",
        "payment_failures",
        "is_downgrade",
        "is_reactivation",
        "cancel_date",
        "cancel_reason",
        "revenue_usd"
      ],
      "partition_by": [],
      "partitions_written": false,
      "files": [
        "subscriptions/part-00000.parquet"
      ],
      "bytes": 19920
    },
    {
      "table": "usage_events",
      "asset": "A06 \u2014 raw product usage events & telemetry",
      "layer": "bronze",
      "grain": "one row per user per ACTIVE day (inactive days are not emitted)",
      "rows": 43514,
      "columns": [
        "event_date",
        "user_id",
        "geo",
        "coding_hours",
        "ai_suggestion_acceptance_rate",
        "session_frequency",
        "suggestions_shown",
        "suggestions_accepted",
        "lines_of_code_written",
        "files_touched",
        "ai_requests",
        "is_weekend"
      ],
      "partition_by": [
        "event_date"
      ],
      "partitions_written": false,
      "files": [
        "usage_events/part-00000.parquet"
      ],
      "bytes": 562824
    },
    {
      "table": "feature_adoption",
      "asset": "A07 \u2014 feature adoption & activation metrics",
      "layer": "bronze",
      "grain": "one row per user per feature per month",
      "rows": 13620,
      "columns": [
        "month_start",
        "user_id",
        "feature_key",
        "feature_name",
        "feature_family",
        "is_adopted",
        "first_activation_date",
        "activation_count",
        "active_days",
        "depth_score"
      ],
      "partition_by": [
        "month_start"
      ],
      "partitions_written": false,
      "files": [
        "feature_adoption/part-00000.parquet"
      ],
      "bytes": 53258
    },
    {
      "table": "support_tickets",
      "asset": "A14 \u2014 support tickets, chat logs & CSAT",
      "layer": "bronze",
      "grain": "one row per support ticket",
      "rows": 223,
      "columns": [
        "ticket_id",
        "user_id",
        "created_date",
        "channel",
        "category",
        "priority",
        "chat_message_count",
        "first_response_minutes",
        "resolution_hours",
        "reopened_count",
        "is_escalated",
        "csat_score",
        "resolved"
      ],
      "partition_by": [],
      "partitions_written": false,
      "files": [
        "support_tickets/part-00000.parquet"
      ],
      "bytes": 14742
    },
    {
      "table": "crm_campaigns",
      "asset": "VA (marketing saturation / campaign metadata)",
      "layer": "bronze",
      "grain": "one row per CRM campaign",
      "rows": 5,
      "columns": [
        "campaign_id",
        "campaign_name",
        "objective",
        "channel",
        "target_segment",
        "offer_type",
        "budget_usd",
        "start_date",
        "end_date",
        "is_active_at_window_end"
      ],
      "partition_by": [],
      "partitions_written": false,
      "files": [
        "crm_campaigns/part-00000.parquet"
      ],
      "bytes": 7023
    },
    {
      "table": "crm_touches",
      "asset": "VA (CRM touch + reactivation outcome)",
      "layer": "bronze",
      "grain": "one row per campaign touch sent to a user",
      "rows": 1098,
      "columns": [
        "touch_id",
        "campaign_id",
        "user_id",
        "touch_date",
        "channel",
        "message_variant",
        "delivered",
        "opened",
        "clicked",
        "outcome",
        "reactivated",
        "user_state_at_touch",
        "cost_usd"
      ],
      "partition_by": [
        "touch_date"
      ],
      "partitions_written": false,
      "files": [
        "crm_touches/part-00000.parquet"
      ],
      "bytes": 23856
    },
    {
      "table": "churn_labels",
      "asset": "derived label (gold) \u2014 supervised training target",
      "layer": "gold",
      "grain": "one row per user per month the user was a subscriber at month start",
      "rows": 2257,
      "columns": [
        "month_start",
        "user_id",
        "geo",
        "churned",
        "churn_date",
        "tenure_months",
        "is_power_user_month",
        "active_days",
        "avg_coding_hours",
        "avg_acceptance_rate",
        "avg_session_frequency",
        "coding_hours_trend_30d",
        "support_tickets_30d",
        "features_adopted",
        "crm_touches_30d"
      ],
      "partition_by": [
        "month_start"
      ],
      "partitions_written": false,
      "files": [
        "churn_labels/part-00000.parquet"
      ],
      "bytes": 68392
    }
  ],
  "total_rows": 61137
}
```

## 12. Appendix — non-reproducible execution details

> **Everything in this appendix varies between runs by design** —
> wall-clock durations and log timestamps depend on when and where the
> generator ran, not on the seed. It is kept separate so sections 1-11
> above are byte-for-byte reproducible: diffing two runs of the
> documented command should show differences *only* inside this
> appendix (plus any `out_dir` paths you changed).

### Stage timings (seconds, wall clock)

| Stage | Wall clock |
| --- | --- |
| population | 0.005 |
| lifecycle | 0.138 |
| usage_events | 0.062 |
| users | 0.001 |
| subscriptions | 0.019 |
| feature_adoption | 0.018 |
| support_tickets | 0.005 |
| crm_campaigns | 0.001 |
| crm_touches | 0.004 |
| churn_labels | 0.007 |
| conform | 0.106 |

### Console log

Captured verbatim from the generator's stderr logger. Timestamps are wall-clock and therefore differ per run.

```console
2026-09-08 20:16:56,053 INFO    datagen | datagen starting | seed=1729 users_requested=50000 sample_frac=0.004 users_effective=200 months=18 window_start=2025-03-01 window_end=2026-08-31 days=549 target_monthly_churn_rate=0.047 target_reactivation_rate=0.08 power_user_bar=>=4.0 coding hours/day on >=5 days/week campaigns=5 output_format=parquet partitioned=False out_dir=data/sample
2026-09-08 20:16:56,053 INFO    datagen | building population: 200 users, 18 months (2025-03-01 .. 2026-08-31)
2026-09-08 20:16:56,059 INFO    datagen | simulating subscription lifecycle + CRM (calibrating churn hazard)
2026-09-08 20:16:56,197 INFO    datagen | hazard intercept calibrated to -2.20312 in 10 iterations -> monthly churn 0.0470 (target 0.0470)
2026-09-08 20:16:56,197 INFO    datagen | generating usage_events (active days only)
2026-09-08 20:16:56,259 INFO    datagen | usage_events: 43,514 rows
2026-09-08 20:16:56,420 INFO    datagen | users                     200 rows
2026-09-08 20:16:56,420 INFO    datagen | subscriptions             220 rows
2026-09-08 20:16:56,420 INFO    datagen | usage_events           43,514 rows
2026-09-08 20:16:56,420 INFO    datagen | feature_adoption       13,620 rows
2026-09-08 20:16:56,420 INFO    datagen | support_tickets           223 rows
2026-09-08 20:16:56,420 INFO    datagen | crm_campaigns               5 rows
2026-09-08 20:16:56,421 INFO    datagen | crm_touches             1,098 rows
2026-09-08 20:16:56,421 INFO    datagen | churn_labels            2,257 rows
2026-09-08 20:16:56,457 INFO    datagen.writer | wrote users                     200 rows -> 1 file(s)
2026-09-08 20:16:56,460 INFO    datagen.writer | wrote subscriptions             220 rows -> 1 file(s)
2026-09-08 20:16:56,483 INFO    datagen.writer | wrote usage_events           43,514 rows -> 1 file(s)
2026-09-08 20:16:56,497 INFO    datagen.writer | wrote feature_adoption       13,620 rows -> 1 file(s)
2026-09-08 20:16:56,499 INFO    datagen.writer | wrote support_tickets           223 rows -> 1 file(s)
2026-09-08 20:16:56,501 INFO    datagen.writer | wrote crm_campaigns               5 rows -> 1 file(s)
2026-09-08 20:16:56,504 INFO    datagen.writer | wrote crm_touches             1,098 rows -> 1 file(s)
2026-09-08 20:16:56,509 INFO    datagen.writer | wrote churn_labels            2,257 rows -> 1 file(s)
2026-09-08 20:16:56,510 INFO    datagen.writer | wrote manifest -> data/sample/_manifest.json
2026-09-08 20:16:56,510 INFO    datagen.writer | wrote Unity Catalog DDL -> data/sample/_unity_catalog.sql
2026-09-08 20:16:56,540 INFO    datagen | check: referential integrity subscriptions.user_id -> users.user_id: 0/200 distinct ids orphaned -> OK
2026-09-08 20:16:56,540 INFO    datagen | check: referential integrity usage_events.user_id -> users.user_id: 0/199 distinct ids orphaned -> OK
2026-09-08 20:16:56,540 INFO    datagen | check: referential integrity feature_adoption.user_id -> users.user_id: 0/200 distinct ids orphaned -> OK
2026-09-08 20:16:56,540 INFO    datagen | check: referential integrity support_tickets.user_id -> users.user_id: 0/120 distinct ids orphaned -> OK
2026-09-08 20:16:56,540 INFO    datagen | check: referential integrity crm_touches.user_id -> users.user_id: 0/196 distinct ids orphaned -> OK
2026-09-08 20:16:56,540 INFO    datagen | check: referential integrity churn_labels.user_id -> users.user_id: 0/200 distinct ids orphaned -> OK
2026-09-08 20:16:56,540 INFO    datagen | check: referential integrity crm_touches.campaign_id -> crm_campaigns.campaign_id: 0/5 orphaned -> OK
2026-09-08 20:16:56,540 INFO    datagen | check: primary key users(user_id): 0/200 rows duplicated -> OK
2026-09-08 20:16:56,540 INFO    datagen | check: primary key subscriptions(subscription_id): 0/220 rows duplicated -> OK
2026-09-08 20:16:56,540 INFO    datagen | check: primary key usage_events(user_id, event_date): 0/43,514 rows duplicated -> OK
2026-09-08 20:16:56,540 INFO    datagen | check: primary key feature_adoption(user_id, feature_key, month_start): 0/13,620 rows duplicated -> OK
2026-09-08 20:16:56,540 INFO    datagen | check: primary key support_tickets(ticket_id): 0/223 rows duplicated -> OK
2026-09-08 20:16:56,540 INFO    datagen | check: primary key crm_campaigns(campaign_id): 0/5 rows duplicated -> OK
2026-09-08 20:16:56,540 INFO    datagen | check: primary key crm_touches(touch_id): 0/1,098 rows duplicated -> OK
2026-09-08 20:16:56,540 INFO    datagen | check: primary key churn_labels(user_id, month_start): 0/2,257 rows duplicated -> OK
2026-09-08 20:16:56,540 INFO    datagen | check: usage_events.event_date within window: OK
2026-09-08 20:16:56,540 INFO    datagen | check: usage_events value ranges plausible: OK
2026-09-08 20:16:56,540 INFO    datagen | check: monthly churn rate 0.0470 within +/-0.5pt of target 0.0470: OK
2026-09-08 20:16:56,541 INFO    datagen | check: usage_events after cancellation (non-reactivated users): 0/7,377 rows outside -> OK
2026-09-08 20:16:56,541 INFO    datagen | check: support_tickets.created_date inside an active subscription term: 0/223 tickets outside -> OK
2026-09-08 20:16:56,541 INFO    datagen | check: reactivated touches (13) == reactivation terms (13): OK
2026-09-08 20:16:56,541 INFO    datagen | check: reactivations per user <= MAX_REACTIVATIONS (1); observed max 1: OK
2026-09-08 20:16:56,541 INFO    datagen | check: churn_labels.churn_date set whenever churned: OK
2026-09-08 20:16:56,541 INFO    datagen | monthly churn rate: 0.0470 (target 0.0470) | users 200 | usage_events 43,514 rows
2026-09-08 20:16:56,541 INFO    datagen | churn detail: 106 churn events / 2257 at-risk user-months = 0.046965
2026-09-08 20:16:56,541 INFO    datagen | datagen finished | total rows 61,137
2026-09-08 20:16:56,544 INFO    datagen | verifying reproducibility: regenerating into a temporary directory
2026-09-08 20:16:56,875 INFO    datagen | building population: 200 users, 18 months (2025-03-01 .. 2026-08-31)
2026-09-08 20:16:56,879 INFO    datagen | simulating subscription lifecycle + CRM (calibrating churn hazard)
2026-09-08 20:16:57,014 INFO    datagen | hazard intercept calibrated to -2.20312 in 10 iterations -> monthly churn 0.0470 (target 0.0470)
2026-09-08 20:16:57,014 INFO    datagen | generating usage_events (active days only)
2026-09-08 20:16:57,072 INFO    datagen | usage_events: 43,514 rows
2026-09-08 20:16:57,235 INFO    datagen | users                     200 rows
2026-09-08 20:16:57,235 INFO    datagen | subscriptions             220 rows
2026-09-08 20:16:57,235 INFO    datagen | usage_events           43,514 rows
2026-09-08 20:16:57,235 INFO    datagen | feature_adoption       13,620 rows
2026-09-08 20:16:57,235 INFO    datagen | support_tickets           223 rows
2026-09-08 20:16:57,235 INFO    datagen | crm_campaigns               5 rows
2026-09-08 20:16:57,235 INFO    datagen | crm_touches             1,098 rows
2026-09-08 20:16:57,235 INFO    datagen | churn_labels            2,257 rows
2026-09-08 20:16:57,567 INFO    datagen.writer | wrote users                     200 rows -> 1 file(s)
2026-09-08 20:16:57,570 INFO    datagen.writer | wrote subscriptions             220 rows -> 1 file(s)
2026-09-08 20:16:57,593 INFO    datagen.writer | wrote usage_events           43,514 rows -> 1 file(s)
2026-09-08 20:16:57,606 INFO    datagen.writer | wrote feature_adoption       13,620 rows -> 1 file(s)
2026-09-08 20:16:57,608 INFO    datagen.writer | wrote support_tickets           223 rows -> 1 file(s)
2026-09-08 20:16:57,610 INFO    datagen.writer | wrote crm_campaigns               5 rows -> 1 file(s)
2026-09-08 20:16:57,613 INFO    datagen.writer | wrote crm_touches             1,098 rows -> 1 file(s)
2026-09-08 20:16:57,619 INFO    datagen.writer | wrote churn_labels            2,257 rows -> 1 file(s)
2026-09-08 20:16:57,620 INFO    datagen.writer | wrote manifest -> /tmp/datagen-verify-u_4yffxh/_manifest.json
2026-09-08 20:16:57,620 INFO    datagen.writer | wrote Unity Catalog DDL -> /tmp/datagen-verify-u_4yffxh/_unity_catalog.sql
2026-09-08 20:16:57,626 INFO    datagen | reproducibility: content digests MATCH | parquet byte digests MATCH
```

---

*Generated by `src/datagen`. Synthetic data only — no real customer data.
Reproduce with the command at the top of this file.*
