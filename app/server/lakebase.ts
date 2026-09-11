// Lakebase Postgres executor for the low-latency "do this now" queue — features the
// Stage-3 serving layer doing its job inside the app. A lazily-created pooled client.

import pg from "pg";
import type { LakebaseConfig } from "./config.js";
import type { Row } from "./sql.js";

const { Pool } = pg;
let pool: pg.Pool | null = null;

function getPool(cfg: LakebaseConfig): pg.Pool {
  if (!pool) {
    pool = new Pool({
      host: cfg.host,
      port: cfg.port,
      database: cfg.database,
      user: cfg.user,
      password: cfg.password,
      ssl: cfg.ssl ? { rejectUnauthorized: false } : false,
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

export async function closePool(): Promise<void> {
  if (pool) {
    await pool.end();
    pool = null;
  }
}
