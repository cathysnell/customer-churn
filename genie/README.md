# Stage 5 — Ask (Genie space)

A **Genie space** that lets a business user ask churn questions in natural language
over the governed `dev_churn` tables — no SQL required. It reads the same governed
gold/silver layer the app and CRM trigger use, so answers are consistent with the
model and the serving store. Architecture: [`../docs/architecture.md`](../docs/architecture.md).

```
dev_churn.silver.churn_labels  ┐
dev_churn.gold.churn_serving   ├─►  Genie space  ─►  NL question → SQL → answer
dev_churn.gold.churn_predictions┘      (this stage)
```

## Tables in scope

| Table | Grain | Use for |
| --- | --- | --- |
| `dev_churn.gold.churn_serving` | one row / user (current) | who / how many / how much about the current base |
| `dev_churn.gold.churn_predictions` | one row / user | model risk score + band (join on `user_id`) |
| `dev_churn.silver.churn_labels` | one row / user / month | churn rate + trends over time |

Keep the scope tight — Genie answers better with a few well-described tables than with
the whole catalog. The silver source tables (users, subscriptions, usage_events, …)
stay out of scope; their signal is already rolled up into the three above.

## Contents (the analyst-authored parts)

| File | Where it goes in the space |
| --- | --- |
| [`instructions.md`](instructions.md) | **Instructions** — business definitions, the `churn_score`-is-a-ranking caveat, and the join rules |
| [`example_queries.sql`](example_queries.sql) | **SQL queries** — 10 curated/"trusted" queries that teach Genie the joins; validated live 2026-09-10 |
| [`sample_questions.md`](sample_questions.md) | **Sample questions** — starter chips + a demo flow, with verified answers |

## Create the space (requires approval — workspace write)

Genie spaces are UI-authored; the CLI `create-space` takes a `serialized_space` blob
you obtain by exporting an existing space (`databricks genie get-space <id>` →
`serialized_space`), so the first space is built in the UI:

1. **New → Genie space**, on a Pro/Serverless SQL warehouse (Databricks Assistant must
   be enabled). Demo warehouse id: `128c306447d9ef00`.
2. Add the three tables above as data sources.
3. Paste [`instructions.md`](instructions.md) into **Instructions**.
4. Add each query in [`example_queries.sql`](example_queries.sql) as an example/trusted
   SQL query, using its `-- Q:` line as the title.
5. Add the [`sample_questions.md`](sample_questions.md) chips.
6. (Optional) Run a Genie **eval/benchmark** over the sample questions to score accuracy.

To version a built space back into the repo: `databricks genie get-space <space_id>`
and commit the `serialized_space`.

## Access / grants (per-stage model)

Genie runs each query as the **asking user** against the SQL warehouse, so a user can
only see what UC already lets them read — the space adds no privilege of its own. The
per-stage grant here is **`SELECT` on the three scoped tables (or `USAGE` on
`dev_churn` + `SELECT` on `gold`/`silver`) to the analyst group / Genie consumer SP**,
granted when that principal exists. No blanket grant.

## Evidence

See [`../evidence/genie-space.md`](../evidence/genie-space.md): the live-validated
answers to the sample questions and (once created) the space id + a benchmark result.
