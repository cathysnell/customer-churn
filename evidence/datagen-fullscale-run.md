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
$ python -m datagen --users 50000 --months 18 --out /tmp/fullrun --format parquet --no-partitions --evidence /tmp/full-evidence-new.md
```

## 1. Run configuration

| Knob | Value |
| --- | --- |
| seed | `1729` |
| users_requested | `50000` |
| sample_frac | `1.0` |
| users_effective | `50000` |
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
| out_dir | `/tmp/fullrun` |

Hazard calibration: intercept **-2.21875** found in
**9** bisection steps, giving a realised
monthly churn rate of **0.046999**
(4.6999%) against the configured
target of **0.047000** (4.7000%).

## 2. Row counts

| Table | Data asset | Layer | Rows | Grain |
| --- | --- | --- | --- | --- |
| `users` | VA (identity / persona / entitlements) | bronze | 50,000 | one row per Pro-tier user |
| `subscriptions` | A03 — subscription plans & billing history | bronze | 54,557 | one row per subscription term (a plan a user held for a period) |
| `usage_events` | A06 — raw product usage events & telemetry | bronze | 10,778,146 | one row per user per ACTIVE day (inactive days are not emitted) |
| `feature_adoption` | A07 — feature adoption & activation metrics | bronze | 3,451,752 | one row per user per feature per month |
| `support_tickets` | A14 — support tickets, chat logs & CSAT | bronze | 63,101 | one row per support ticket |
| `crm_campaigns` | VA (marketing saturation / campaign metadata) | bronze | 5 | one row per CRM campaign |
| `crm_touches` | VA (CRM touch + reactivation outcome) | bronze | 289,382 | one row per campaign touch sent to a user |
| `churn_labels` | derived label (gold) — supervised training target | gold | 571,848 | one row per user per month the user was a subscriber at month start |
| **TOTAL** | | | **15,258,791** | |

## 3. Headline KPIs realised in the generated data

All targets below are the **illustrative** baselines from
`docs/project-brief.md` — chosen for this demo, not real Anysphere figures.

Every rate is shown as the explicit fraction that produces it, so the
arithmetic is checkable rather than asserted.

| KPI | Target (illustrative) | Realised in this run | Numerator / denominator |
| --- | --- | --- | --- |
| Pro monthly churn rate | 4.70% | **4.6999%** (`0.046999`) | 26,876 churn events / 571,848 at-risk user-months |
| CRM winback reactivation rate | 8.00% | **7.9926%** (`0.079926`) | 3,444 reactivated / 43,090 delivered winback touches |
| Power-user share (sustained: >=4 hrs/day on >=5 days/wk, in >=50% of >=2 active months) | segment definition | **22.2920%** | 11,146 flagged / 50,000 users |
| Users who churned at least once in the window | — | **49.4940%** | over 50,000 users |
| `usage_events` density (rows / (users x days)) | active days only | **39.2646%** | 10,778,146 rows / (50,000 x 549) |

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

### `users` — 50,000 rows

```text
     user_id signup_date  geo country             plan tier         persona company_size acquisition_channel primary_language     ide_theme  power_user_flag  tenure_days_at_window_end
USR-00000001  2024-07-17 APAC      IN      pro_monthly  pro         student            1      organic_search       typescript          dark            False                        775
USR-00000002  2025-05-03 EMEA      ES pro_team_monthly  pro  individual_dev       51-200      organic_search       typescript         light             True                        485
USR-00000003  2024-02-10   NA      CA      pro_monthly  pro       team_lead        11-50      organic_search           python         light            False                        933
USR-00000004  2024-10-23 EMEA      PL       pro_annual  pro       team_lead         2-10      organic_search               go          dark            False                        677
USR-00000005  2025-08-12   NA      MX      pro_monthly  pro startup_founder        1000+         paid_search           python high_contrast             True                        384
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

### `subscriptions` — 54,557 rows

