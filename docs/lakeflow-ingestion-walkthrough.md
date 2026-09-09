# Lakeflow ingestion walkthrough (Stage 1)

> **Purpose:** a teach-by-doing guide to ingest ONE source/table end to end with
> Lakeflow, then a pattern to repeat for the rest. We start with **`usage_events`
> (asset A06)** — the raw developer-behavior telemetry (daily coding hours, AI
> suggestion acceptance rate, session frequency) — because it is the highest-volume,
> streaming-shaped source and the primary churn signal.
>
> Terminology note (current as of 2026): what used to be "Delta Live Tables (DLT)"
> is now **Lakeflow (Spark) Declarative Pipelines**; **Lakeflow Connect** is the
> managed-connector ingestion layer; **Auto Loader** (`cloudFiles`) is still the
> file-ingestion source. Streaming tables require **Unity Catalog**.

## The mental model (how the pieces fit)

```
raw files (synthetic parquet/csv in a UC Volume)
        │   Auto Loader (cloudFiles)  ── incremental file discovery + schema tracking
        ▼
bronze streaming table  (CREATE OR REFRESH STREAMING TABLE ... FROM STREAM read_files(...))
        │   Declarative Pipeline (SQL or Python), runs on serverless
        ▼
silver  (cleaned/typed materialized view or streaming table)
        ▼
gold    (aggregates / features consumed by ML, Lakebase, Genie, the app)
```

- **Lakeflow Connect** = managed connectors for DBs/SaaS/message buses (e.g. pull
  from Salesforce or Postgres via CDC). We don't need a SaaS connector for the demo
  because our raw data is synthetic files — so we use **Auto Loader over files in a
  Unity Catalog Volume**, which is the file-ingestion path of the same Lakeflow
  stack.
- **Declarative Pipeline** = where you DECLARE the bronze/silver/gold tables in SQL
  or Python; Databricks figures out the DAG, incremental refresh, and checkpoints.
- **Streaming table** = a Delta table with incremental semantics; new files land →
  only new rows are processed.

## Prerequisites (one-time)

1. A Unity Catalog **catalog** (`dev_churn`) with the schemas the pipeline writes
   to — **`bronze`** and **`silver`** — plus a **`landing`** schema to hold the raw
   files Volume.
2. A UC **Volume** for raw synthetic files: `dev_churn.landing.raw`, giving the path
   `/Volumes/dev_churn/landing/raw/`. Auto Loader also needs a schema-tracking
   location — we keep it in a `_schemas/` **subdirectory of this same Volume**
   (`/Volumes/dev_churn/landing/raw/_schemas/…`), so **no second Volume is needed**.
   It sits beside the ingested `usage_events/` folder, so it is never re-ingested.
3. Permission to create pipelines and streaming tables (UC required).
4. The synthetic sample data from the data-generation stage (the generator's small
   sample, generated locally under `data/` — we upload that to the Volume).

Create them once (adjust the profile):

```bash
P=fevm-serverless-stable-yuzk83
databricks schemas create bronze  dev_churn --profile $P
databricks schemas create silver  dev_churn --profile $P
databricks schemas create landing dev_churn --profile $P
databricks volumes create dev_churn landing raw MANAGED --profile $P
```

> **Gotcha (2026-09-09):** every segment of a `/Volumes/<catalog>/<schema>/<volume>/…`
> path up to the third element is a real UC object. Pointing `schemaLocation` at
> `/Volumes/dev_churn/landing/_schemas/…` implies a **Volume** named `_schemas` that
> doesn't exist and fails with *"Volume `dev_churn`.`landing`.`_schemas` does not
> exist."* Keep the schema-tracking dir **inside** an existing Volume (a `_schemas/`
> subdirectory of `raw`), as the steps below now do.

## Step 1 — Land the raw files in a UC Volume

The generator writes partitioned files locally. Upload the `usage_events` sample to
the Volume (CLI shown; the UI upload works too):

```bash
databricks fs cp -r data/usage_events \
  dbfs:/Volumes/dev_churn/landing/raw/usage_events/
```

Why a Volume: Auto Loader watches a path, and UC Volumes are the governed,
UC-native place to keep raw file landing zones (lineage + permissions come for free).

## Step 2 — Declare the bronze streaming table (SQL)

Create a pipeline source file, `pipelines/usage_events.sql`:

```sql
CREATE OR REFRESH STREAMING TABLE dev_churn.bronze.usage_events_raw
COMMENT 'A06 raw developer-behavior telemetry, ingested incrementally via Auto Loader'
AS
SELECT
  *,
  _metadata.file_path      AS _source_file,
  current_timestamp()      AS _ingested_at
FROM STREAM read_files(
  '/Volumes/dev_churn/landing/raw/usage_events/',
  format          => 'parquet',
  schemaLocation  => '/Volumes/dev_churn/landing/raw/_schemas/usage_events'
);
```

