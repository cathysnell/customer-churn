import { describe, expect, it } from "vitest";
import {
  atRiskSql,
  buildKpis,
  isValidUserId,
  latestChurnPct,
  mapAtRisk,
  mapGeo,
  mapMrrByBand,
  mapTrend,
  mapUserDetail,
  normBand,
  num,
  userDetailSql,
} from "./sql.js";

describe("coercion", () => {
  it("num coerces strings/decimals and falls back", () => {
    expect(num("0.0325")).toBeCloseTo(0.0325);
    expect(num(5)).toBe(5);
    expect(num(null)).toBe(0);
    expect(num("nope", -1)).toBe(-1);
  });
  it("normBand normalizes and defaults to low", () => {
    expect(normBand("HIGH")).toBe("high");
    expect(normBand("medium")).toBe("medium");
    expect(normBand("garbage")).toBe("low");
  });
  it("isValidUserId rejects injection", () => {
    expect(isValidUserId("usr_4837a9")).toBe(true);
    expect(isValidUserId("x'; DROP TABLE t; --")).toBe(false);
    expect(isValidUserId("")).toBe(false);
  });
});

describe("query builders", () => {
  it("uses the configured catalog + metric views", () => {
    expect(atRiskSql("dev_churn")).toContain("dev_churn.gold.churn_predictions");
    expect(atRiskSql("dev_churn")).toContain("s.is_currently_subscribed = TRUE");
  });
  it("adds validated filters and clamps the limit", () => {
    const sql = atRiskSql("dev_churn", { band: "high", geo: "LATAM", noCrm: true, limit: 9999 });
    expect(sql).toContain("p.churn_risk_band = 'high'");
    expect(sql).toContain("s.geo = 'LATAM'");
    expect(sql).toContain("s.crm_touches_30d = 0");
    expect(sql).toContain("LIMIT 500"); // clamped
  });
  it("rejects an out-of-allowlist filter", () => {
    expect(() => atRiskSql("dev_churn", { band: "sneaky" as never })).toThrow();
    expect(() => atRiskSql("dev_churn", { geo: "'; DROP" })).toThrow();
  });
  it("userDetailSql rejects a bad id", () => {
    expect(() => userDetailSql("dev_churn", "a' OR '1'='1")).toThrow();
    expect(userDetailSql("dev_churn", "usr_1")).toContain("p.user_id = 'usr_1'");
  });
});

describe("mappers", () => {
  it("latestChurnPct converts a fraction to a percentage", () => {
    expect(latestChurnPct([{ churn_rate: 0.0325 }])).toBe(3.25);
    expect(latestChurnPct([])).toBe(0);
  });
  it("mapTrend/mapGeo scale to percent", () => {
    expect(mapTrend([{ month: "2026-08-01T00:00:00", churn_rate: 0.0325 }])).toEqual([
      { month: "2026-08-01", churnRatePct: 3.25 },
    ]);
    expect(mapGeo([{ geo: "LATAM", churn_rate: 0.0399 }])).toEqual([
      { geo: "LATAM", churnRatePct: 3.99 },
    ]);
  });
  it("mapMrrByBand rounds and normalizes band", () => {
    expect(mapMrrByBand([{ band: "HIGH", mrr: "36568.4" }])).toEqual([
      { band: "high", mrr: 36568 },
    ]);
  });
  it("mapAtRisk shapes a row", () => {
    const [u] = mapAtRisk([
      {
        user_id: "usr_1",
        geo: "NA",
        persona: "team_lead",
        plan: "pro_team_monthly",
        mrr: "180",
        score: "0.9421",
        band: "high",
        coding_trend: "0.617",
        crm_touches: "0",
      },
    ]);
    expect(u).toEqual({
      userId: "usr_1",
      geo: "NA",
      persona: "team_lead",
      plan: "pro_team_monthly",
      mrr: 180,
      score: 0.942,
      band: "high",
      codingTrend: 0.62,
      crmTouches: 0,
    });
  });
  it("mapUserDetail returns null for missing row", () => {
    expect(mapUserDetail(undefined)).toBeNull();
    const d = mapUserDetail({
      user_id: "usr_1", geo: "NA", persona: "p", plan: "pro_monthly",
      mrr: 20, score: 0.5, band: "medium", coding_trend: 0.9, crm_touches: 1,
      avg_acceptance_rate: 0.24, avg_session_frequency: 2.1, support_tickets: 3,
      tenure_months: 14, is_currently_subscribed: true,
    });
    expect(d?.avgAcceptanceRate).toBe(0.24);
    expect(d?.isCurrentlySubscribed).toBe(true);
    expect(d?.tenureMonths).toBe(14);
  });
});

describe("buildKpis", () => {
  it("sums MRR bands and attaches illustrative constants", () => {
    const kpis = buildKpis(
      [
        { band: "low", mrr: 446184 },
        { band: "medium", mrr: 58736 },
        { band: "high", mrr: 36568 },
      ],
      3.25,
    );
    expect(kpis.churnRatePct).toBe(3.25);
    expect(kpis.churnTargetPct).toBe(4.0);
    expect(kpis.mrrAtRiskTotal).toBe(541488);
    expect(kpis.illustrative).toContain("projectedAnnualImpact");
  });
});