```text
subscription_id      user_id          plan_id        plan_name tier billing_period  mrr_usd  list_price_usd term_start_date term_end_date  term_index   status  renewals_count  payment_failures  is_downgrade  is_reactivation cancel_date cancel_reason  revenue_usd
  SUB-000000001 USR-00000001      pro_monthly      Pro Monthly  pro        monthly     20.0            20.0      2024-07-17           NaT           0   active              18                 0         False            False         NaT          None       366.00
  SUB-000000002 USR-00000002 pro_team_monthly Pro Team Monthly  pro        monthly     40.0            40.0      2025-05-03           NaT           0   active              16                 0         False            False         NaT          None       648.00
  SUB-000000003 USR-00000003      pro_monthly      Pro Monthly  pro        monthly     20.0            20.0      2024-02-10    2025-08-03           0 canceled               5                 0         False            False  2025-08-03 stopped_using       104.00
  SUB-000000004 USR-00000004       pro_annual       Pro Annual  pro         annual     16.0           192.0      2024-10-23           NaT           0   active               1                 0         False            False         NaT          None       292.80
  SUB-000000005 USR-00000005      pro_monthly      Pro Monthly  pro        monthly     20.0            20.0      2025-08-12           NaT           0   active              12                 0         False            False         NaT          None       256.67
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

### `usage_events` — 10,778,146 rows

```text
event_date      user_id  geo  coding_hours  ai_suggestion_acceptance_rate  session_frequency  suggestions_shown  suggestions_accepted  lines_of_code_written  files_touched  ai_requests  is_weekend
2025-03-01 USR-00000001 APAC         1.096                         0.7429                  2                 35                    26                     65              3            3        True
2025-03-01 USR-00000003   NA         2.212                         0.3333                  3                 72                    24                    126              4            9        True
2025-03-01 USR-00000011 EMEA         3.248                         0.4340                  2                106                    46                    184             11            9        True
2025-03-01 USR-00000013   NA         1.873                         0.5385                  1                 52                    28                    116              8            6        True
2025-03-01 USR-00000017 EMEA         2.897                         0.4259                  1                108                    46                    184             10            7        True
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

### `feature_adoption` — 3,451,752 rows

```text
month_start      user_id     feature_key             feature_name feature_family  is_adopted first_activation_date  activation_count  active_days  depth_score
 2025-03-01 USR-00000001      agent_mode Agentic Multi-Step Edits        agentic       False                   NaT                 0            0          0.0
 2025-03-01 USR-00000001   codebase_chat      Codebase-Aware Chat        core_ai       False                   NaT                 0            0          0.0
 2025-03-01 USR-00000001 multi_file_edit          Multi-File Edit        agentic       False                   NaT                 0            0          0.0
 2025-03-01 USR-00000001   project_rules      Project Rules Files  customization       False                   NaT                 0            0          0.0
 2025-03-01 USR-00000001  tab_completion    Inline Tab Completion        core_ai       False                   NaT                 0            0          0.0
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

### `support_tickets` — 63,101 rows

```text
    ticket_id      user_id created_date     channel           category  priority  chat_message_count  first_response_minutes  resolution_hours  reopened_count  is_escalated  csat_score  resolved
TCK-000000001 USR-00000782   2025-03-01       email        integration P2_normal                   4                     190             54.43               0         False         5.0      True
TCK-000000002 USR-00000791   2025-03-01 in_app_chat suggestion_quality    P3_low                   4                     498             24.92               0         False         3.0      True
TCK-000000003 USR-00001637   2025-03-01 in_app_chat            billing    P3_low                   4                     430             28.27               1         False         NaN      True
TCK-000000004 USR-00001732   2025-03-01 in_app_chat suggestion_quality P2_normal                   2                     205             61.19               0         False         3.0      True
TCK-000000005 USR-00002039   2025-03-01 in_app_chat suggestion_quality   P1_high                   1                      39             13.87               0         False         4.0      True
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

### `crm_touches` — 289,382 rows

