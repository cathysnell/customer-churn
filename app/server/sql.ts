// Pure SQL builders, row mappers, and KPI assembly. No I/O here — everything is a
// pure function of its inputs so it can be unit-tested without a live warehouse.

import {
  RISK_BANDS,
  GEOS,
  type AtRiskFilters,
  type AtRiskUser,
  type BandMrr,
  type CodingPoint,
  type GeoChurn,
  type Kpis,
  type RiskBand,
  type TrendPoint,
  type UserDetail,
} from "../shared/api.js";
import {
  CHURN_BASELINE_PCT,
  CHURN_TARGET_PCT,
  ILLUSTRATIVE_FIELDS,
  PROJECTED_ANNUAL_IMPACT,
  REACTIVATION_BASELINE_PCT,
  REACTIVATION_PCT,
} from "./constants.js";

export type Row = Record<string, unknown>;

// ---- coercion / validation ----

export function num(v: unknown, fallback = 0): number {
  if (v === null || v === undefined || v === "") return fallback;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : fallback;
}

export function normBand(v: unknown): RiskBand {
  const s = String(v ?? "").toLowerCase();
  return (RISK_BANDS as string[]).includes(s) ? (s as RiskBand) : "low";
}

export function isValidUserId(id: string): boolean {
  return /^[A-Za-z0-9_-]{1,64}$/.test(id);
}

function assertBand(b: string): RiskBand {
  if (!(RISK_BANDS as string[]).includes(b)) throw new Error(`invalid band: ${b}`);
  return b as RiskBand;
}

function assertGeo(g: string): string {
  if (!(GEOS as readonly string[]).includes(g)) throw new Error(`invalid geo: ${g}`);
  return g;
}

function clampLimit(n: number | undefined, def: number, max: number): number {
  const v = Math.floor(num(n, def));
  return Math.min(Math.max(v, 1), max);
}

// ---- warehouse query builders (metric views + governed gold tables) ----

export function latestChurnSql(catalog: string): string {
  return (
    "SELECT MEASURE(`Churn rate`) AS churn_rate " +
    `FROM ${catalog}.gold.churn_metrics_monthly ` +
    "WHERE `Month` = (SELECT MAX(`Month`) FROM " +
    `${catalog}.gold.churn_metrics_monthly)`
  );
}

export function trendSql(catalog: string): string {
  return (
    "SELECT `Month` AS month, MEASURE(`Churn rate`) AS churn_rate " +
    `FROM ${catalog}.gold.churn_metrics_monthly ` +
    "GROUP BY `Month` ORDER BY `Month`"
  );
}

export function geoChurnSql(catalog: string): string {
  return (
    "SELECT `Geo` AS geo, MEASURE(`Churn rate`) AS churn_rate " +
    `FROM ${catalog}.gold.churn_metrics_monthly ` +
    "WHERE `Month` = (SELECT MAX(`Month`) FROM " +
    `${catalog}.gold.churn_metrics_monthly) ` +
    "GROUP BY `Geo` ORDER BY churn_rate DESC"
  );
}

export function mrrByBandSql(catalog: string): string {
  return (
    "SELECT `Risk band` AS band, MEASURE(`MRR at risk`) AS mrr " +
    `FROM ${catalog}.gold.churn_metrics_current ` +
    "GROUP BY `Risk band` ORDER BY mrr DESC"
  );
}

/** Worklist rows. Filters are validated against allowlists before interpolation. */
export function atRiskSql(catalog: string, f: AtRiskFilters = {}): string {
  const where = ["s.is_currently_subscribed = TRUE"];
  if (f.band) where.push(`p.churn_risk_band = '${assertBand(f.band)}'`);
  if (f.geo) where.push(`s.geo = '${assertGeo(f.geo)}'`);
  if (f.noCrm) where.push("s.crm_touches_30d = 0");
  if (f.minScore !== undefined) where.push(`p.churn_score >= ${num(f.minScore)}`);
  const limit = clampLimit(f.limit, 100, 500);
  return (
    "SELECT p.user_id AS user_id, s.geo AS geo, s.persona AS persona, " +
    "s.plan AS plan, s.mrr_usd AS mrr, p.churn_score AS score, " +
    "p.churn_risk_band AS band, s.coding_hours_trend_30d AS coding_trend, " +
    "s.crm_touches_30d AS crm_touches " +
    `FROM ${catalog}.gold.churn_predictions p ` +
    `JOIN ${catalog}.gold.churn_serving s USING (user_id) ` +
    `WHERE ${where.join(" AND ")} ` +
    `ORDER BY p.churn_score DESC LIMIT ${limit}`
  );
}

