// Lakebase Postgres executor for the low-latency "do this now" queue — features the
// Stage-3 serving layer doing its job inside the app. A lazily-created pooled client.

import type pg from "pg";
import { createLakebasePool } from "@databricks/lakebase";
import type { AtRiskFilters } from "../shared/api.js";
import type { LakebaseConfig } from "./config.js";
import { num, type Row } from "./sql.js";

let pool: pg.Pool | null = null;

// createLakebasePool returns a standard pg.Pool whose password is a callback that
// mints/refreshes a short-lived OAuth token per physical connection (Lakebase tokens
// expire ~1h). In Databricks Apps the app SP identity is auto-resolved from the
// ServiceContext; locally, a static `password` (if set) is used and OAuth is skipped.
function getPool(cfg: LakebaseConfig): pg.Pool {
  if (!pool) {
    pool = createLakebasePool({
      host: cfg.host,
      port: cfg.port,
      database: cfg.database,
      endpoint: cfg.endpoint || undefined,
      sslMode: cfg.sslMode,
      user: cfg.user,
      password: cfg.password,
      max: 4,
      idleTimeoutMillis: 30_000,
    });
  }
  return pool;
}

// The worklist projection, aliased to match `mapAtRisk` so the warehouse and Lakebase
// paths produce identical DTOs. Shared by the do-now queue and the at-risk list.
const SERVING_COLS =
  "p.user_id AS user_id, s.geo AS geo, s.persona AS persona, s.plan AS plan, " +
  "s.mrr_usd AS mrr, p.churn_score AS score, p.churn_risk_band AS band, " +
  "s.coding_hours_trend_30d AS coding_trend, s.crm_touches_30d AS crm_touches";
const SERVING_FROM =
  "FROM public.churn_predictions p JOIN public.churn_serving s USING (user_id)";

function clampLimit(n: number, def = 100, max = 500): number {
  return Math.min(Math.max(Math.floor(num(n, def)), 1), max);
}

/** High-risk, currently-subscribed subscribers with zero CRM touch, by MRR desc.
 *  LEFT JOINs the Lakebase-owned outreach log and drops anyone contacted in the last
 *  30 days — so logging outreach in the app removes them from the queue LIVE, before
 *  the (slower) warehouse `crm_touches_30d` recompute catches up. */
export const DO_NOW_SQL =
  `SELECT ${SERVING_COLS} ${SERVING_FROM} ` +
  "LEFT JOIN (SELECT user_id, MAX(logged_at) AS last_touch FROM public.crm_outreach_log GROUP BY user_id) o USING (user_id) " +
  "WHERE p.churn_risk_band = 'high' AND s.is_currently_subscribed = TRUE " +
  "AND s.crm_touches_30d = 0 " +
  "AND (o.last_touch IS NULL OR o.last_touch < now() - INTERVAL '30 days') " +
  "ORDER BY s.mrr_usd DESC LIMIT $1";

export async function queryDoNow(cfg: LakebaseConfig, limit: number): Promise<Row[]> {
  const res = await getPool(cfg).query(DO_NOW_SQL, [clampLimit(limit)]);
  return res.rows as Row[];
}

/** At-risk worklist rows from Lakebase (the general filterable list — "browse all").
 *  Filters are bound as parameters (not interpolated). Returns text + values for the
 *  parameterized query so it can be unit-tested without a connection. */
export function atRiskLakebaseQuery(f: AtRiskFilters = {}): { text: string; values: unknown[] } {
  const where = ["s.is_currently_subscribed = TRUE"];
  const values: unknown[] = [];
  if (f.band) { values.push(f.band); where.push(`p.churn_risk_band = $${values.length}`); }
  if (f.geo) { values.push(f.geo); where.push(`s.geo = $${values.length}`); }
  if (f.noCrm) where.push("s.crm_touches_30d = 0");
  if (f.minScore !== undefined) { values.push(num(f.minScore)); where.push(`p.churn_score >= $${values.length}`); }
  values.push(clampLimit(f.limit ?? 100));
  const text =
    `SELECT ${SERVING_COLS} ${SERVING_FROM} WHERE ${where.join(" AND ")} ` +
    `ORDER BY p.churn_score DESC LIMIT $${values.length}`;
  return { text, values };
}

