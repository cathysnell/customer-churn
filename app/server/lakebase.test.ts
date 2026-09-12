import { describe, expect, it } from "vitest";
import {
  atRiskLakebaseQuery,
  DO_NOW_SQL,
  LOG_OUTREACH_SQL,
  READ_NARRATIVE_SQL,
  UPSERT_NARRATIVE_SQL,
  USER_DETAIL_LAKEBASE_SQL,
} from "./lakebase.js";

describe("lakebase SQL", () => {
  it("do-now query joins predictions + serving and drops recently-touched users", () => {
    expect(DO_NOW_SQL).toContain("public.churn_predictions");
    expect(DO_NOW_SQL).toContain("public.churn_serving");
    expect(DO_NOW_SQL).toContain("p.churn_risk_band = 'high'");
    expect(DO_NOW_SQL).toContain("s.crm_touches_30d = 0");
    // Live outreach-log exclusion (the closed loop): drop anyone contacted in 30d.
    expect(DO_NOW_SQL).toContain("public.crm_outreach_log");
    expect(DO_NOW_SQL).toContain("INTERVAL '30 days'");
    expect(DO_NOW_SQL).toContain("LIMIT $1");
  });

  it("narrative read/upsert target public.app_narrative and upsert on the key", () => {
    expect(READ_NARRATIVE_SQL).toContain("public.app_narrative");
    expect(READ_NARRATIVE_SQL).toContain("WHERE cache_key = $1");
    expect(UPSERT_NARRATIVE_SQL).toContain("INSERT INTO public.app_narrative");
    expect(UPSERT_NARRATIVE_SQL).toContain("ON CONFLICT (cache_key) DO UPDATE");
  });

  it("user-detail query pulls the extra signal columns for the drawer", () => {
    expect(USER_DETAIL_LAKEBASE_SQL).toContain("avg_acceptance_rate");
    expect(USER_DETAIL_LAKEBASE_SQL).toContain("support_tickets");
    expect(USER_DETAIL_LAKEBASE_SQL).toContain("is_currently_subscribed");
    expect(USER_DETAIL_LAKEBASE_SQL).toContain("WHERE p.user_id = $1");
  });

  it("outreach insert targets the Lakebase-owned log", () => {
    expect(LOG_OUTREACH_SQL).toContain("INSERT INTO public.crm_outreach_log");
    expect(LOG_OUTREACH_SQL).toContain("VALUES ($1, $2, $3)");
  });
});

describe("atRiskLakebaseQuery", () => {
  it("binds only the currently-subscribed clause + limit with no filters", () => {
    const q = atRiskLakebaseQuery();
    expect(q.text).toContain("s.is_currently_subscribed = TRUE");
    expect(q.text).toContain("ORDER BY p.churn_score DESC LIMIT $1");
    expect(q.values).toEqual([100]);
  });
  it("parameterizes band/geo/minScore and appends the limit last", () => {
    const q = atRiskLakebaseQuery({ band: "high", geo: "LATAM", noCrm: true, minScore: 0.5, limit: 25 });
    expect(q.text).toContain("p.churn_risk_band = $1");
    expect(q.text).toContain("s.geo = $2");
    expect(q.text).toContain("s.crm_touches_30d = 0"); // noCrm is a literal, not a param
    expect(q.text).toContain("p.churn_score >= $3");
    expect(q.text).toContain("LIMIT $4");
    expect(q.values).toEqual(["high", "LATAM", 0.5, 25]);
  });
  it("clamps the limit to [1,500]", () => {
    expect(atRiskLakebaseQuery({ limit: 9999 }).values).toEqual([500]);
    expect(atRiskLakebaseQuery({ limit: 0 }).values).toEqual([1]);
  });
});
