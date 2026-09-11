import { describe, expect, it } from "vitest";
import { geoSeverity, money, moneyShort, pct, trendArrow, trendClass } from "./format";
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
  it("trend arrow + class by direction", () => {
    expect(trendClass(0.62)).toBe("dn");
    expect(trendArrow(0.62)).toBe("▼");
    expect(trendClass(1.03)).toBe("up");
    expect(trendArrow(1.03)).toBe("▲");
    expect(trendClass(0.95)).toBe("flat");
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
