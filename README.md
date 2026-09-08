# FE Bar Demo

An end-to-end Databricks data journey built for the **FE Bar program**: a working
prototype that solves a *specific* customer problem in a *specific* industry, from
raw data all the way to a business-facing app.

> **Industry / customer problem:** Developer tools / B2B SaaS — a **freemium-to-Pro
> AI code editor (Anysphere / Cursor archetype)** whose **Pro-tier subscribers
> churn** with no unified daily signal to predict *who* will lapse in time to act.
> This build is a **Developer Behavioral Analytics Platform for Retention and Churn
> Prediction**: it ingests behavioral signals (active coding hours, AI-suggestion
> acceptance rate, session frequency), scores each Pro user's churn propensity
> daily, and triggers personalized CRM re-engagement to hold **monthly Pro churn
> below the 4% target** (benchmark: **−15%** churn) while lifting reactivation
> (**+22%**). See [`docs/project-brief.md`](docs/project-brief.md).

## The integrated journey

The build is a single, integrated journey — not siloed stages. Each stage hands off
to the next:

| Stage | Databricks capability | What it does here |
|-------|----------------------|-------------------|
| 1. Ingest | **Lakeflow** | Ingest the raw dataset (synthetic or public) |
| 2. Govern | **Unity Catalog** | Catalog, permissions, lineage over the data |
| 3. Serve | **Lakebase** | Operational / low-latency serving layer |
| 4. Intelligence | **ML or Gen AI** | The model that makes it intelligent |
| 5. Ask | **Genie Room** | Natural-language querying over the governed data |
| 6. Surface | **Databricks App** | Business-facing UI on top of it all |

## Contribution workflow (non-negotiable)

**All changes ship via a branch + pull request — never a direct commit to `main`.**
Every PR requires **human review before merge**; the automation opens PRs but never
merges them. Each build stage is implemented on its own branch and reviewed by an
independent (different-vendor) reviewer before it goes up for human merge.

## Data policy (non-negotiable)

**Synthetic or publicly available data only.** No real customer data, records, or
customer-identifying content — ever. Anything customer-derived must be scrubbed or
regenerated synthetically before it is committed.

## Repo layout

```
fe-bar-demo/
├── README.md                     # this file
├── docs/
│   ├── project-brief.md          # industry, customer problem, outcome, KPIs
│   ├── fe-bar-requirements.md     # program requirements, summarized
│   ├── architecture.md            # the 6-stage journey, wired end to end
│   └── submission-checklist.md    # what to submit + how to pass each gate
├── ingest/                        # Lakeflow ingestion (TBD)
├── notebooks/                     # notebooks committed WITH outputs visible
├── ml/                            # ML / Gen AI assets (TBD)
├── app/                           # Databricks App (TBD)
└── genie/                         # Genie Room config / sample questions (TBD)
```

## Execution evidence (this is what gets scored)

The evaluator **reads text only** — it cannot see images. Source code alone does not
pass the Build domain. Every stage must commit **text-readable evidence that it
actually ran**: notebook cells with their outputs, logged run output, query results,
or real model output. A screenshot or screen recording does **not** count.

See [`docs/submission-checklist.md`](docs/submission-checklist.md) for the full gate.
