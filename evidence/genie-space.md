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

## Benchmark eval run — baseline, before ontology wiring (2026-09-10)

Space **"Subscription Churn Analytics"** — `space_id 01f1ad360e121f099e3070de938cd8cb`,
warehouse `128c306447d9ef00`. Ran the 10 benchmarks ([`../genie/benchmarks.md`](../genie/benchmarks.md))
in the workspace. Run `01f1ad605bf31c8d97f5240eaa0e3c31` — this is the **baseline
taken before the fixes below were applied**:

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

## Fixes applied (2026-09-10, after the baseline run)

Applied in the live space by the Genie space editor and mirrored back to the repo;
confirmed via `genie get-space <id> --include-serialized-space`:

1. ✅ **Ontology wired into the space.** Both metric views (`churn_metrics_current`,
   `churn_metrics_monthly`) are now registered **data sources**, and both functions
   (`at_risk_users`, `untouched_at_risk_users`) are registered **trusted assets** —
   so Genie can route to them (baseline root cause was that it couldn't).
2. ✅ **Example queries moved to metric-view / function forms.** 5 curated examples
   (Q1, Q2, Q5, declining-engagement, power-users) now use `MEASURE()`; the raw-SQL
   examples that were teaching the wrong pattern are gone. Synced verbatim to
   [`../genie/example_queries.sql`](../genie/example_queries.sql) (11 queries).
3. ✅ **New example for Q6** — "Who are our most at-risk subscribers?" →
   `SELECT * FROM dev_churn.gold.at_risk_users(0.9)`.
4. ✅ Join spec de-duplicated (kept the named "Predictions to serving" one); entity
   matching enabled on `Geo` (+ format assistance across columns).

## Benchmark tuning rounds + the 9/10 ceiling (2026-09-10)

After the ontology wiring, several more rounds ran. Score progression across runs:
**4 → 6 → 8 → 8 → 7 → 9 → 9**. Pulling each run's per-question detail
(`genie-get-eval-result-details`) showed every remaining miss was a **benchmark
expected-answer bug**, not a Genie/ontology defect — and that **Genie-code's
auto-fixer had been mutating the expected answers to chase whatever Genie generated
on a given run**, leaving them contradictory with the questions/instructions. Fixes
applied to the live space via `genie update-space` (full serialized_space replacement
with etag), pulling the current space first so the 4 prior rounds were preserved:

- **Q8** expected filtered `WHERE Risk band IN ('high','low')` (2 bands) while the
  question asks to compare "across churn risk bands" → changed expected to all bands;
  also reworded the question band-agnostic. Now passes.
- **Q6 / Q7** expected answers carried `ROUND(churn_score,3)` / `ROUND(coding_hours_trend,2)`,
  which fought a "return raw numeric values, no ROUND()" instruction and Genie's raw
  output → stripped ROUND from the expected answers.
- **Q7** expected had an arbitrary `LIMIT 50` while "which subscribers" means all →
  removed the LIMIT; added a "list questions return all rows, no LIMIT unless a top-N
  is asked" instruction.

**The ceiling is LLM non-determinism, not a bug.** Every run now scores **9/10**, but
*which* row-level question fails rotates between **Q6 and Q7**: Genie
non-deterministically wraps `churn_score` / `coding_hours_trend` in `ROUND()` (and
occasionally adds a `LIMIT`) on those two list questions — on runs where it rounds,
exact-match grading fails the formatting; on runs where it doesn't, it passes. The
expected answers are now correct and internally consistent; the remaining gap is that
Genie doesn't deterministically obey the no-ROUND instruction. Genie's *answer is
analytically correct every run* — the only difference is display rounding
(e.g. `0.998` vs `0.9987`).

## Recommendation (at 9/10 — grading-philosophy call, not more tuning)

Chasing 10/10 by re-tuning is whack-a-mole against a stochastic generator (it's what
put the expected answers in a contradictory state to begin with). Options, best first:

1. **Accept the correct-but-rounded answers via manual review.** The eval result
   carries a `manual_assessment` field; mark the rounded Q6/Q7 answers as acceptable.
   This records a true 10/10 without pretending Genie is deterministic.
2. **Treat 9/10 as effectively passing** with this cosmetic-rounding flake documented
   — the substance (ontology usage, correct results) is there on all 10.
3. **Numeric-format-tolerant judge**, if/when the platform exposes that — the right
   long-term fix, since exact-value matching is too brittle for a stochastic SQL
   generator on cosmetic formatting.

Not recommended: putting `ROUND()` back into the expected answers — Genie rounds only
*some* runs, so no single expected answer (raw or rounded) matches both variants.

## Repo sync status

The repo's `genie/benchmarks.md` + `example_queries.sql` + `instructions.md` still
reflect the pre-Genie-code metric-view answer forms plus two targeted edits
(no-ROUND rule, Q8 reword). They have **not** been fully re-synced to the live space's
current (Genie-code-mutated + hand-corrected) benchmark answers, since that state is
still in flux pending the grading-philosophy decision above. Full re-sync
(`genie get-space <id> --include-serialized-space` → repo) should happen once the
benchmark set is finalized/accepted.

## Access / grants (per-stage model)

Genie executes as the asking user against the warehouse, so it grants no privilege of
its own — a user sees only what UC already permits. The per-stage grant is `SELECT` on
the three scoped tables to the analyst group / Genie consumer SP when that principal
exists; deliberately no blanket grant.
