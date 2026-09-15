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
│   ├── diagrams.md                # slide-ready process-flow + architecture diagrams (+ SVGs)
│   └── submission-checklist.md    # what to submit + how to pass each gate
├── src/datagen/                   # Stage 0: synthetic dataset generator + README
├── tests/                         # pytest suite for the generator
├── sql/unity_catalog.sql          # UC registration DDL (text, schema-derived)
├── evidence/                      # committed TEXT execution evidence per stage
│                                  # (data/ is generated locally and gitignored)
├── ingest/                        # Stage 1: Lakeflow ingestion (metadata + usage events)
├── metrics/                       # governed metric views (churn_metrics_current / _monthly)
├── ml/                            # Stage 4: churn model train/score + MLflow job
├── serving/                       # Stage 3/6: Lakebase sync, reverse ETL, app-owned tables
├── genie/                         # Stage 5: Genie Room config + sample questions
├── app/                           # Stage 6: Databricks App (React + Fastify)
└── databricks.yml                 # Asset Bundle: deploys the app to Databricks Apps
```

## Stage 0 — the dataset

The journey starts from a **synthetic** developer-behavior dataset generated
in-repo: 8 tables covering subscriptions (A03), daily usage telemetry (A06),
feature adoption (A07), support/CSAT (A14), CRM campaigns and touches, and
per-user monthly churn labels. 50,000 Pro users × 18 months of daily history at
full scale (~15.3M rows), with a `--sample-frac` flag for fast runs.

- **How to run it, the schema, and the realism model:**
  [`src/datagen/README.md`](src/datagen/README.md)
- **Execution evidence (text):**
  [`evidence/datagen-sample-run.md`](evidence/datagen-sample-run.md) (committed
  sample run, with two-run reproducibility digests),
  [`evidence/datagen-fullscale-run.md`](evidence/datagen-fullscale-run.md) +
  [`.log`](evidence/datagen-fullscale-run.log) (50,000-user run, 15,258,791 rows),
  [`evidence/pytest-output.txt`](evidence/pytest-output.txt) (163 tests + lint)
- **Unity Catalog DDL:** [`sql/unity_catalog.sql`](sql/unity_catalog.sql) — text,
  derived purely from the table specs, so the governance stage can run it verbatim.

### No data is committed — the dataset is reproducible from code

**`data/` is gitignored in its entirety; no Parquet/CSV artifact is tracked.** The
generator is deterministic from a committed seed (`1729`), so the dataset is
materialised on demand rather than stored:

```bash
python -m datagen --sample-frac 0.004 --months 18 --out data/sample \
    --format parquet --no-partitions          # small, ~7s
python -m datagen --out data/full             # full 50k users / ~15.3M rows
```

Downstream stages ingest from that local output or from a **Databricks Volume** the
generator wrote to — never from bytes in git. What *is* committed is the text proof
that the generator ran: row counts, `head()` previews, per-table digests, and a
two-run reproducibility comparison, all under [`evidence/`](evidence).

## Execution evidence (this is what gets scored)

The evaluator **reads text only** — it cannot see images. Source code alone does not
pass the Build domain. Every stage must commit **text-readable evidence that it
actually ran**: notebook cells with their outputs, logged run output, query results,
or real model output. A screenshot or screen recording does **not** count.

See [`docs/submission-checklist.md`](docs/submission-checklist.md) for the full gate.