```text
      touch_id campaign_id      user_id touch_date channel message_variant  delivered  opened  clicked     outcome  reactivated user_state_at_touch  cost_usd
TCH-0000000001     CMP-001 USR-00000421 2025-04-01   email     C_incentive       True   False    False no_response        False             at_risk      0.04
TCH-0000000002     CMP-001 USR-00000524 2025-04-01   email       A_control       True   False    False no_response        False             at_risk      0.04
TCH-0000000003     CMP-001 USR-00001012 2025-04-01   email     C_incentive       True   False    False no_response        False             at_risk      0.04
TCH-0000000004     CMP-001 USR-00001116 2025-04-01   email       A_control       True   False    False no_response        False             at_risk      0.04
TCH-0000000005     CMP-001 USR-00001184 2025-04-01   email  B_personalized       True   False    False no_response        False             at_risk      0.04
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

### `churn_labels` — 571,848 rows

```text
month_start      user_id  geo  churned churn_date  tenure_months  is_power_user_month  active_days  avg_coding_hours  avg_acceptance_rate  avg_session_frequency  coding_hours_trend_30d  support_tickets_30d  features_adopted  crm_touches_30d
 2025-03-01 USR-00000001 APAC    False        NaT              8                False           18             1.847               0.4347                  4.167                     1.0                    0                 0                0
 2025-03-01 USR-00000003   NA    False        NaT             13                False           20             4.598               0.4041                  3.300                     1.0                    0                 1                0
 2025-03-01 USR-00000004 EMEA    False        NaT              5                False           11             1.666               0.2940                  2.636                     1.0                    0                 1                0
 2025-03-01 USR-00000006 EMEA    False        NaT             48                False           22             4.524               0.3199                  5.500                     1.0                    0                 1                0
 2025-03-01 USR-00000007   NA    False        NaT              8                False           22             4.714               0.3118                  6.545                     1.0                    0                 2                0
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
NA     19174         4389               222984         10043              0.0450            4.2573               0.3794                 4.1866            0.2289
EMEA   13012         2652               150493          6829              0.0454            4.0012               0.3674                 4.0666            0.2038
APAC   10390         2680               120186          5461              0.0454            4.6276               0.4009                 4.4918            0.2579
LATAM   3408          637                34775          2186              0.0629            4.0426               0.3684                 4.0124            0.1869
MEA     2017          351                20060          1304              0.0650            3.8296               0.3581                 3.9111            0.1740
ANZ     1999          437                23350          1053              0.0451            4.0741               0.3816                 4.1200            0.2186
```

### Per-month churn and engagement

```text
             at_risk_users  churn_events  monthly_churn_rate  avg_coding_hours  avg_acceptance_rate  avg_session_frequency  power_user_months
month_start                                                                                                                                  
2025-03-01           35958          1999              0.0556            3.6060               0.3508                 3.6931               7483
2025-04-01           34571          1976              0.0572            3.6313               0.3494                 3.7448               6642
2025-05-01           33697          1922              0.0570            3.6373               0.3491                 3.7396               6695
2025-06-01           33262          2113              0.0635            3.5544               0.3452                 3.6799               6882
2025-07-01           32839          2025              0.0617            3.5570               0.3448                 3.7031               6128
2025-08-01           32556          1929              0.0593            3.6317               0.3501                 3.7405               6794
2025-09-01           32391          1398              0.0432            4.0757               0.3679                 4.0806               9489
2025-10-01           32622          1397              0.0428            4.2388               0.3755                 4.2035               9701
2025-11-01           32681          1398              0.0428            4.1551               0.3748                 4.1101               9610
2025-12-01           32535          2002              0.0615            3.9062               0.3626                 3.9733               8721
2026-01-01           31624          1341              0.0424            4.4355               0.3880                 4.3421              10328
2026-02-01           31291          1230              0.0393            4.6431               0.3984                 4.5060              11059
2026-03-01           30829           951              0.0308            4.8122               0.4077                 4.6244              12001
2026-04-01           30522          1146              0.0375            4.8645               0.4104                 4.6817              11547
2026-05-01           29816          1063              0.0357            4.9274               0.4168                 4.7082              11568
2026-06-01           29090          1082              0.0372            4.9613               0.4178                 4.7664              11665
2026-07-01           28223          1016              0.0360            5.0154               0.4213                 4.8162              11041
2026-08-01           27341           888              0.0325            5.1488               0.4318                 4.8972              11280
```

### `usage_events` numeric distributions (the A06 behavioural signal)

```text
         coding_hours  ai_suggestion_acceptance_rate  session_frequency  suggestions_shown  suggestions_accepted  lines_of_code_written   files_touched     ai_requests
count 10,778,146.0000                10,778,146.0000    10,778,146.0000    10,778,146.0000       10,778,146.0000        10,778,146.0000 10,778,146.0000 10,778,146.0000
mean           4.7703                         0.4054             4.6555           162.1914               73.4957               295.7613         20.9921         14.7870
std            3.5103                         0.1398             3.3024           120.0275               71.8945               218.3151         16.1035         11.5412
min            0.0500                         0.0000             1.0000             1.0000                0.0000                 0.0000          1.0000          0.0000
25%            2.2220                         0.3115             2.0000            75.0000               25.0000               137.0000          9.0000          6.0000
50%            3.7860                         0.4023             4.0000           129.0000               50.0000               235.0000         17.0000         12.0000
75%            6.2690                         0.4951             6.0000           214.0000               96.0000               389.0000         28.0000         20.0000
max           16.0000                         1.0000            40.0000           656.0000              599.0000             1,134.0000        111.0000         85.0000
```

### `users` categorical distributions

```text
       users
