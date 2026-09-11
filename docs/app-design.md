# Stage 6 — Databricks App design doc: the Retention Cockpit

> **Status:** DESIGN (pre-build). This doc defines *what the app should look like and
> do* before any code lands. It is the contract for the Stage-6 build. Numbers shown in
> mockups are the live/illustrative values from the earlier stages (see
> [`project-brief.md`](project-brief.md)); every illustrative figure is labeled as such
> in the UI, per FE Bar data-safety.

## 1. Purpose & the one-line pitch

The **Retention Cockpit** is the business surface for the whole journey: it turns the
governed churn data + daily model scores (Stages 1–4) and the Genie semantic layer
(Stage 5) into a decision surface for the people who own retention at an
**Anysphere/Cursor-archetype** AI code editor.

> *"Keep Pro-tier monthly churn under 4% by seeing — every day — which subscribers are
> about to lapse, how much revenue is at risk, and who to reach first."*

It serves **two audiences in one app**, switchable by a persona toggle:

| Persona | Job-to-be-done | Primary view |
| --- | --- | --- |
| **Executive** (CRO / CFO / exec sponsor) | *Are we winning against the 4% churn target, and what's the revenue + ROI story?* | **Executive Overview** — KPIs, trend, MRR at risk, ROI |
| **Account manager / CSM** (domain owner) | *Who do I contact today, and what do I say?* | **Retention Worklist** — prioritized at-risk users + actions |

Both read the **same governed numbers** as Genie, so the story is consistent whether
someone asks a question in natural language or reads the dashboard.

## 2. Goals & non-goals

**Goals**
- Look and feel like a first-party **Databricks** product out of the box — clean,
  data-forward, professional; ready to present live to an executive.
- Be **trivially re-skinnable** — one theme file swaps the entire brand (Databricks →
  Anysphere → any customer) without touching components. This is itself a demo lever:
  *"we can dress this in your brand in minutes."*
- Tell a **clear narrative** top-to-bottom: problem → daily signal → who's at risk →
  what to do → business impact.
- **TypeScript + React** (explicitly not Streamlit), deployed as a Databricks App.
- Consistent numbers with Genie and the metric views (single semantic source of truth).

**Non-goals (for the demo)**
- No real write-back to CRM/production systems — outreach actions are demo-simulated
  (optimistic UI + a logged event), clearly labeled.
- No auth/user-management screens — Databricks Apps handles identity.
- No model training/monitoring UI — that's the ML stage's surface, not the cockpit.
- Not a general BI tool — it's an opinionated, narrative cockpit, not Genie/DBSQL.

## 3. Personas & their questions

**Executive (CRO/CFO).** Presents to the board; thinks in rate, revenue, and ROI.
Questions: *What's this month's Pro churn vs the 4% target? Is the trend improving? How
much MRR is at risk right now? What's the projected annual impact of the program? Which
geographies are trending worse?*

**Account manager / CSM (domain owner).** Works a queue; thinks in accounts and actions.
Questions: *Which high-value subscribers are most likely to churn? Who haven't we
touched yet? Why is this user at risk? What should I send them?* The hero cohort here is
the **1,004 high-risk, currently-subscribed users with zero CRM touch in 30 days** — the
actionable gap the program closes.

## 4. Information architecture

```
 ┌───────────────────────────────────────────────────────────────────────┐
 │  TOP BAR:  [◆ logo]  Retention Cockpit     [Exec ⇆ AM toggle]  [env]   │
 ├───────────────────────────────────────────────────────────────────────┤
 │  data-safety strip: "Illustrative synthetic data — no real customer data" │
 ├───────────────────────────────────────────────────────────────────────┤
 │                                                                         │
 │   TAB 1  Overview      TAB 2  Retention Worklist     TAB 3  Ask (Genie) │
 │                                                                         │
 └───────────────────────────────────────────────────────────────────────┘
```

Three tabs, one persona toggle. The toggle doesn't hide tabs — it **re-orders and
re-emphasizes**: Exec lands on Overview; AM lands on Worklist. Everyone can reach all
three (execs love to poke the worklist; AMs want the headline number).

