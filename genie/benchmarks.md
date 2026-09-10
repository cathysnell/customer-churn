# Genie space — benchmarks (accuracy eval harness)

Benchmarks are question → expected-SQL pairs that act as **unit tests** for the Genie
space: they verify Genie generates correct SQL and catch regressions when you change
instructions, metric views, or trusted assets. This is the Genie analogue of the
pytest suite the rest of the repo uses.

Each answer below is the **metric-view / function form** — what a well-curated space
should resolve to — and every one was **executed live on the workspace 2026-09-10**
(warehouse `128c306447d9ef00`); the "Expected result" is the actual output. The space's
curated examples in [`example_queries.sql`](example_queries.sql) use the same
metric-view / function forms (synced from the live space). Genie's *generated* SQL is
graded against the result of the answer SQL,
so the answer just has to run and return the right rows — it need not match Genie's
phrasing.

## Summary

| # | Question | Answer form | Expected result (validated) |
|---|---|---|---|
| 1 | What is the latest monthly churn rate? | `Churn rate` measure, latest month | **0.0325** |
| 2 | How has churn trended month over month? | `Churn rate` by `Month` | 18 months, 0.0556 → 0.0325 (declining) |
| 3 | How many users are in each churn risk band? | `Users` by `Risk band` | low 23,353 · high 20,581 · medium 6,066 |
| 4 | How much MRR is at risk from high-risk subscribers? | `MRR at risk` by `Risk band` | high **$36,568** (low 446,184 · med 58,736) |
| 5 | Which regions have the highest churn? | `Churn rate` by `Geo`, latest month | LATAM 0.0399 (highest) → ANZ 0.0306 |
| 6 | Who are our most at-risk subscribers? | `at_risk_users(0.9)` | 357 users, score ≥ 0.9 |
| 7 | Which high-risk subscribers have had no CRM outreach in 30 days? | `untouched_at_risk_users('high')` | **1,004** users |
| 8 | Do high-risk users show declining coding hours vs low-risk? | `Avg coding hours trend` by `Risk band` | high 0.91 · med 0.98 · low 1.02 |
| 9 | Are power users less likely to be high risk? | `Avg churn score` by `Is power user` | power 0.058 vs non-power 0.573 |
| 10 | What is the total MRR of currently-subscribed users? | `MRR at risk` measure (ungrouped) | **$541,488** |

> Consistency checks: Q4 bands sum to Q10 ($446,184 + 58,736 + 36,568 = $541,488);
> Q3 bands sum to the full 50,000-user base. `MRR at risk` is MRR of
> *currently-subscribed* users (the measure filters on `is_currently_subscribed`),
> so Q4/Q10 are subscribed-only while Q3 `Users` counts the whole base.

## Answer SQL (validated 2026-09-10)

**1 — Latest monthly churn rate** → `2026-08-01 | 0.0325`
```sql
SELECT `Month`, MEASURE(`Churn rate`) AS churn_rate
FROM dev_churn.gold.churn_metrics_monthly
GROUP BY `Month`
ORDER BY `Month` DESC
LIMIT 1;
```

**2 — Churn trend month over month** → 18 rows, 0.0556 (2025-03) → 0.0325 (2026-08)
```sql
SELECT `Month`, MEASURE(`Churn rate`) AS churn_rate
FROM dev_churn.gold.churn_metrics_monthly
GROUP BY `Month`
ORDER BY `Month`;
```

**3 — Users per risk band** → low 23,353 · high 20,581 · medium 6,066
```sql
SELECT `Risk band`, MEASURE(`Users`) AS users
FROM dev_churn.gold.churn_metrics_current
GROUP BY `Risk band`
ORDER BY users DESC;
```

**4 — MRR at risk by band** → high $36,568 · medium $58,736 · low $446,184
```sql
SELECT `Risk band`, MEASURE(`MRR at risk`) AS mrr_at_risk
FROM dev_churn.gold.churn_metrics_current
GROUP BY `Risk band`
ORDER BY mrr_at_risk DESC;
```

**5 — Regions with highest churn (latest month)** → LATAM 0.0399 (highest) … ANZ 0.0306
```sql
SELECT `Geo`, MEASURE(`Churn rate`) AS churn_rate
FROM dev_churn.gold.churn_metrics_monthly
WHERE `Month` = (SELECT MAX(`Month`) FROM dev_churn.gold.churn_metrics_monthly)
GROUP BY `Geo`
ORDER BY churn_rate DESC;
```

**6 — Most at-risk subscribers** → 357 users with `churn_score` ≥ 0.9
```sql
SELECT * FROM dev_churn.gold.at_risk_users(0.9);
```

**7 — High-risk subscribers with no CRM outreach in 30 days** → 1,004 users
```sql
SELECT * FROM dev_churn.gold.untouched_at_risk_users('high');
```

**8 — Declining coding hours by risk band** → high 0.91 · medium 0.98 · low 1.02
```sql
SELECT `Risk band`, MEASURE(`Avg coding hours trend`) AS avg_coding_trend
FROM dev_churn.gold.churn_metrics_current
GROUP BY `Risk band`
ORDER BY avg_coding_trend;
```

**9 — Power users vs churn risk** → power users 0.058 vs non-power 0.573
```sql
SELECT `Is power user`, MEASURE(`Avg churn score`) AS avg_churn_score
FROM dev_churn.gold.churn_metrics_current
GROUP BY `Is power user`;
```

**10 — Total MRR of currently-subscribed users** → $541,488
```sql
SELECT MEASURE(`MRR at risk`) AS total_mrr
FROM dev_churn.gold.churn_metrics_current;
```

## Add + run

1. In the space, open **Benchmarks** and add each row (question + its answer SQL
   above). Editors can also **save a good chat answer as a benchmark** directly from a
   conversation.
2. Run an evaluation from the CLI (the space id is in the space URL):

   ```bash
   databricks genie genie-create-eval-run <space_id> \
     -p fevm-serverless-stable-yuzk83 --json '{"benchmark_ids": [...]}'
   databricks genie genie-list-eval-results <space_id> <eval_run_id> \
     -p fevm-serverless-stable-yuzk83
   ```

3. Record the accuracy score in [`../evidence/genie-space.md`](../evidence/genie-space.md).
   Re-run after any instruction/metric-view change to catch regressions.

> Note: the eval CLI (`genie-create-eval-run`, `genie-list-eval-runs`,
> `genie-list-eval-results`) is present on this workspace (Beta). The exact
> benchmark-creation payload is space-specific; add benchmarks in the UI first, then
> reference their ids in the eval run.
