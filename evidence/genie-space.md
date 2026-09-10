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
