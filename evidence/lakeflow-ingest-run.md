# Lakeflow ingestion — execution evidence (Stage 1)

Text evidence that the `metadata_ingest` ETL (Declarative) pipeline ran end to end
on `fevm-serverless-stable-yuzk83` and materialised all 8 sources through
bronze → silver. Captured 2026-09-09 via the SQL warehouse against the live tables.

- **Pipeline:** `metadata_ingest` (id `f844d3f8-6f68-49ae-8e4d-ccc947448293`)
- **Latest update:** `4ba1cb66` — state **COMPLETED**
- **Catalog / schemas:** `dev_churn` → `bronze` (raw) + `silver` (typed + quality-checked)
- **Ownership:** `usage_events` is owned by this pipeline; the standalone
  `usage_events_ingest` pipeline is retired (definitions commented out).

## Silver row counts

| Table | Rows |
| --- | ---: |
| users | 50,000 |
| subscriptions | 54,557 |
| usage_events | 10,778,146 |
| feature_adoption | 3,451,752 |
| support_tickets | 63,101 |
| crm_campaigns | 5 |
| crm_touches | 289,382 |
| churn_labels | 571,848 |

These match the full-scale generator run (seed 1729): 50,000 Pro users × 18 months.

## Data-quality expectations (from the pipeline event log)

Every expectation on every table, with passed / failed record counts:

| Dataset (silver) | Expectation | Passed | Failed |
| --- | --- | ---: | ---: |
| users | valid_user | 50,000 | 0 |
| users | valid_geo | 50,000 | 0 |
| users | valid_tier | 50,000 | 0 |
| subscriptions | valid_subscription | 54,557 | 0 |
| subscriptions | valid_mrr | 54,557 | 0 |
| subscriptions | valid_billing | 54,557 | 0 |
| usage_events | valid_user | 10,778,146 | 0 |
| usage_events | valid_hours | 10,778,146 | 0 |
| usage_events | valid_accept | 10,778,146 | 0 |
| feature_adoption | valid_user | 3,451,752 | 0 |
| feature_adoption | valid_depth | 3,451,752 | 0 |
| feature_adoption | valid_active_days | 3,451,752 | 0 |
| support_tickets | valid_ticket | 63,101 | 0 |
| support_tickets | valid_resolution | 63,101 | 0 |
| support_tickets | valid_csat | 36,454 | 26,647 |
| crm_campaigns | valid_campaign | 5 | 0 |
| crm_campaigns | valid_budget | 5 | 0 |
| crm_campaigns | valid_objective | 5 | 0 |
| crm_touches | valid_touch | 289,382 | 0 |
| crm_touches | valid_outcome | 289,382 | 0 |
| crm_touches | valid_cost | 289,382 | 0 |
| churn_labels | valid_user | 571,848 | 0 |
| churn_labels | valid_tenure | 571,848 | 0 |

**Note on `support_tickets.valid_csat` (26,647 flagged):** `csat_score` is NULL for
unanswered tickets, and this runtime counts a NULL expectation predicate as a
violation. `valid_csat` is a warn-only (`expect_keep`) rule, so those rows are
**kept**, not dropped — the count reflects legitimately-missing survey responses,
not bad data. Follow-up: make the rule NULL-tolerant
(`csat_score IS NULL OR csat_score BETWEEN 1 AND 5`) so unanswered tickets don't
register as violations.

## Silver `head()` — `dev_churn.silver.usage_events`

```
user_id      | event_date | coding_hours | ai_acceptance_rate | session_frequency | geo
USR-00000001 | 2026-07-25 | 0.429        | 0.4615             | 1                 | APAC
USR-00000009 | 2026-07-25 | 3.515        | 0.5852             | 11                | EMEA
USR-00000011 | 2026-07-25 | 9.123        | 0.6544             | 6                 | EMEA
USR-00000017 | 2026-07-25 | 1.366        | 0.3                | 2                 | EMEA
USR-00000021 | 2026-07-25 | 6.022        | 0.7644             | 2                 | LATAM
```

## Signal sanity check

`AVG(churned)` over `churn_labels` (one row per at-risk user-month) is the monthly
churn rate directly:

```
monthly_churn_rate = 0.047   over 571,848 at-risk user-months
```

4.7% — matches the generator's calibrated target, confirming the churn signal
survived ingestion intact.
