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

// coding_hours_trend_30d is a RATIO of this month's mean coding hours to last month's:
// 1.0 = flat, <1 = declining (0.0 = coding stopped entirely), >1 = growing. We render it
// as a percent change from flat and color by direction, with a ±3% "flat" dead-band.
const FLAT_LO = 0.97;
const FLAT_HI = 1.03;

/** Color by direction: declining = red (dn), ~flat = grey, growing = green (up). */
export function trendClass(ratio: number): "dn" | "up" | "flat" {
  if (ratio < FLAT_LO) return "dn";
  if (ratio > FLAT_HI) return "up";
  return "flat";
}

export function trendArrow(ratio: number): string {
  if (ratio < FLAT_LO) return "▼";
  if (ratio > FLAT_HI) return "▲";
  return "—";
}

/** Unsigned magnitude of the change from flat; the arrow conveys direction.
 *  0.62 → "38%", 1.0 → "flat", 0.0 → "100%", 1.78 → "78%". */
export function trendLabel(ratio: number): string {
  if (ratio >= FLAT_LO && ratio <= FLAT_HI) return "flat";
  return Math.abs(Math.round((ratio - 1) * 100)) + "%";
}

/** CSS severity class for a churn-by-region bar. */
export function geoSeverity(churnPct: number): RiskBand {
  if (churnPct >= 3.7) return "high";
  if (churnPct >= 3.3) return "medium";
  return "low";
}

/** Short "Mon D" stamp for a narrative refresh date. Returns "" on an unparseable
 *  input so callers can hide the stamp rather than render "Invalid Date". */
export function shortDate(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  return new Date(t).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
