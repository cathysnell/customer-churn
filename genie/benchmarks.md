# Genie space — benchmarks (accuracy eval harness)

Benchmarks are question → expected-SQL pairs that act as **unit tests** for the Genie
space: they verify Genie generates correct SQL and catch regressions when you change
instructions, metric views, or trusted assets. This is the Genie analogue of the
pytest suite the rest of the repo uses.

## The benchmark set

Each question below pairs with a verified query — the metric-view / function form is
preferred (it's what a well-curated space should resolve to), with the raw-SQL
equivalent in [`example_queries.sql`](example_queries.sql) as the fallback.

| # | Question | Expected logic |
|---|---|---|
| 1 | What is the latest monthly churn rate? | `MEASURE(\`Churn rate\`)` on `churn_metrics_monthly`, latest `Month` → **~0.0325** |
| 2 | How has churn trended month over month? | `Churn rate` by `Month` on `churn_metrics_monthly` |
| 3 | How many users are in each churn risk band? | `Users` by `Risk band` on `churn_metrics_current` |
| 4 | How much MRR is at risk from high-risk subscribers? | `MRR at risk` by `Risk band` on `churn_metrics_current` → high **~$36.6K** |
| 5 | Which regions have the highest churn? | `Churn rate` by `Geo`, latest `Month`, `churn_metrics_monthly` |
| 6 | Who are our most at-risk subscribers? | `at_risk_users(0.9)` |
| 7 | Which high-risk subscribers have had no CRM outreach in 30 days? | `untouched_at_risk_users('high')` → **~1004** |
| 8 | Do high-risk users show declining coding hours vs low-risk? | `Avg coding hours trend` by `Risk band` on `churn_metrics_current` |
| 9 | Are power users less likely to be high risk? | `Avg churn score` by `Is power user` on `churn_metrics_current` |
| 10 | What is the total MRR of currently-subscribed users? | `MEASURE(\`MRR at risk\`)` (subscribed) on `churn_metrics_current` |

## Add + run

1. In the space, open **Benchmarks** and add each row (question + its expected SQL).
   Editors can also **save a good chat answer as a benchmark** directly from a
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