export function userDetailSql(catalog: string, userId: string): string {
  if (!isValidUserId(userId)) throw new Error(`invalid user id: ${userId}`);
  return (
    "SELECT p.user_id AS user_id, s.geo AS geo, s.persona AS persona, " +
    "s.plan AS plan, s.mrr_usd AS mrr, p.churn_score AS score, " +
    "p.churn_risk_band AS band, s.coding_hours_trend_30d AS coding_trend, " +
    "s.crm_touches_30d AS crm_touches, s.avg_acceptance_rate AS avg_acceptance_rate, " +
    "s.avg_session_frequency AS avg_session_frequency, " +
    "s.support_tickets_30d AS support_tickets, s.tenure_months AS tenure_months, " +
    "s.is_currently_subscribed AS is_currently_subscribed " +
    `FROM ${catalog}.gold.churn_predictions p ` +
    `JOIN ${catalog}.gold.churn_serving s USING (user_id) ` +
    `WHERE p.user_id = '${userId}'`
  );
}

/** Last `months` months of a user's avg coding hours, from the monthly label table. */
export function codingHistorySql(catalog: string, userId: string, months: number): string {
  if (!isValidUserId(userId)) throw new Error(`invalid user id: ${userId}`);
  const n = Math.min(Math.max(Math.floor(num(months, 3)), 1), 24);
  // CAST the DATE to STRING so the driver returns "YYYY-MM-DD", not a JS Date object.
  return (
    "SELECT CAST(month_start AS STRING) AS month, avg_coding_hours AS coding_hours " +
    `FROM ${catalog}.silver.churn_labels ` +
    `WHERE user_id = '${userId}' ` +
    `ORDER BY month_start DESC LIMIT ${n}`
  );
}

// ---- row mappers ----

export function latestChurnPct(rows: Row[]): number {
  return round2(num(rows[0]?.churn_rate) * 100);
}

export function mapTrend(rows: Row[]): TrendPoint[] {
  return rows.map((r) => ({
    month: String(r.month ?? "").slice(0, 10),
    churnRatePct: round2(num(r.churn_rate) * 100),
  }));
}

export function mapGeo(rows: Row[]): GeoChurn[] {
  return rows.map((r) => ({
    geo: String(r.geo ?? ""),
    churnRatePct: round2(num(r.churn_rate) * 100),
  }));
}

/** DESC query → ascending (oldest → newest) for charting. */
export function mapCodingHistory(rows: Row[]): CodingPoint[] {
  return rows
    .map((r) => ({
      month: String(r.month ?? "").slice(0, 10),
      codingHours: round2(num(r.coding_hours)),
    }))
    .reverse();
}

export function mapMrrByBand(rows: Row[]): BandMrr[] {
  return rows.map((r) => ({ band: normBand(r.band), mrr: Math.round(num(r.mrr)) }));
}

export function mapAtRisk(rows: Row[]): AtRiskUser[] {
  return rows.map((r) => ({
    userId: String(r.user_id ?? ""),
    geo: String(r.geo ?? ""),
    persona: String(r.persona ?? ""),
    plan: String(r.plan ?? ""),
    mrr: Math.round(num(r.mrr)),
    score: round3(num(r.score)),
    band: normBand(r.band),
    codingTrend: round2(num(r.coding_trend)),
    crmTouches: Math.round(num(r.crm_touches)),
  }));
}

export function mapUserDetail(row: Row | undefined): UserDetail | null {
  if (!row) return null;
  const base = mapAtRisk([row])[0];
  return {
    ...base,
    avgAcceptanceRate: round3(num(row.avg_acceptance_rate)),
    avgSessionFrequency: round2(num(row.avg_session_frequency)),
    supportTickets: Math.round(num(row.support_tickets)),
    tenureMonths: row.tenure_months == null ? null : Math.round(num(row.tenure_months)),
    isCurrentlySubscribed: Boolean(row.is_currently_subscribed),
  };
}

// ---- KPI assembly (live churn + MRR, illustrative reactivation + ROI) ----

export function buildKpis(mrrByBand: BandMrr[], churnRatePct: number): Kpis {
  return {
    churnRatePct,
    churnTargetPct: CHURN_TARGET_PCT,
    churnBaselinePct: CHURN_BASELINE_PCT,
    mrrAtRiskTotal: mrrByBand.reduce((s, b) => s + b.mrr, 0),
    mrrAtRiskByBand: mrrByBand,
    reactivationPct: REACTIVATION_PCT,
    reactivationBaselinePct: REACTIVATION_BASELINE_PCT,
    projectedAnnualImpact: PROJECTED_ANNUAL_IMPACT,
    illustrative: ILLUSTRATIVE_FIELDS,
  };
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}
function round3(n: number): number {
  return Math.round(n * 1000) / 1000;
}
