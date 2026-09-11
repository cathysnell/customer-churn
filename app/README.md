# Stage 6 — Retention Cockpit (Databricks App)

The business surface for the end-to-end churn journey. A React + TypeScript frontend
served by a Fastify (TypeScript) backend that reads the **same governed semantic layer
as Genie** (the metric views + trusted functions), so the app's numbers provably match
the Genie space and the dashboards.

Design: [`../docs/app-design.md`](../docs/app-design.md) · mockup:
[`../docs/app-mockup.html`](../docs/app-mockup.html).

## Architecture

```
 React / Vite (src/)  ──/api/*──►  Fastify (server/)  ──►  SQL warehouse  (metric views + fns)
   Overview · Worklist · Ask                            └►  Lakebase PG    (do-now queue)
                                                        └►  Genie API      (Ask tab)
```

- **Backend** (`server/`) — Fastify. `sql.ts` holds pure query builders + row mappers
  (unit-tested); `databricks.ts` / `lakebase.ts` / `genie.ts` are the executors;
  `data.ts` is the `DataApi` the routes call; `routes.ts` is the HTTP surface.
- **Frontend** (`src/`) — Vite + React. Design tokens in `theme.css` drive the
  Databricks↔Anysphere re-skin; components in `components/`, views in `views/`, the
  typed client in `lib/api.ts`.
- **Contract** (`shared/api.ts`) — the DTOs both sides import, so they can't drift.

## Resolved build decisions (design doc §9)

1. Backend **Node/Fastify (TS)** · 2. **warehouse** for KPIs/trend/worklist, **Lakebase**
for the do-now queue · 3. Genie **Conversations API panel** · 4. **app service principal** ·
5. **pre-generated** re-engagement drafts · 6. **simulated** outreach.

## Develop

```bash
npm install
cp .env.example .env          # fill in DATABRICKS_HOST + DATABRICKS_TOKEN
npm run dev:server            # Fastify on :8000
npm run dev:web               # Vite on :5173 (proxies /api → :8000)
npm test                      # vitest
npm run typecheck             # tsc --noEmit
```

## Deploy (Databricks Apps)

`app.yaml` pins the warehouse id + Genie space; `DATABRICKS_HOST` and the OAuth token
are injected by the runtime. `npm run build` emits `dist/`, which the Fastify process
(`npm run start`) serves alongside `/api`.

**Grants the app SP needs** (least-privilege, per-stage model):
- Warehouse `128c306447d9ef00`: `CAN USE`
- UC: `SELECT` on `dev_churn.gold.churn_serving`, `.churn_predictions`,
  `dev_churn.silver.churn_labels`; `EXECUTE` on `dev_churn.gold.at_risk_users`,
  `.untouched_at_risk_users`
- Lakebase: `GRANT SELECT ON public.churn_serving, public.churn_predictions TO <app_sp_role>`
- Genie space `01f1ad360e121f099e3070de938cd8cb`: `CAN RUN`

## Evidence

The FE Bar evaluator reads text only. Capture the served API responses
(`/api/kpis`, `/api/at-risk`, …) and the app run/deploy log into `../evidence/`;
screenshots don't count as execution evidence.

## API

`GET /api/health` · `GET /api/kpis` · `GET /api/trend` · `GET /api/geo-churn` ·
`GET /api/at-risk?band=&geo=&noCrm=&minScore=&limit=` · `GET /api/do-now?limit=` ·
`GET /api/user/:id` · `POST /api/genie/query {question}` · `POST /api/outreach {userId}`.