## 5. Screen-by-screen (the narrative)

### Tab 1 — Executive Overview  *(the "are we winning?" screen)*

The narrative arc reads top-to-bottom like a slide:

1. **KPI hero row** — four cards, big numbers, target deltas:
   - **Pro monthly churn** — `3.25%` with a gauge against the **4.0% target** (green
     when under). Sub-label: "target < 4.0%". *(Churn rate measure, latest month.)*
   - **MRR at risk** — `$541,488` total, with a mini high/med/low split. *(MRR at risk
     measure.)*
   - **Reactivation rate** — `9.8%` vs `8.0%` baseline (**+22%**), labeled *illustrative*.
   - **Projected annual impact** — **≈ $2.58M**, labeled *illustrative*, with a tooltip
     that expands the ROI formula (`ARR × NRR% + Churn_Prevention × Base × LTV`).
2. **Churn trend** — an 18-month line of monthly churn rate with the 4% target as a
   reference line; annotation showing the decline `5.56% → 3.25%`. *(churn_metrics_monthly.)*
3. **Where the risk is** — two charts side by side:
   - **MRR at risk by band** (high/med/low bar).
   - **Churn by geography** (latest month, sorted; LATAM highest → ANZ lowest).
4. **The "so what" callout** — one sentence tying it together, e.g. *"We're under the 4%
   target this month; $36.6K of MRR sits in the high-risk band, concentrated in LATAM —
   and 1,004 high-value subscribers have had no outreach yet."* with a button → jumps to
   the Worklist filtered to that cohort.

### Tab 2 — Retention Worklist  *(the "who do I contact?" screen)*

The operator screen. Left = a filterable, sortable **at-risk table**; right (or a
slide-over drawer) = the **per-user detail** with a suggested action.

- **"Do this now" queue** pinned at top: high-risk + currently-subscribed + `crm_touches_30d = 0`,
  sorted by MRR. This is the 1,004-user cohort — the single most valuable list in the app.
- **Table columns:** user, geo, persona, plan, MRR, churn score (as a **risk badge**,
  not a raw probability — per the "score is a ranking, not a probability" rule),
  coding-hours trend (▼ sparkline when declining), CRM touches (30d).
- **Filters:** risk band, geo, persona, plan, "no CRM touch", currently-subscribed.
- **Per-user drawer:** identity + plan/MRR header; the **decline signal** (coding-hours
  trend, acceptance rate, session frequency, support tickets — the behavioral story);
  a **suggested re-engagement play** with a **GenAI-drafted message** (the Agent Bricks
  angle from the brief — a personalized note keyed to *why* this user is at risk); and a
  **[Log outreach] / [Add to campaign]** CTA (demo: optimistic update + logged event,
  labeled as simulated).

### Tab 3 — Ask (Genie)  *(the "just ask" screen)*

