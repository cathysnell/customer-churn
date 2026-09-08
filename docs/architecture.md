# Architecture — the integrated end-to-end journey

The FE Bar build must be **one integrated journey**, not six siloed demos. This doc
describes how each stage hands off to the next. The concrete industry/dataset is
defined in [`project-brief.md`](project-brief.md); this file describes the *shape*
that any chosen problem must fill.

```
  RAW DATASET  (synthetic or public)
        │
        ▼
 ┌───────────────┐   1. LAKEFLOW
 │  Ingestion    │   Land raw data into bronze; incremental pipeline.
 └───────┬───────┘   Evidence: pipeline run logs + row counts committed as text.
         │
         ▼
 ┌───────────────┐   2. UNITY CATALOG
 │  Governance   │   catalog.schema.table, grants, lineage, data quality.
 └───────┬───────┘   Evidence: DDL + SHOW GRANTS / lineage query output committed.
         │
         ▼
 ┌───────────────┐   3. LAKEBASE
 │  Op. serving  │   Sync curated/gold tables to Lakebase for low-latency reads.
 └───────┬───────┘   Evidence: query results / latency output committed as text.
         │
         ▼
 ┌───────────────┐   4. ML / GEN AI
 │ Intelligence  │   Train/serve a model (or GenAI) that produces the key decision.
 └───────┬───────┘   Evidence: training metrics + real inference output committed.
         │
         ├──────────────► 5. GENIE ROOM
         │                Natural-language Q&A over the governed gold tables.
         │                Evidence: sample questions + returned SQL/results committed.
         │
         ▼
 ┌───────────────┐   6. DATABRICKS APP
 │  Business UI  │   Surfaces predictions + Genie + KPIs to the business user.
 └───────────────┘   Evidence: app run log / served responses committed as text.
```

## Handoff contract between stages

- **Lakeflow → Unity Catalog:** ingested bronze tables are registered under a single
  UC catalog/schema; nothing lives outside governance.
- **Unity Catalog → Lakebase:** curated **gold** tables (governed) are the *only*
  source synced to the operational serving layer.
- **Unity Catalog / gold → ML:** the model trains and scores off governed features,
  writing predictions back as a governed table.
- **Governed gold + predictions → Genie:** Genie answers natural-language questions
  against the same governed tables — consistent numbers with the app.
- **Everything → Databricks App:** the app reads predictions, KPIs, and optionally
  embeds/queries Genie — one coherent business surface.

## Reproducibility

The whole journey is expressed as a **Databricks Asset Bundle** (`databricks.yml` +
resources) so it is deploy-reproducible and reviewable as text. Notebooks are
committed **with outputs visible** so execution evidence travels with the code.

## Evidence strategy (per stage)

Each stage directory commits a text artifact proving it ran — see
[`submission-checklist.md`](submission-checklist.md). No stage is "done" until its
text-readable execution evidence is committed.
