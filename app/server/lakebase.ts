// Lakebase Postgres executor for the low-latency "do this now" queue — features the
// Stage-3 serving layer doing its job inside the app. A lazily-created pooled client.

import type pg from "pg";
import { createLakebasePool } from "@databricks/lakebase";
import type { LakebaseConfig } from "./config.js";
import type { Row } from "./sql.js";

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

/** High-risk, currently-subscribed subscribers with zero CRM touch, by MRR desc.
 *  Columns are aliased to match `mapAtRisk` so the warehouse and Lakebase paths
 *  produce identical DTOs. */
export const DO_NOW_SQL =
  "SELECT p.user_id AS user_id, s.geo AS geo, s.persona AS persona, " +
  "s.plan AS plan, s.mrr_usd AS mrr, p.churn_score AS score, " +
  "p.churn_risk_band AS band, s.coding_hours_trend_30d AS coding_trend, " +
  "s.crm_touches_30d AS crm_touches " +
  "FROM public.churn_predictions p " +
  "JOIN public.churn_serving s USING (user_id) " +
  "WHERE p.churn_risk_band = 'high' AND s.is_currently_subscribed = TRUE " +
  "AND s.crm_touches_30d = 0 " +
  "ORDER BY s.mrr_usd DESC LIMIT $1";

export async function queryDoNow(cfg: LakebaseConfig, limit: number): Promise<Row[]> {
  const res = await getPool(cfg).query(DO_NOW_SQL, [Math.min(Math.max(limit, 1), 500)]);
  return res.rows as Row[];
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