Natural-language Q&A over the same governed tables, so the numbers match the dashboards.
Reuses the curated prompts from [`../genie/sample_questions.md`](../genie/sample_questions.md)
as clickable chips ("What's this month's Pro churn?", "Which regions are trending
worse?", "Who are our most at-risk power users?"). Two viable implementations — see §9
(open decisions): **(a)** embed the live Genie space via its conversation API, or **(b)**
a lightweight NL panel that calls the Genie Conversations API and renders the returned
SQL + result table. Either way it's framed as "the same brain, ask it anything."

## 6. Visual design — Databricks look, one-file re-skin

### 6.1 Design language
Clean, generous whitespace, data-forward, restrained color. Content sits on light
neutral surfaces with a single strong brand accent; **color carries meaning** (risk
bands, target deltas) rather than decoration. Rounded-but-tight radii, subtle
elevation, one accent per view. This is the Databricks product aesthetic: confident,
quiet, numbers-first.

### 6.2 Token architecture (the re-skin mechanism)
Nothing hard-codes a hex value. Components consume **semantic tokens**; semantic tokens
map to a **brand palette**; the brand palette is the *only* file you edit to re-skin.

```
 brand palette (theme.databricks.ts)   ─┐
 brand palette (theme.anysphere.ts)    ─┼─►  semantic tokens (CSS vars)  ─►  components
 brand palette (theme.<customer>.ts)   ─┘     --color-brand, --color-bg,
                                              --color-text, --risk-high, …
```

- **Semantic tokens** (stable API for components): `--color-bg`, `--color-surface`,
  `--color-text`, `--color-muted`, `--color-brand`, `--color-brand-contrast`,
  `--color-accent`, `--risk-high`, `--risk-medium`, `--risk-low`, `--status-good`,
  `--status-warn`, radii, spacing scale, font family, shadow scale.
- **Databricks default brand:** Lava accent `#FF3621`, deep navy ink `#1B3139`, oat/off-white
  surfaces `#F9F7F4`/`#FFFFFF`, neutral grey scale; system/`Inter` fallback for the
  Databricks typeface. Risk palette: high = red, medium = amber, low = green.
- **Re-skin = swap one file.** A `<ThemeProvider theme="databricks|anysphere|…">` sets
  the CSS variables at `:root`. Ship 2 themes to prove it (Databricks + a dark
  "Anysphere/Cursor" theme) and a theme picker in a dev/demo menu.
- **Dark mode** falls out of the same mechanism (a theme is just a token set).

### 6.3 Charts & tables
One charting lib, themed from the same tokens (categorical + sequential palettes derived
from the brand). Tables are dense, sortable, keyboard-navigable, with sticky headers.

## 7. Component inventory (build checklist)

`AppShell` (top bar + tabs + data-safety strip) · `PersonaToggle` · `ThemeProvider` +
theme files · `KpiCard` (value, target delta, tooltip) · `GaugeVsTarget` · `TrendChart`
(reference line) · `BarByCategory` · `RiskBadge` · `DataTable` (filter/sort/paginate) ·
`Sparkline` · `UserDetailDrawer` · `SuggestedActionCard` (+ GenAI message block) ·
`GeniePanel` (chips + query + result) · `FilterBar` · `IllustrativeTag` · `EmptyState` /
`ErrorState` / `LoadingSkeleton`.

## 8. Technical architecture

**Stack (all TypeScript):**
- **Frontend:** Vite + React 18 + TypeScript. Styling via CSS variables (tokens) with a
  small utility layer; **Recharts** (or visx) for charts, themed from tokens; **TanStack
  Query** for data fetching/caching; **React Router** for the tabs. Accessible primitives
  (Radix) for the drawer/menus.
- **Backend:** a thin **Node + Fastify (TypeScript)** API server bundled with the app.
  Endpoints: `GET /api/kpis`, `GET /api/trend`, `GET /api/at-risk` (with filters),
  `GET /api/user/:id`, `POST /api/genie/query`, `POST /api/outreach` (demo log). The
  backend holds all data access — the browser never talks to the warehouse directly.
- **Data access:** the backend queries the **SQL warehouse** via the Databricks SQL
  driver, reading the **metric views** (`churn_metrics_current`, `churn_metrics_monthly`)
  and **trusted functions** (`at_risk_users`, `untouched_at_risk_users`) — the *same*
  semantic layer Genie uses, which is what guarantees the numbers match. The low-latency
  **Lakebase Postgres** copy (`dev_churn_serving_pg.public.churn_serving` /
  `.churn_predictions`) is the alternative path for the worklist if we want to show the
  operational-serving stage in action (see §9).

**Data → screen mapping:**

| Screen element | Source object | Access |
| --- | --- | --- |
| Churn rate KPI + trend | `churn_metrics_monthly` (`MEASURE(Churn rate)`) | warehouse |
| MRR at risk (total + by band) | `churn_metrics_current` (`MEASURE(MRR at risk)`) | warehouse |
| Churn by geo | `churn_metrics_monthly` by `Geo`, latest month | warehouse |
| Engagement by band | `churn_metrics_current` (avg coding trend / acceptance) | warehouse |
| Worklist / "do this now" | `at_risk_users(0.9)`, `untouched_at_risk_users('high')` | warehouse (or Lakebase) |
| Per-user detail | `churn_serving` ⋈ `churn_predictions` | warehouse (or Lakebase) |
| Ask tab | Genie space `01f1ad360e121f099e3070de938cd8cb` | Genie Conversations API |
| Reactivation / ROI cards | illustrative constants from `project-brief.md` | static (labeled) |

**Auth & identity.** Databricks Apps injects an OAuth identity. Default: the app runs as
its **service principal**; the SP gets least-privilege grants per the per-stage
governance model — `SELECT` on the three gold/silver tables + `EXECUTE` on the two
functions (or Postgres-side `GRANT SELECT` on `public.churn_serving` /
`churn_predictions` if reading Lakebase), `CAN USE` on the warehouse, and `CAN RUN` on
the Genie space. On-behalf-of-user is the alternative if we want row-level UC enforcement
per viewer (see §9).

**Deployment.** Standard Databricks App: `app.yaml` (command + env), `databricks apps
deploy`, resources declared for the warehouse, (optional) Lakebase instance, and the
Genie space. Frontend is built to static assets served by the Fastify process.

## 9. Open decisions (resolve before/while building)

1. **Backend language — Node/Fastify (TS) vs Python/FastAPI.** Recommend **Node/TS** for
   one-language cohesion with the frontend (user asked for TS). FastAPI is the more common
   Databricks Apps path and has richer SDK examples — fall back to it if the Node SQL
   driver friction is high.
2. **Worklist data path — SQL warehouse vs Lakebase Postgres.** Recommend **warehouse**
   as primary (one auth path, reuses the metric layer, numbers provably match Genie).
   Using **Lakebase** for the worklist is a nice way to *show the serving stage doing its
   job* (low-latency operational reads) — consider a toggle or use it just for the "do
   this now" queue.
3. **Genie tab — embedded space vs Conversations API panel.** API panel gives us control
   of the look; embed is faster and unmistakably "real Genie."
4. **Identity — app SP vs on-behalf-of-user.** SP is simplest for a demo; OBO enforces UC
   per viewer if we want to show governance carrying through to the app.
5. **GenAI re-engagement message — live model call vs pre-generated.** A live Agent
   Bricks/Foundation Model call is the strongest story; pre-generated per-persona
   templates are the safe fallback if latency/cost is a concern on stage.
6. **Outreach action — simulated only** (recommended for the demo) vs a real logged event
   table.

## 10. Accessibility & responsive

WCAG 2.1 AA contrast on all token pairs (verify both themes); full keyboard nav
(table, filters, drawer, tabs); visible focus; charts have text/table fallbacks so the
data is never image-only. Layout targets a **presentation display and a laptop** first
(the exec-demo context); it degrades gracefully to tablet width. Not optimized for phones.

## 11. Evidence strategy (FE Bar — text-readable)

The evaluator reads **text only**; screenshots don't count. So the app's execution
evidence (committed to `evidence/`) is: the **served API responses** (`/api/kpis`,
`/api/at-risk`, …) captured as JSON, the **app run/deploy log**, and a short transcript
showing a Genie query returning matching numbers. The visual design is proven by the
committed code + a served response, not by a picture.

## 12. Build sequence (proposed, after this doc is approved)

1. Scaffold Vite React TS + Fastify TS, `app.yaml`, theme system with 2 themes.
2. Backend read layer against the warehouse (KPIs, trend, at-risk) — commit sample
   responses as evidence.
3. Executive Overview tab (KPIs, gauge, trend, geo/band charts).
4. Retention Worklist tab (table, filters, "do this now" queue, user drawer).
5. Ask (Genie) tab.
6. Deploy to Databricks Apps; grant the app SP; capture run-log + served-response evidence.
7. PR with evidence; update the deck's app section.

*Cross-refs:* problem/KPIs/ROI/personas → [`project-brief.md`](project-brief.md);
stage handoffs → [`architecture.md`](architecture.md); semantic layer the app reads →
[`../genie/`](../genie/) + [`../metrics/`](../metrics/); serving copy →
[`../serving/`](../serving/).
