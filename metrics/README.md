# Metric views — certified semantic layer

Unity Catalog **metric views** for the churn demo. A metric view declares `dimensions`
and `measures` in YAML over a source query; the measures compile to consistent SQL at
runtime, so every consumer (Genie, dashboards, the Stage-6 app) gets the *same*
certified numbers instead of re-deriving joins and aggregations. Query with `MEASURE()`:

```sql
SELECT `Risk band`, MEASURE(`MRR at risk`) AS mrr
FROM dev_churn.gold.churn_metrics_current GROUP BY `Risk band`;
```

| View | Grain | Use for |
| --- | --- | --- |
| [`churn_metrics_current.sql`](churn_metrics_current.sql) → `dev_churn.gold.churn_metrics_current` | one row / user (serving ⋈ predictions) | risk bands, MRR at risk, engagement by segment |
| [`churn_metrics_monthly.sql`](churn_metrics_monthly.sql) → `dev_churn.gold.churn_metrics_monthly` | one row / user / month (churn_labels) | churn rate + trends over time, by region |

Two views because the grains differ (current per-user vs monthly). Deploy each on a
SQL warehouse (`CREATE OR REPLACE VIEW … WITH METRICS LANGUAGE YAML …`); syntax
verified on `fevm-serverless-stable-yuzk83` (2026-09-10). They back the Stage-5 Genie
space — see [`../genie/README.md`](../genie/README.md).