geo         
NA     19174
EMEA   13012
APAC   10390
LATAM   3408
MEA     2017
ANZ     1999

                 users
persona               
individual_dev   21788
team_lead         9568
freelancer        7132
startup_founder   5958
student           5554

                  users
plan                   
pro_monthly       34034
pro_annual        11944
pro_team_monthly   4022
```

### `subscriptions` (A03) lifecycle mix

```text
                            terms
status                           
active                      26568
canceled                    24747
churned_after_reactivation   2129
downgraded                   1113

                           cancellations
cancel_reason                           
stopped_using                       8300
too_expensive                       5853
switched_competitor                 4347
missing_features                    3293
quality_of_suggestions              2715
employer_provided_license           1614
other                                754

total recognised revenue in window: $11,823,529.24
terms per user: 1.091
downgrade terms: 1,113   reactivation terms: 3,444
```

### `feature_adoption` (A07) stickiness features

```text
                   rows  adoption_rate  avg_activations  avg_depth
feature_key                                                       
agent_mode       575292         0.3603           9.0516     0.1939
codebase_chat    575292         0.5576          42.7031     0.3724
multi_file_edit  575292         0.3299           6.0106     0.1716
project_rules    575292         0.1962           1.0246     0.0871
tab_completion   575292         0.7196         250.9267     0.5551
terminal_ai      575292         0.2894           8.7197     0.1439
```

### `support_tickets` (A14) volume, chat volume and CSAT

```text
                 tickets  avg_chat_messages  avg_csat  escalation_rate
channel                                                               
community_forum     8379             2.4830    3.9612           0.1094
email              21295             2.4953    3.9694           0.1127
in_app_chat        29062             2.5002    3.9630           0.1112
phone               4365             2.5480    3.9533           0.1081

                     tickets  avg_csat
category                              
account_login           6964    3.9578
billing                10102    3.9446
feature_request         6280    3.9640
indexing_failure        8880    3.9791
integration             3805    3.9427
performance_latency    11917    3.9636
suggestion_quality     15153    3.9774

overall mean CSAT: 3.9643 (response rate 57.77%)
total chat messages: 157,725
```

### `crm_touches` by campaign, outcome and user state at touch

```text
             touches  delivered_rate  open_rate  click_rate  reactivation_rate   cost_usd
campaign_id                                                                              
CMP-001        82793          0.9600     0.3261      0.0923             0.0000 3,311.7200
CMP-002         6392          0.9953     0.6173      0.2664             0.0000    63.9200
CMP-003        44875          0.9602     0.3752      0.1606             0.0767 1,795.0000
CMP-004        96895          0.9951     0.6139      0.2724             0.0000   968.9500
CMP-005        58427          0.8803     0.3609      0.0774             0.0000 1,168.5400

                       touches
outcome                       
no_response             159116
engaged_no_conversion   123348
unsubscribed              3474
reactivated               3444

                     touches
user_state_at_touch         
active                131757
at_risk               112750
lapsed                 44875
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
retained  25253            5.3602               0.4387                 5.0731          20.5744                  1.0013               0.1112
churned   24747            2.1222               0.2752                 2.5614          11.7108                  0.9551               0.1753
```

### Monthly churn rate by coding-hours trend bucket

The core signal: churn rises steeply as the month-over-month coding-hours trend falls, from ~3% among growing users to a multiple of that among collapsing ones.

The highest `>1.25 (surging)` bucket is *not* the lowest-churn group, and that is expected rather than a defect: a large positive swing is usually a rebound off a very low prior month, so it mixes genuinely recovering users with erratic ones. The monotone part of the relationship is the decline side, which is what the churn model is meant to learn.

```text
                             user_months  churn_rate  avg_coding_hours  avg_acceptance_rate  avg_session_frequency
