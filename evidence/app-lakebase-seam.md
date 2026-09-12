# Stage 6 — Lakebase seam / closed loop (execution evidence)

The worklist now serves operational reads from the **Lakebase serving layer** and turns
"Log outreach" into a **real write** whose effect is visible in the queue immediately —
the closed loop. Captured 2026-09-12 on `fevm-serverless-stable-yuzk83`, app SP
`1768cda0-b24e-493f-8b2f-16fb8b8eda3a`. Scope: layers (a)+(b) live; (c) committed as
artifacts (not deployed).

## (a) At-risk list + subscriber detail served from Lakebase (warehouse fallback)

The general at-risk list and the drawer detail now read `public.churn_predictions ⋈
public.churn_serving` in Lakebase (KPIs/trend/geo stay on the governed warehouse metric
views). Verified live — the exact parameterized queries from `app/server/lakebase.ts`:

```
at-risk (band=high, geo=EMEA, limit 4) → 4 rows, churn_score DESC
  USR-00020564 EMEA student  mrr 20 score 0.9987 band high
  USR-00007234 EMEA indiv    mrr 20 score 0.9987 band high  (crm 1)
  USR-00027723 EMEA indiv    mrr 20 score 0.9986 band high
  USR-00041604 EMEA student  mrr 20 score 0.9986 band high  (crm 1)

user-detail (USR-00009599) → 1 row incl. all drawer columns
  APAC individual_dev pro_team_monthly mrr 40 score 0.6937 band high
  acceptance 0.4044  sessions/wk 2  support 0  tenure 34mo  subscribed t
```

Reads are wrapped in try/catch and fall back to the warehouse on any Lakebase error.
The Worklist shows "⚡ Served live from Lakebase" on the browse view too (now truthful).

## (b) Real outreach write — Lakebase = system of record — closes the loop LIVE

`public.crm_outreach_log` created (approved workspace write) + SP granted:

```
Table "public.crm_outreach_log"
  id        bigint       not null  generated always as identity  PK
  user_id   text         not null
  channel   text         not null  default 'app'
  note      text
  logged_at timestamptz  not null  default now()
  index crm_outreach_log_user_time_idx (user_id, logged_at DESC)

grants → 1768cda0-…  =  INSERT, SELECT   (verified)
```

`outreach()` INSERTs here; `DO_NOW_SQL` LEFT JOINs it and drops anyone contacted in the
last 30 days. End-to-end against the live table (exact `LOG_OUTREACH_SQL` + `DO_NOW_SQL`),
target = the queue's top user `USR-00005980`:

```
1. target in do-now queue BEFORE outreach   → 1  (present)
2. INSERT crm_outreach_log (real write)      → INSERT 0 1
3. target in do-now queue AFTER outreach     → 0  (dropped from the queue LIVE)
4. DELETE the outreach row                   → DELETE 1
5. target back in the queue                  → 1  (returns)
6. final crm_outreach_log row count          → 0  (table empty)
```

No external CRM is ever called (`simulated: true`) — the persisted log IS the loop. In
the UI, "Log outreach" refreshes the queue (reload key) and closes the drawer, so the
contacted subscriber visibly disappears.

## (c) PG→Delta propagation — committed as artifacts, NOT deployed

Managed Lakehouse Sync / Lakebase CDF is not viable here: it's Public Preview, AND this
metastore has no storage root, so managed UC synced-table pipelines fail
(`UNITY_CATALOG_INITIALIZATION_FAILED`) — the same reason the forward gold→Lakebase sync
is a serverless notebook. So (c) is a self-managed serverless PG→Delta job mirroring
`serving/reverse_etl.py`: `serving/crm_outreach_sync.py` (incremental append by id
high-watermark) + `_job.json` (PAUSED) + `serving/crm_outreach_delta.sql`. Deploy in a
follow-up PR.

## Remaining (post-merge)

Redeploy the app from merged `main`; then live-verify in the running app that logging
outreach removes the subscriber from the do-now queue and writes a `crm_outreach_log`
row as the SP.