What each part does:
- `STREAMING TABLE` → incremental; re-running only processes NEW files.
- `STREAM read_files(...)` → Auto Loader under the hood; discovers new files.
- `schemaLocation` → where inferred schema + evolution history is tracked, so new
  columns don't break the pipeline.
- The `_source_file` / `_ingested_at` columns are cheap, high-value lineage/debug
  breadcrumbs — keep them.

### Same thing in Python (if you prefer)

`pipelines/usage_events.py`:

```python
from pyspark import pipelines as dp

@dp.table(name="usage_events_raw", comment="A06 raw telemetry via Auto Loader")
def usage_events_raw():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "parquet")
        .option("cloudFiles.schemaLocation",
                "/Volumes/dev_churn/landing/raw/_schemas/usage_events")
        .load("/Volumes/dev_churn/landing/raw/usage_events/")
    )
```

## Step 3 — Add a silver layer with quality expectations

Bronze is raw; silver is trustworthy. Declarative pipelines let you attach
**expectations** that drop or fail bad rows — and the pass/fail counts become
committable text evidence.

```sql
CREATE OR REFRESH STREAMING TABLE dev_churn.silver.usage_events
(
  CONSTRAINT valid_user     EXPECT (user_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT valid_hours    EXPECT (coding_hours BETWEEN 0 AND 24),
  -- Expectations are evaluated against the SELECT's OUTPUT columns, so this must
  -- use the aliased name `ai_acceptance_rate`, not the source `ai_suggestion_acceptance_rate`.
  CONSTRAINT valid_accept   EXPECT (ai_acceptance_rate BETWEEN 0 AND 1)
)
AS
SELECT
  CAST(user_id AS STRING)                     AS user_id,
  CAST(event_date AS DATE)                     AS event_date,
  CAST(coding_hours AS DOUBLE)                 AS coding_hours,
  CAST(ai_suggestion_acceptance_rate AS DOUBLE) AS ai_acceptance_rate,
  CAST(session_frequency AS INT)               AS session_frequency,
  geo
FROM STREAM dev_churn.bronze.usage_events_raw;
```

## Step 4 — Create and run the pipeline

In the workspace sidebar go to **Jobs & Pipelines → Create → ETL pipeline**. The
wizard **scaffolds a source-code folder for you** — a folder in your workspace (e.g.
`/Workspace/Users/<you>/<pipeline-name>/`) with a `transformations/` subfolder and
the starter `my_transformations.py`. That folder *is* the pipeline: Lakeflow runs
every table definition under it, so you don't point it anywhere by hand — you just
edit the file it created. (You can see or change the folder later under **Settings →
Source code**, e.g. to add repo files.) Set the default catalog to `dev_churn`,
choose **serverless**, and run.

**Choose `ETL pipeline`, not `Ingestion pipeline`** — the two are different Lakeflow
entry points:

| UI choice | What it is | Use it when |
| --- | --- | --- |
| **ETL pipeline** ✅ | **Lakeflow Declarative Pipelines** (formerly DLT). You author the bronze/silver/gold tables yourself in SQL or Python. | Our case: Auto Loader over synthetic files in a Volume, declared in code. |
| Ingestion pipeline | **Lakeflow Connect** — a guided *managed connector* (Salesforce, Workday, SQL Server/Postgres CDC…). No code; you pick a source system. | Only if you were pulling CRM live from Salesforce/a DB instead of files. |

### What the ETL wizard scaffolds

Creating an ETL pipeline lays down a source folder with a `transformations/`
directory and a starter file — for a Python pipeline that's **`my_transformations.py`**
(blank, or a commented sample). You put your table definitions there; every
`@dp.table` function across the files in that folder becomes a node in the DAG.
You can rename the file or add more — the pipeline reads the whole folder.

### Paste this into `my_transformations.py`

One file defines the whole `usage_events` chain — bronze (Auto Loader) → silver
(typed + quality-checked). Table names are **fully qualified** so bronze and silver
land in different schemas regardless of the pipeline's default schema:

```python
from pyspark import pipelines as dp
from pyspark.sql.functions import col, current_timestamp

# ---- Bronze: raw A06 telemetry, ingested incrementally via Auto Loader ----
@dp.table(
    name="dev_churn.bronze.usage_events_raw",
    comment="A06 raw developer-behavior telemetry via Auto Loader",
)
def usage_events_raw():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "parquet")
        .option("cloudFiles.schemaLocation",
                "/Volumes/dev_churn/landing/raw/_schemas/usage_events")
        .load("/Volumes/dev_churn/landing/raw/usage_events/")
        # cheap, high-value lineage/debug breadcrumbs
        .withColumn("_source_file", col("_metadata.file_path"))
        .withColumn("_ingested_at", current_timestamp())
    )

# ---- Silver: typed + quality-checked ----
# Expectations bind to this function's OUTPUT columns, so valid_accept references
# the aliased `ai_acceptance_rate`, not the source `ai_suggestion_acceptance_rate`.
@dp.table(
    name="dev_churn.silver.usage_events",
    comment="A06 cleaned/typed telemetry with data-quality expectations",
)
@dp.expect_all_or_drop({"valid_user": "user_id IS NOT NULL"})
@dp.expect_all({
    "valid_hours":  "coding_hours BETWEEN 0 AND 24",
    "valid_accept": "ai_acceptance_rate BETWEEN 0 AND 1",
})
def usage_events():
    return (
        spark.readStream.table("dev_churn.bronze.usage_events_raw")
        .selectExpr(
            "CAST(user_id AS STRING)                       AS user_id",
            "CAST(event_date AS DATE)                      AS event_date",
            "CAST(coding_hours AS DOUBLE)                  AS coding_hours",
            "CAST(ai_suggestion_acceptance_rate AS DOUBLE) AS ai_acceptance_rate",
            "CAST(session_frequency AS INT)                AS session_frequency",
            "geo",
        )
    )
```

