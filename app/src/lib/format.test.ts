import { describe, expect, it } from "vitest";
import { geoSeverity, money, moneyShort, pct, trendArrow, trendClass, trendLabel } from "./format";
import { atRiskUrl } from "./api";

describe("formatters", () => {
  it("money rounds and groups", () => {
    expect(money(36568.4)).toBe("$36,568");
    expect(money(541488)).toBe("$541,488");
  });
  it("moneyShort abbreviates", () => {
    expect(moneyShort(2_580_000)).toBe("$2.58M");
    expect(moneyShort(36568)).toBe("$36.6K");
    expect(moneyShort(180)).toBe("$180");
  });
  it("pct fixes digits", () => {
    expect(pct(3.25)).toBe("3.25%");
    expect(pct(4, 1)).toBe("4.0%");
  });
  it("trend arrow + class by direction (1.0 = flat, ±3% dead-band)", () => {
    expect(trendClass(0.62)).toBe("dn"); // −38%, declining
    expect(trendArrow(0.62)).toBe("▼");
    expect(trendClass(0.0)).toBe("dn"); // coding stopped = worst, not flat
    expect(trendClass(1.0)).toBe("flat"); // unchanged
    expect(trendArrow(1.0)).toBe("—");
    expect(trendClass(0.97)).toBe("flat"); // within dead-band
    expect(trendClass(1.1)).toBe("up"); // +10%, growing
    expect(trendArrow(1.1)).toBe("▲");
  });

  it("trendLabel: percent change from flat, unsigned (arrow gives direction)", () => {
    expect(trendLabel(1.0)).toBe("flat");
    expect(trendLabel(0.97)).toBe("flat");
    expect(trendLabel(0.62)).toBe("38%");
    expect(trendLabel(0.0)).toBe("100%");
    expect(trendLabel(1.78)).toBe("78%");
  });
  it("geoSeverity buckets churn", () => {
    expect(geoSeverity(3.99)).toBe("high");
    expect(geoSeverity(3.48)).toBe("medium");
    expect(geoSeverity(3.06)).toBe("low");
  });
});

describe("atRiskUrl", () => {
  it("builds a bare url with no filters", () => {
    expect(atRiskUrl()).toBe("/api/at-risk");
  });
  it("serializes filters", () => {
    expect(atRiskUrl({ band: "high", geo: "LATAM", noCrm: true, limit: 25 })).toBe(
      "/api/at-risk?band=high&geo=LATAM&noCrm=true&limit=25",
    );
  });
});
