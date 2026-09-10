# Stage 3 — Lakebase serving

Syncs the governed per-user churn state into **Lakebase Autoscaling** (managed
Postgres) so the CRM trigger and the app (Stage 6) can read current state with
low latency. Architecture: [`../docs/architecture.md`](../docs/architecture.md).

```
dev_churn.silver.*  ──(SQL)──►  dev_churn.gold.churn_serving  ──(UC synced table)──►  Lakebase Postgres
   governed source              one row per user, PK user_id        dev_churn_serving_pg.public.churn_serving
```

## Components

| Artifact | What / how |
| --- | --- |
| [`churn_serving.sql`](churn_serving.sql) | Builds `dev_churn.gold.churn_serving` — one row per user (identity, current subscription status, latest monthly engagement/label) with PK `user_id`. Run on a SQL warehouse. |
| Lakebase project | Autoscaling project `dev-churn-serving` (PG 17), branch `production`, endpoint `primary`. Created with `databricks postgres create-project`. |
| UC catalog over PG | `dev_churn_serving_pg` registers the Lakebase `databricks_postgres` DB in UC. `databricks postgres create-catalog dev_churn_serving_pg --json '{"spec":{"branch":"projects/dev-churn-serving/branches/production","postgres_database":"databricks_postgres"}}'` |
| [`synced_table.json`](synced_table.json) | UC synced table (reverse ETL) `dev_churn_serving_pg.public.churn_serving` from the gold source. `databricks postgres create-synced-table dev_churn_serving_pg.public.churn_serving --json @serving/synced_table.json` |

> **Autoscaling vs Provisioned:** synced tables use the **`databricks postgres`**
> (Autoscaling) surface — `create-catalog` / `create-synced-table`. The
> `databricks database ...` synced-table API is for **Provisioned** instances and
> requires a `database_instance_name` that Autoscaling projects don't expose; an
> Autoscaling project is not listed by `list-database-instances`.

## Sync mode

`SNAPSHOT` (one-time/on-demand full copy) — no Change Data Feed required, right for
this demo. For scheduled refresh, enable CDF on the source and switch to `TRIGGERED`:

```sql
ALTER TABLE dev_churn.gold.churn_serving SET TBLPROPERTIES (delta.enableChangeDataFeed = true);
```

## Access / grants (per-stage governance model)

- The synced table (reverse ETL) reads the source Delta and writes to Lakebase as
  its **owner identity** — no extra UC grant needed at this stage.
- The **app** reads from **Lakebase Postgres**, not the Delta table. Its access is a
  **Postgres-side role grant to the app's service principal** (`GRANT SELECT ON
  public.churn_serving TO <app_sp_role>`), created in **Stage 6** when the app SP
  exists. It is deliberately not granted here.

## Evidence

See [`../evidence/lakebase-serving-run.md`](../evidence/lakebase-serving-run.md):
the synced-table online state, a per-user Postgres lookup, and read latency.