> `event_date` is the Hive partition column in the landing path
> (`…/usage_events/event_date=YYYY-MM-DD/…`); Auto Loader infers it automatically,
> so it's present in bronze without being in the file body.
>
> `@dp.expect_all_or_drop` **drops** violating rows (a NULL `user_id` is unusable);
> `@dp.expect_all` only **records** violations as metrics and keeps the rows — both
> pass/fail counts land in the event log for Step 5's evidence. The equivalent SQL
> in Steps 2–3 uses `ON VIOLATION DROP ROW` vs. a bare `EXPECT`.

### Pipeline settings

- **Serverless**: on.
- **Default catalog**: `dev_churn`; **default schema**: `bronze` (unqualified table
  names would land here — ours are fully qualified, so this is just the fallback).
- **Source code**: the folder containing `my_transformations.py` (the wizard sets
  this to the scaffolded folder already).

Then **Validate** (dry-run: resolves the DAG and schemas without writing), then
**Run**.

### Reproducible-from-repo alternative (Asset Bundle)

Instead of the UI, a `databricks.yml` can declare the pipeline so it lives in git:
`databricks bundle deploy && databricks bundle run`. Same `my_transformations.py`;
the bundle just owns the pipeline's settings.

On the first run you'll see the DAG: `usage_events_raw` → `usage_events`, with row
counts and expectation pass rates per table.

## Step 5 — Capture TEXT execution evidence (this is graded)

The evaluator reads text only — a screenshot of the pipeline graph does NOT count.
Commit the actual output. Good, cheap evidence:

```sql
-- committed as a notebook cell WITH its output, or piped to evidence/usage_events_ingest.txt
SELECT COUNT(*) AS row_count,
       COUNT(DISTINCT user_id) AS users,
       MIN(event_date) AS first_day, MAX(event_date) AS last_day
FROM dev_churn.silver.usage_events;

-- expectation results (the data-quality proof)
SELECT * FROM event_log(TABLE(dev_churn.silver.usage_events))
WHERE event_type = 'flow_progress';
```

Commit: the pipeline run's row counts, the expectation pass/fail numbers, and a
`head()` of the silver table. That is defensible "it actually ran" evidence.

## Repeat for the other tables

Same pattern per source, with the right connector/format:
- `subscriptions`/billing (A03), `feature_adoption` (A07), `support_tickets` (A14):
  identical Auto-Loader-over-Volume pattern (they're synthetic files too).
- `crm_campaigns` / `crm_touches`: same; in a real deployment CRM would come via a
  **Lakeflow Connect** SaaS connector (e.g. Salesforce) instead of files — worth a
  sentence in the deck to show you know the managed-connector path.
- `churn_labels`: ingest as a batch/materialized view; it's derived, not streamed.

### Optional: make it metadata-driven

Rather than copy `my_transformations.py` per source, you can drive the whole set
from **metadata**. Every table shares the same bronze shape (Auto Loader over a
Volume folder) and differs only in a few values — source name, format, the
silver casts/renames, and its expectations. Describe each source as a dict entry
and loop over the list, generating the bronze + silver `@dp.table` definitions
programmatically (the pipeline file runs at graph-resolution time, so a `for` loop
creates real DAG nodes). Adding a source then becomes a config entry, not new code.

Two things to know: bind the loop variable per iteration (a factory function or
default-arg capture) or every generated table closes over the *last* spec; and
carry a `mode` flag so `churn_labels` can be batch while the rest stream. The
per-table column/cast metadata can even be **derived from `src/datagen/schemas.py`**
(the generator's single source of truth), keeping ingest DRY with the data itself.
It's also a strong "metadata-driven ingestion framework" point for the deck.

## Where this hands off next

- **Unity Catalog (Stage 2)** governs everything we just created (it already does —
  streaming tables are UC objects); Stage 2 adds ownership, grants, and lineage.
- **Lakebase (Stage 3)** reads the gold/serving view for low-latency per-user state.
- **ML (Stage 4)** trains on silver/gold features.
