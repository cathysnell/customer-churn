// Pure display formatters, shared across views.

import type { RiskBand } from "../../shared/api";

export function money(n: number): string {
  return "$" + Math.round(n).toLocaleString("en-US");
}

export function moneyShort(n: number): string {
  if (Math.abs(n) >= 1_000_000) return "$" + (n / 1_000_000).toFixed(2) + "M";
  if (Math.abs(n) >= 1_000) return "$" + (n / 1_000).toFixed(1) + "K";
  return money(n);
}

export function pct(n: number, digits = 2): string {
  return n.toFixed(digits) + "%";
}

/** CSS class suffix for a trend arrow (coding_hours_trend_30d). */
export function trendClass(t: number): "dn" | "up" | "flat" {
  if (t < 0.9) return "dn";
  if (t > 1) return "up";
  return "flat";
}

export function trendArrow(t: number): string {
  if (t < 0.9) return "▼";
  if (t > 1) return "▲";
  return "—";
}

/** CSS severity class for a churn-by-region bar. */
export function geoSeverity(churnPct: number): RiskBand {
  if (churnPct >= 3.7) return "high";
  if (churnPct >= 3.3) return "medium";
  return "low";
}
