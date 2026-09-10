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

## Benchmark eval run (2026-09-10)

Space **"Subscription Churn Analytics"** — `space_id 01f1ad360e121f099e3070de938cd8cb`,
warehouse `128c306447d9ef00`. Ran the 10 benchmarks ([`../genie/benchmarks.md`](../genie/benchmarks.md))
in the workspace. Latest run `01f1ad605bf31c8d97f5240eaa0e3c31`:

**Score: 4 GOOD / 5 NEEDS_REVIEW / 1 BAD (4/10 correct).**

| # | Question | Verdict | Judge reason | Genie's generated SQL |
| --- | --- | --- | --- | --- |
| 1 | latest churn rate | NEEDS_REVIEW | INCORRECT_METRIC_CALCULATION | raw `AVG(CAST(churned AS INT))` on `silver.churn_labels` |
| 2 | churn trend MoM | NEEDS_REVIEW | INCORRECT_METRIC_CALCULATION | raw `churn_labels`, extra cols (at_risk/churned counts) |
| 3 | users per band | GOOD | — | raw `churn_predictions` COUNT by band |
| 4 | MRR at risk | GOOD | — | raw join `SUM(mrr_usd) WHERE is_currently_subscribed` |
| 5 | regions highest churn | NEEDS_REVIEW | INCORRECT_TABLE_OR_FIELD_USAGE | raw `churn_labels` (latest-month filter) |
| 6 | most at-risk subscribers | BAD | RESULT_MISSING_COLUMNS, MISSING_OR_INCORRECT_FILTER | answered the *wrong question* — a COUNT/SUM of untouched high-risk, not a ranked list |
| 7 | no CRM outreach 30d | GOOD | — | called `untouched_at_risk_users('high')` ✓ |
| 8 | declining coding by band | NEEDS_REVIEW | INCORRECT_TABLE_OR_FIELD_USAGE | raw join, extra cols |
| 9 | power users vs risk | NEEDS_REVIEW | INCORRECT_TABLE_OR_FIELD_USAGE | raw join, extra cols |
| 10 | total MRR subscribed | GOOD | — | raw `SUM(mrr_usd) WHERE is_currently_subscribed` |

**Root cause:** Genie is **not using the metric views or functions** — it hand-rolls
raw SQL against the base/gold tables. Where the raw result happens to match the
expected shape/values it passes (Q3/Q4/Q10), but the LLM judge flags the method as
incorrect metric calculation / table usage everywhere the expected answer used
`MEASURE()` (Q1/Q2/Q5/Q8/Q9). Q7 is the one metric-layer win — Genie called the
trusted function. Q6 is a genuine miss: Genie misread "most at-risk subscribers" and
answered the CRM-outreach question instead.

Two contributing factors: (a) the metric views/functions may not be wired into the
space as data sources / trusted assets — if they aren't registered, Genie can't route
to them; (b) the space's example queries ([`../genie/example_queries.sql`](../genie/example_queries.sql))
are the **raw-SQL** forms, which actively teach Genie to imitate raw-table SQL — in
direct conflict with the metric-view expected answers.

## Proposed follow-ups (NOT yet applied — pending review)

1. **Wire the ontology into the space** (highest leverage): add `churn_metrics_current`
   and `churn_metrics_monthly` as data sources / metrics, and register `at_risk_users`
   + `untouched_at_risk_users` as trusted assets. The objects exist in UC but Genie
   isn't routing to them.
2. **Replace the space's example queries with the metric-view forms** (from
   `benchmarks.md`) so examples and expected answers agree — the raw-SQL examples are
   teaching the wrong pattern.
3. **Fix Q6**: reword to an unambiguous ranked-list ask ("List the subscribers most
   likely to churn, highest score first") and register `at_risk_users` so Genie routes
   to it; reconsider the `0.9` threshold in the expected answer vs. a top-N ordering.
4. **Decide grading intent**: if "correct numbers" is enough, the NEEDS_REVIEW raw-SQL
   answers (Q1/Q2/Q5) are arguably fine and could be manually accepted; if "use the
   certified semantic layer" is the bar, keep them failing until fix #1/#2 land. The
   score is a proxy for *"is Genie using the governed ontology,"* which is the point of
   Stage 5 — so #1/#2 are the real fix, not relaxing the benchmark.
5. Minor: instruct Genie to return only the requested measure + grouping (Q2/Q8/Q9
   lost points partly for extra columns).

Re-run the eval after #1/#2 to confirm the lift, then version the space back
(`databricks genie get-space <id>` — note this workspace's `get-space` returns only
summary fields, not a `serialized_space` blob).

## Access / grants (per-stage model)

Genie executes as the asking user against the warehouse, so it grants no privilege of
its own — a user sees only what UC already permits. The per-stage grant is `SELECT` on
the three scoped tables to the analyst group / Genie consumer SP when that principal
exists; deliberately no blanket grant.
