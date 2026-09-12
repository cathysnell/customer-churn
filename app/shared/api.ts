// Shared API contract between the Fastify backend and the React frontend.
// One source of truth so the two can't drift.

export type RiskBand = "high" | "medium" | "low";

/** Executive KPI header. Churn + MRR come from the governed metric views;
 *  reactivation + ROI are illustrative constants (labeled as such in the UI). */
export interface Kpis {
  churnRatePct: number; // latest monthly Pro churn, e.g. 3.25
  churnTargetPct: number; // 4.0
  churnBaselinePct: number; // illustrative 4.7
  mrrAtRiskTotal: number; // currently-subscribed MRR
  mrrAtRiskByBand: BandMrr[];
  reactivationPct: number; // illustrative
  reactivationBaselinePct: number; // illustrative
  projectedAnnualImpact: number; // illustrative ROI
}

export interface BandMrr {
  band: RiskBand;
  mrr: number;
}

export interface TrendPoint {
  month: string; // YYYY-MM-DD
  churnRatePct: number;
}

export interface GeoChurn {
  geo: string;
  churnRatePct: number;
}

export interface AtRiskUser {
  userId: string;
  geo: string;
  persona: string;
  plan: string;
  mrr: number;
  score: number; // 0..1
  band: RiskBand;
  codingTrend: number; // coding_hours_trend_30d
  crmTouches: number; // crm_touches_30d
}

export interface UserDetail extends AtRiskUser {
  avgAcceptanceRate: number;
  avgSessionFrequency: number;
  supportTickets: number;
  tenureMonths: number | null;
  isCurrentlySubscribed: boolean;
}

export interface AtRiskFilters {
  band?: RiskBand;
  geo?: string;
  noCrm?: boolean;
  minScore?: number;
  limit?: number;
}

export interface Health {
  status: string;
  doNowSource: "lakebase" | "warehouse";
}

export interface CodingPoint {
  month: string; // YYYY-MM-DD
  codingHours: number; // avg daily coding hours that month
}

export interface GenieAnswer {
  question: string;
  text: string;
  sql: string;
  columns: string[];
  rows: (string | number | null)[][];
}

export interface OutreachResult {
  logged: boolean;
  userId: string;
  simulated: true; // this build never sends externally
}

export const RISK_BANDS: RiskBand[] = ["high", "medium", "low"];
export const GEOS = ["NA", "EMEA", "APAC", "LATAM", "MEA", "ANZ"] as const;
