# Genie space — execution evidence (Stage 5)

Evidence for the Stage-5 gate (natural-language querying over the governed data). The
Genie space itself is a UI-authored asset (see [`../genie/README.md`](../genie/README.md));
what's verifiable in text is that the space's **curated/trusted SQL runs correctly on
the governed tables and returns sensible answers**. All queries in
[`../genie/example_queries.sql`](../genie/example_queries.sql) were executed on the
`fevm-serverless-stable-yuzk83` SQL warehouse (`128c306447d9ef00`), 2026-09-10.

## Scope

Three governed tables: `dev_churn.gold.churn_serving`, `dev_churn.gold.churn_predictions`,
`dev_churn.silver.churn_labels`. Join key `user_id`.

## Validated answers (the demo script)

**Latest monthly churn rate** — `3.25%` (matches the model's validation base rate).

**Risk bands, currently-subscribed users — MRR at risk:**
```
band     users    mrr_at_risk
low      21798    $446,184
medium    2921     $58,736
high      1849     $36,568
```

**Engagement by risk band** (the decline signal holds — high risk = falling coding
hours + lower AI-acceptance):
```
band     coding_hours_trend_30d   avg_acceptance_rate
high             0.91                    0.247
medium           0.98                    0.296
low              1.02                    0.463
```

**High-risk, currently-subscribed users with zero CRM touch in 30 days:** `1,004`
— the actionable gap the retention play closes.

Every curated query returned without error, confirming the joins and the business
definitions in [`../genie/instructions.md`](../genie/instructions.md) resolve against
the deployed schema.

## Semantic layer / ontology — deployed & verified (2026-09-10)

Following Databricks' curation hierarchy (prose instructions last), the semantics were
pushed into structural governed layers. All created and verified live on
`fevm-serverless-stable-yuzk83`:

| Object | Type | Verified |
| --- | --- | --- |
| `dev_churn.gold.churn_metrics_current` | metric view (serving ⋈ predictions) | `MEASURE(MRR at risk)` by band = high $36,568 / med $58,736 / low $446,184 (matches raw SQL) |
| `dev_churn.gold.churn_metrics_monthly` | metric view (churn_labels) | `MEASURE(Churn rate)` latest month = 0.0325 |
| `dev_churn.gold.at_risk_users(min_score)` | trusted function | `at_risk_users(0.95)` returns subscribed users ≥ 0.95, score desc |
| `dev_churn.gold.untouched_at_risk_users(band)` | trusted function | `untouched_at_risk_users('high')` = 1004 |
| `churn_predictions_user_fk` | FK → `churn_serving(user_id)` | present in `information_schema.table_constraints`; baked into `ml/score_churn.py` so it survives re-scoring |

`instructions.md` was correspondingly slimmed to the qualitative caveat
(`churn_score` is a ranking, not a probability) plus a pointer to these objects.
Two bring-up notes: a SQL function's `LIMIT` must be constant and a param can't be
referenced in a `QUALIFY` window filter, so the top-N function was recast as a
score-threshold function `at_risk_users(min_score)`; UC functions must be created one
statement per SQL-API call.

## Pending (workspace write, on approval)

Create the space in the UI on warehouse `128c306447d9ef00`, load the instructions +
the 10 trusted queries + the sample-question chips, then (optionally) run a Genie
benchmark over the sample questions. Once created, version it back with
`databricks genie get-space <id>` and record the space id + benchmark score here.

## Access / grants (per-stage model)

Genie executes as the asking user against the warehouse, so it grants no privilege of
its own — a user sees only what UC already permits. The per-stage grant is `SELECT` on
the three scoped tables to the analyst group / Genie consumer SP when that principal
exists; deliberately no blanket grant.
