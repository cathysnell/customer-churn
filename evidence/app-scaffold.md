# Stage 6 — app scaffold: execution evidence

Proves the Retention Cockpit scaffold ([`../app/`](../app/)) builds, typechecks, tests
green, and boots. Live served-response evidence (against the warehouse + Lakebase +
Genie) is captured after deploy, when the app SP has its grants. Run 2026-09-11 on
Node v25.8.1 / npm 11.11.0.

## Test suite — `npm test`

```
 RUN  v2.1.9 /Users/cathy.snell/Code/customer-churn/app

 ✓ server/config.test.ts (4 tests) 2ms
 ✓ server/genie.test.ts (5 tests) 2ms
 ✓ server/sql.test.ts (13 tests) 3ms
 ✓ src/lib/format.test.ts (7 tests) 14ms
 ✓ server/routes.test.ts (7 tests) 59ms
 ✓ src/components/KpiCard.test.tsx (3 tests) 13ms

 Test Files  6 passed (6)
      Tests  39 passed (39)
```

Coverage: pure SQL builders/mappers + KPI assembly (guards catalog use, filter
allowlists, injection rejection, fraction→percent scaling), config loading (host
normalization, warehouse http path, Lakebase gating, port fallback), Genie
response parsing, HTTP routes (via a mocked `DataApi` + `app.inject`), and frontend
formatters + a component render.

## Typecheck — `npx tsc --noEmit`

```
=== tsc exit: 0 ===
```

## Production build — `npm run build`

```
vite v6.4.3 building for production...
✓ 40 modules transformed.
dist/index.html                   0.74 kB │ gzip:  0.41 kB
dist/assets/index-*.css          16.09 kB │ gzip:  3.87 kB
dist/assets/index-*.js          167.41 kB │ gzip: 53.69 kB
✓ built in 246ms
```

## Server boot — `PORT=8099 npm run start`

```
--- /api/health ---
{"status":"ok","doNowSource":"warehouse"}
--- / (SPA served?) ---
<title>Retention Cockpit</title>
--- /api/kpis (no creds locally) ---
500
```

`/api/health` responds and the built SPA is served. `/api/kpis` returns 500 **as
expected without credentials** — the `@databricks/sql` driver has no host/token to
connect with locally (`Invalid URL: https://:443/`); in Databricks Apps the runtime
injects `DATABRICKS_HOST` + the SP OAuth token and the warehouse read resolves. The
`doNowSource: "warehouse"` confirms the Lakebase-vs-warehouse fallback wiring: with no
`LAKEBASE_*` env the do-now queue falls back to the warehouse.