export async function queryAtRisk(cfg: LakebaseConfig, f: AtRiskFilters = {}): Promise<Row[]> {
  const q = atRiskLakebaseQuery(f);
  const res = await getPool(cfg).query(q.text, q.values);
  return res.rows as Row[];
}

/** Full per-user detail from Lakebase (drawer). Adds the extra signal columns on top
 *  of the shared projection; aliased to match `mapUserDetail`. */
export const USER_DETAIL_LAKEBASE_SQL =
  `SELECT ${SERVING_COLS}, s.avg_acceptance_rate AS avg_acceptance_rate, ` +
  "s.avg_session_frequency AS avg_session_frequency, s.support_tickets_30d AS support_tickets, " +
  "s.tenure_months AS tenure_months, s.is_currently_subscribed AS is_currently_subscribed " +
  `${SERVING_FROM} WHERE p.user_id = $1`;

export async function queryUserDetail(cfg: LakebaseConfig, userId: string): Promise<Row[]> {
  const res = await getPool(cfg).query(USER_DETAIL_LAKEBASE_SQL, [userId]);
  return res.rows as Row[];
}

// ---- outreach log (Lakebase = system of record for operational writes) ----
//
// Table (created out-of-band, see serving/crm_outreach_log.sql):
//   public.crm_outreach_log(id, user_id, channel, note, logged_at)
// The app SP needs SELECT (do-now join) + INSERT (logging). This build never calls an
// external CRM — the write is to our own governed log, which is the demo's closed loop.

export const LOG_OUTREACH_SQL =
  "INSERT INTO public.crm_outreach_log (user_id, channel, note) VALUES ($1, $2, $3)";

export async function logOutreach(
  cfg: LakebaseConfig,
  userId: string,
  channel = "app",
  note = "Retention outreach logged from the cockpit",
): Promise<void> {
  await getPool(cfg).query(LOG_OUTREACH_SQL, [userId, channel, note]);
}

// ---- narrative cache (Lakebase = system of record for the app's own cached text) ----
//
// Table (created out-of-band, see serving/app_narrative.sql):
//   public.app_narrative(cache_key TEXT PRIMARY KEY, body TEXT NOT NULL,
//                        generated_at TIMESTAMPTZ NOT NULL, source TEXT NOT NULL)
// The app SP needs SELECT/INSERT/UPDATE. Until the table exists these queries throw
// and the data layer falls back to the templated narrative.

export interface NarrativeRow {
  body: string;
  generatedAt: string; // ISO8601
  source: string;
}

export const READ_NARRATIVE_SQL =
  "SELECT body, generated_at, source FROM public.app_narrative WHERE cache_key = $1";

export const UPSERT_NARRATIVE_SQL =
  "INSERT INTO public.app_narrative (cache_key, body, generated_at, source) " +
  "VALUES ($1, $2, now(), $3) " +
  "ON CONFLICT (cache_key) DO UPDATE SET " +
  "body = EXCLUDED.body, generated_at = EXCLUDED.generated_at, source = EXCLUDED.source";

export async function readNarrative(
  cfg: LakebaseConfig,
  cacheKey: string,
): Promise<NarrativeRow | null> {
  const res = await getPool(cfg).query(READ_NARRATIVE_SQL, [cacheKey]);
  const row = res.rows[0] as Record<string, unknown> | undefined;
  if (!row) return null;
  const ts = row.generated_at;
  return {
    body: String(row.body ?? ""),
    generatedAt: ts instanceof Date ? ts.toISOString() : String(ts ?? ""),
    source: String(row.source ?? ""),
  };
}

export async function writeNarrative(
  cfg: LakebaseConfig,
  cacheKey: string,
  body: string,
  source: string,
): Promise<void> {
  await getPool(cfg).query(UPSERT_NARRATIVE_SQL, [cacheKey, body, source]);
}

export async function closePool(): Promise<void> {
  if (pool) {
    await pool.end();
    pool = null;
  }
}
