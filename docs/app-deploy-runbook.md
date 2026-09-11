# Stage 6 — Databricks App deploy runbook

Deploys the Retention Cockpit ([`../app/`](../app/)) to Databricks Apps via the Asset
Bundle at the repo root ([`../databricks.yml`](../databricks.yml)). Each step is a
workspace write — run it deliberately, with the `fevm-serverless-stable-yuzk83` profile
authenticated (`databricks auth login --profile fevm-serverless-stable-yuzk83`).

Prereqs: Databricks CLI **≥ v0.239.0** (for `source_code_path`); the metric views,
functions, and Genie space from Stages 3–5 already live (they are).

## 1. Validate + deploy the app resource

```bash
cd /Users/cathy.snell/Code/customer-churn
databricks bundle validate -t dev -p fevm-serverless-stable-yuzk83
databricks bundle deploy   -t dev -p fevm-serverless-stable-yuzk83   # uploads app/, creates the app
databricks bundle run cockpit -t dev -p fevm-serverless-stable-yuzk83 # installs deps, builds, starts
```

`deploy` uploads the source and creates the app (which **mints the app's service
principal**) and, from the `sql_warehouse` app resource, auto-grants that SP `CAN_USE`
on warehouse `128c306447d9ef00`. `run` triggers `npm install` → `prestart` (`vite build`)
→ `npm run start` in the runtime. The `sync.exclude` keeps local `node_modules`/`dist`
out of the upload.

> If not using bundles, the equivalent is `databricks apps deploy retention-cockpit
> --source-code-path <workspace path>` after `databricks sync app ./app`; the bundle
> path is preferred (matches the repo's DAB architecture).

## 2. Grab the app's service principal

```bash
databricks apps get retention-cockpit -p fevm-serverless-stable-yuzk83
# → note .service_principal_client_id  (a UUID)  and the app URL
```

## 3. Grant the SP on Unity Catalog

The warehouse grant is already done (step 1). UC `SELECT`/`EXECUTE` are not
auto-granted — apply [`../app/grants.sql`](../app/grants.sql), replacing `:app_sp` with
the application id from step 2:

```bash
# after substituting :app_sp, run each statement on warehouse 128c306447d9ef00
databricks api post /api/2.0/sql/statements/ -p fevm-serverless-stable-yuzk83 \
  --json '{"warehouse_id":"128c306447d9ef00","statement":"GRANT USE CATALOG ON CATALOG dev_churn TO `<app_sp>`","wait_timeout":"30s"}'
# …repeat for each GRANT in grants.sql (one statement per call)
```

The app SP also needs **CAN RUN on the Genie space** for the Ask tab:

```bash
databricks permissions update genie /api/2.0/genie/spaces/01f1ad360e121f099e3070de938cd8cb \
  ... # or set CAN RUN in the Genie space UI → Permissions
```

## 4. (Optional) Lakebase for the "do this now" queue

The queue works via the warehouse fallback with no extra setup. To feature the Stage-3
serving layer instead:

1. Create secret scope + key: `databricks secrets create-scope retention-cockpit`;
   put the Lakebase role password at key `lakebase-password`.
2. Uncomment the `lakebase-password` secret resource in `databricks.yml` and the
   `LAKEBASE_*` env in `app/app.yaml` (fill host/user), then re-`deploy`/`run`.
3. Apply [`../app/lakebase_grants.sql`](../app/lakebase_grants.sql) in Postgres.

## 5. Verify + capture evidence (text-readable)

The FE Bar evaluator reads text only — capture responses, not screenshots:

```bash
APP_URL=$(databricks apps get retention-cockpit -p fevm-serverless-stable-yuzk83 | jq -r .url)
TOKEN=$(databricks auth token -p fevm-serverless-stable-yuzk83 | jq -r .access_token)
for ep in health kpis trend geo-churn "at-risk?band=high&noCrm=true&limit=5" do-now; do
  echo "== /$ep =="; curl -s -H "Authorization: Bearer $TOKEN" "$APP_URL/api/$ep"; echo
done > ../evidence/app-served-responses.txt
databricks apps get retention-cockpit -p fevm-serverless-stable-yuzk83 > ../evidence/app-deploy-status.txt
```

Commit `evidence/app-served-responses.txt` + `evidence/app-deploy-status.txt`. Confirm
the KPI numbers match the Genie space and `evidence/genie-space.md` (churn 3.25%, MRR at
risk high $36,568) — that consistency is the whole point of reading the shared metric
views.

## Rollback / teardown

```bash
databricks bundle destroy -t dev -p fevm-serverless-stable-yuzk83
```
