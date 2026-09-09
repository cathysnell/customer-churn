# Lakeflow ingestion pipelines (Stage 1)

Source mirror of the two Lakeflow **ETL pipelines** (Declarative Pipelines) that
ingest the synthetic dataset from the landing Volume into `dev_churn`. Both are
serverless, default catalog `dev_churn`, and read every table definition under their
`transformations/` folder. Walkthrough: [`../docs/lakeflow-ingestion-walkthrough.md`](../docs/lakeflow-ingestion-walkthrough.md).

| Folder | Pipeline (workspace) | What it does |
| --- | --- | --- |
| [`usage_events_ingest/`](usage_events_ingest/) | `usage_events_ingest` | Hard-coded reference: one bronze→silver pair for `usage_events`, written out explicitly. |
| [`metadata_ingest/`](metadata_ingest/) | `metadata_ingest` | Metadata-driven: `metadata.py` describes all 8 sources; `md_transformation.py` loops over them to generate every bronze→silver pair. |

Both pipelines target the **same** tables (`dev_churn.bronze.<t>_raw` /
`dev_churn.silver.<t>`), so the `usage_events` entry in `metadata_ingest/metadata.py`
is kept identical to the hard-coded pipeline's silver projection. Run only one of
them against those tables at a time.

## Layout

```
usage_events_ingest/transformations/my_transformation.py   # bronze + silver, usage_events
metadata_ingest/transformations/
    metadata.py            # TABLES: one dict per source (name, format, select, expectations)
    md_transformation.py   # the factory loop that turns TABLES into @dp.table nodes
```

The `select` cast lists in `metadata.py` are derived from
[`../src/datagen/schemas.py`](../src/datagen/schemas.py) — the generator's single
source of truth — so silver types stay in lockstep with the emitted data.

## Adding a source (metadata pipeline)

Append a dict to `TABLES` in `metadata.py` — `name`, `format`, the silver `select`
projection, and `expect_drop` / `expect_keep`. No code change; the loop picks it up.
Land its files under `/Volumes/dev_churn/landing/raw/<name>/` first.