trend_bucket                                                                                                      
<=0.50 (collapsing)                 2300      0.7913            0.4732               0.1085                 0.9416
0.50-0.75 (steep decline)          39282      0.1097            2.4075               0.3073                 3.0151
0.75-0.90 (declining)             117600      0.0480            3.5693               0.3605                 3.8767
0.90-1.00 (flat/slight dip)       152021      0.0387            4.2633               0.3831                 4.2605
1.00-1.25 (growing)               203153      0.0308            4.8879               0.4032                 4.5999
>1.25 (surging)                    57492      0.0516            4.5859               0.3846                 4.1904
```

### Pearson correlation of each behavioural feature with the churn label

Negative = higher values of the feature go with *less* churn.

```text
                        pearson_r_with_churned
avg_coding_hours                       -0.1890
avg_acceptance_rate                    -0.2155
avg_session_frequency                  -0.1665
coding_hours_trend_30d                 -0.0953
active_days                            -0.4273
support_tickets_30d                     0.0641
features_adopted                       -0.0898
tenure_months                          -0.0392
```

## 8. Internal consistency checks

Run by `datagen.pipeline.validate` on the frames emitted above.

```text
referential integrity subscriptions.user_id -> users.user_id: OK
referential integrity usage_events.user_id -> users.user_id: OK
referential integrity feature_adoption.user_id -> users.user_id: OK
referential integrity support_tickets.user_id -> users.user_id: OK
referential integrity crm_touches.user_id -> users.user_id: OK
referential integrity churn_labels.user_id -> users.user_id: OK
referential integrity crm_touches.campaign_id -> crm_campaigns.campaign_id: OK
primary key users(user_id): OK
primary key subscriptions(subscription_id): OK
primary key usage_events(user_id, event_date): OK
primary key feature_adoption(user_id, feature_key, month_start): OK
primary key support_tickets(ticket_id): OK
primary key crm_campaigns(campaign_id): OK
primary key crm_touches(touch_id): OK
primary key churn_labels(user_id, month_start): OK
usage_events.event_date within window: OK
usage_events value ranges plausible: OK
monthly churn rate 0.0470 within +/-0.5pt of target 0.0470: OK
no usage_events after cancellation (non-reactivated users): OK
support_tickets.created_date inside an active subscription term: OK
reactivated touches (3444) == reactivation terms (3444): OK
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
churn_labels         6b073b863aa95bc707d516df6c044727a3ae0dae074efbf91219c93b2f707396
crm_campaigns        24a031ae365c958ae66b44d066a077fa0177b5a3dcc36487fa7dd1b3e25473ca
crm_touches          9829cc4d58c6eeade86f9903980615b80f61eb27cdb962673161bd67903b3954
feature_adoption     fe9ac946f06d8d49a0ac1eab497887a96efc1edcd5012a8e606033a443187409
subscriptions        723784b072ff962b50a7b0bb967877f59e1d5517b79322a940b62c829a82f659
support_tickets      0e8464f3d6f1292ce59803357c769b484b36bc3f541c90b821b28c3a9685f2a7
usage_events         26764634c6ffcf76640f8416537da463c8fdec2f924fa5585337fc0e5ade90cd
users                bf62382a8f43b3249f558e2e140026d64a747306ba9e4df9434bf1248631d5cf
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
users/part-00000.parquet                 5843e40bd2d410b59684f527ce612511028798a1d56e99cd5408ab17fb5fc740
subscriptions/part-00000.parquet         50a7000628abbbe2f28882aad5de521c78f658b035670c711eaa6c5a868a5ae1
usage_events/part-00000.parquet          de7783ec3bf261e558bf5ba7ab01182194cb209ec26946fce1e1ce684d52a45a
feature_adoption/part-00000.parquet      086a3be800d070ecab7a9b8acefa544dca549f66a83ccb9c9a79147d176de08f
support_tickets/part-00000.parquet       8268eb7557c433c9124cf71b6dd463150eec37aec30e03d3348f552ca5276cba
crm_campaigns/part-00000.parquet         1e3eb2239eb0cfeeeba89f2e962ee514086dd4d19606dcf974ddfb2c4ce906c6
crm_touches/part-00000.parquet           782ad6c875554f109591d12c4ecd05978ec48cbc00399ab1915e626bba1f7b39
churn_labels/part-00000.parquet          058f7416d9340d8c2e6660eae6835ae85dd517e7c2e5387ec8627524e8dbf01d
```

## 10. Output manifest (`_manifest.json`)

Written alongside the data. This is the handoff contract to the Lakeflow ingest stage (files + row counts) and the Unity Catalog stage (target catalog/schema + DDL file).

```json
{
  "generator_version": "0.1.0",
  "config": {
    "seed": 1729,
    "users_requested": 50000,
    "sample_frac": 1.0,
    "users_effective": 50000,
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
    "out_dir": "/tmp/fullrun"
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
      "rows": 50000,
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
      "bytes": 678126
    },
    {
      "table": "subscriptions",
      "asset": "A03 \u2014 subscription plans & billing history",
      "layer": "bronze",
      "grain": "one row per subscription term (a plan a user held for a period)",
      "rows": 54557,
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
      "bytes": 1164691
    },
    {
      "table": "usage_events",
      "asset": "A06 \u2014 raw product usage events & telemetry",
      "layer": "bronze",
      "grain": "one row per user per ACTIVE day (inactive days are not emitted)",
      "rows": 10778146,
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
      "bytes": 132670475
    },
    {
      "table": "feature_adoption",
      "asset": "A07 \u2014 feature adoption & activation metrics",
      "layer": "bronze",
      "grain": "one row per user per feature per month",
      "rows": 3451752,
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
      "bytes": 14220701
    },
    {
      "table": "support_tickets",
      "asset": "A14 \u2014 support tickets, chat logs & CSAT",
      "layer": "bronze",
      "grain": "one row per support ticket",
      "rows": 63101,
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
      "bytes": 1109475
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
      "rows": 289382,
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
      "bytes": 2698943
    },
    {
      "table": "churn_labels",
      "asset": "derived label (gold) \u2014 supervised training target",
      "layer": "gold",
      "grain": "one row per user per month the user was a subscriber at month start",
      "rows": 571848,
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
      "bytes": 7026369
    }
  ],
  "total_rows": 15258791
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
| population | 0.324 |
| lifecycle | 9.882 |
| usage_events | 16.299 |
| users | 0.026 |
| subscriptions | 4.146 |
| feature_adoption | 5.097 |
| support_tickets | 0.139 |
| crm_campaigns | 0.002 |
| crm_touches | 0.405 |
| churn_labels | 1.291 |
| conform | 13.546 |

