import { describe, expect, it } from "vitest";
import { DO_NOW_SQL, READ_NARRATIVE_SQL, UPSERT_NARRATIVE_SQL } from "./lakebase.js";

describe("lakebase SQL", () => {
  it("do-now query joins predictions + serving on the untouched high-risk cohort", () => {
    expect(DO_NOW_SQL).toContain("public.churn_predictions");
    expect(DO_NOW_SQL).toContain("public.churn_serving");
    expect(DO_NOW_SQL).toContain("p.churn_risk_band = 'high'");
    expect(DO_NOW_SQL).toContain("s.crm_touches_30d = 0");
    expect(DO_NOW_SQL).toContain("LIMIT $1");
  });

  it("narrative read/upsert target public.app_narrative and upsert on the key", () => {
    expect(READ_NARRATIVE_SQL).toContain("public.app_narrative");
    expect(READ_NARRATIVE_SQL).toContain("WHERE cache_key = $1");
    expect(UPSERT_NARRATIVE_SQL).toContain("INSERT INTO public.app_narrative");
    expect(UPSERT_NARRATIVE_SQL).toContain("ON CONFLICT (cache_key) DO UPDATE");
  });
});