### Console log

Captured verbatim from the generator's stderr logger. Timestamps are wall-clock and therefore differ per run.

```console
2026-09-08 19:50:36,235 INFO    datagen | datagen starting | seed=1729 users_requested=50000 sample_frac=1.0 users_effective=50000 months=18 window_start=2025-03-01 window_end=2026-08-31 days=549 target_monthly_churn_rate=0.047 target_reactivation_rate=0.08 power_user_bar=>=4.0 coding hours/day on >=5 days/week campaigns=5 output_format=parquet partitioned=False out_dir=/tmp/fullrun
2026-09-08 19:50:36,236 INFO    datagen | building population: 50000 users, 18 months (2025-03-01 .. 2026-08-31)
2026-09-08 19:50:36,559 INFO    datagen | simulating subscription lifecycle + CRM (calibrating churn hazard)
2026-09-08 19:50:46,442 INFO    datagen | hazard intercept calibrated to -2.21875 in 9 iterations -> monthly churn 0.0470 (target 0.0470)
2026-09-08 19:50:46,442 INFO    datagen | generating usage_events (active days only)
2026-09-08 19:51:02,741 INFO    datagen | usage_events: 10,778,146 rows
2026-09-08 19:51:27,394 INFO    datagen | users                  50,000 rows
2026-09-08 19:51:27,395 INFO    datagen | subscriptions          54,557 rows
2026-09-08 19:51:27,395 INFO    datagen | usage_events       10,778,146 rows
2026-09-08 19:51:27,395 INFO    datagen | feature_adoption    3,451,752 rows
2026-09-08 19:51:27,395 INFO    datagen | support_tickets        63,101 rows
2026-09-08 19:51:27,395 INFO    datagen | crm_campaigns               5 rows
2026-09-08 19:51:27,395 INFO    datagen | crm_touches           289,382 rows
2026-09-08 19:51:27,395 INFO    datagen | churn_labels          571,848 rows
2026-09-08 19:51:27,496 INFO    datagen.writer | wrote users                  50,000 rows -> 1 file(s)
2026-09-08 19:51:27,565 INFO    datagen.writer | wrote subscriptions          54,557 rows -> 1 file(s)
2026-09-08 19:51:31,673 INFO    datagen.writer | wrote usage_events       10,778,146 rows -> 1 file(s)
2026-09-08 19:51:34,896 INFO    datagen.writer | wrote feature_adoption    3,451,752 rows -> 1 file(s)
2026-09-08 19:51:34,957 INFO    datagen.writer | wrote support_tickets        63,101 rows -> 1 file(s)
2026-09-08 19:51:34,959 INFO    datagen.writer | wrote crm_campaigns               5 rows -> 1 file(s)
2026-09-08 19:51:35,272 INFO    datagen.writer | wrote crm_touches           289,382 rows -> 1 file(s)
2026-09-08 19:51:35,514 INFO    datagen.writer | wrote churn_labels          571,848 rows -> 1 file(s)
2026-09-08 19:51:35,515 INFO    datagen.writer | wrote manifest -> /tmp/fullrun/_manifest.json
2026-09-08 19:51:35,516 INFO    datagen.writer | wrote Unity Catalog DDL -> /tmp/fullrun/_unity_catalog.sql
2026-09-08 19:51:43,863 INFO    datagen | check: referential integrity subscriptions.user_id -> users.user_id: OK
2026-09-08 19:51:43,863 INFO    datagen | check: referential integrity usage_events.user_id -> users.user_id: OK
2026-09-08 19:51:43,863 INFO    datagen | check: referential integrity feature_adoption.user_id -> users.user_id: OK
2026-09-08 19:51:43,863 INFO    datagen | check: referential integrity support_tickets.user_id -> users.user_id: OK
2026-09-08 19:51:43,863 INFO    datagen | check: referential integrity crm_touches.user_id -> users.user_id: OK
2026-09-08 19:51:43,863 INFO    datagen | check: referential integrity churn_labels.user_id -> users.user_id: OK
2026-09-08 19:51:43,863 INFO    datagen | check: referential integrity crm_touches.campaign_id -> crm_campaigns.campaign_id: OK
2026-09-08 19:51:43,863 INFO    datagen | check: primary key users(user_id): OK
2026-09-08 19:51:43,863 INFO    datagen | check: primary key subscriptions(subscription_id): OK
2026-09-08 19:51:43,864 INFO    datagen | check: primary key usage_events(user_id, event_date): OK
2026-09-08 19:51:43,864 INFO    datagen | check: primary key feature_adoption(user_id, feature_key, month_start): OK
2026-09-08 19:51:43,864 INFO    datagen | check: primary key support_tickets(ticket_id): OK
2026-09-08 19:51:43,864 INFO    datagen | check: primary key crm_campaigns(campaign_id): OK
2026-09-08 19:51:43,864 INFO    datagen | check: primary key crm_touches(touch_id): OK
2026-09-08 19:51:43,864 INFO    datagen | check: primary key churn_labels(user_id, month_start): OK
2026-09-08 19:51:43,864 INFO    datagen | check: usage_events.event_date within window: OK
2026-09-08 19:51:43,864 INFO    datagen | check: usage_events value ranges plausible: OK
2026-09-08 19:51:43,864 INFO    datagen | check: monthly churn rate 0.0470 within +/-0.5pt of target 0.0470: OK
2026-09-08 19:51:43,864 INFO    datagen | check: no usage_events after cancellation (non-reactivated users): OK
2026-09-08 19:51:43,864 INFO    datagen | check: support_tickets.created_date inside an active subscription term: OK
2026-09-08 19:51:43,864 INFO    datagen | check: reactivated touches (3444) == reactivation terms (3444): OK
2026-09-08 19:51:43,864 INFO    datagen | check: reactivations per user <= MAX_REACTIVATIONS (1); observed max 1: OK
2026-09-08 19:51:43,864 INFO    datagen | check: churn_labels.churn_date set whenever churned: OK
2026-09-08 19:51:43,864 INFO    datagen | monthly churn rate: 0.0470 (target 0.0470) | users 50,000 | usage_events 10,778,146 rows
2026-09-08 19:51:43,865 INFO    datagen | churn detail: 26876 churn events / 571848 at-risk user-months = 0.046999
2026-09-08 19:51:43,865 INFO    datagen | datagen finished | total rows 15,258,791
```

---

*Generated by `src/datagen`. Synthetic data only — no real customer data.
Reproduce with the command at the top of this file.*
