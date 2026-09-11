import Fastify from "fastify";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AtRiskUser,
  GenieAnswer,
  Kpis,
  UserDetail,
} from "../shared/api.js";
import type { DataApi } from "./data.js";
import { buildRoutes } from "./routes.js";

const sampleUser: AtRiskUser = {
  userId: "usr_1", geo: "NA", persona: "team_lead", plan: "pro_team_monthly",
  mrr: 180, score: 0.94, band: "high", codingTrend: 0.62, crmTouches: 0,
};
const sampleKpis: Kpis = {
  churnRatePct: 3.25, churnTargetPct: 4, churnBaselinePct: 4.7,
  mrrAtRiskTotal: 541488, mrrAtRiskByBand: [{ band: "high", mrr: 36568 }],
  reactivationPct: 9.8, reactivationBaselinePct: 8, projectedAnnualImpact: 2580000,
  illustrative: ["projectedAnnualImpact"],
};

function mockDeps(over: Partial<DataApi> = {}): DataApi {
  return {
    getKpis: vi.fn(async () => sampleKpis),
    getTrend: vi.fn(async () => [{ month: "2026-08-01", churnRatePct: 3.25 }]),
    getGeoChurn: vi.fn(async () => [{ geo: "LATAM", churnRatePct: 3.99 }]),
    getAtRisk: vi.fn(async () => [sampleUser]),
    getDoNow: vi.fn(async () => [sampleUser]),
    getUser: vi.fn(async () => ({ ...sampleUser, avgAcceptanceRate: 0.24, avgSessionFrequency: 2.1, supportTickets: 3, tenureMonths: 14, isCurrentlySubscribed: true }) as UserDetail),
    ask: vi.fn(async (q: string): Promise<GenieAnswer> => ({ question: q, text: "answer", sql: "SELECT 1", columns: ["a"], rows: [[1]] })),
    outreach: vi.fn((userId: string) => ({ logged: true as const, userId, simulated: true as const })),
    doNowSource: vi.fn(() => "lakebase" as const),
    ...over,
  };
}

async function makeApp(deps: DataApi) {
  const app = Fastify();
  await app.register(buildRoutes(deps));
  await app.ready();
  return app;
}

describe("routes", () => {
  let deps: DataApi;
  beforeEach(() => {
    deps = mockDeps();
  });

  it("GET /api/health reports the do-now source", async () => {
    const app = await makeApp(deps);
    const res = await app.inject({ method: "GET", url: "/api/health" });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual({ status: "ok", doNowSource: "lakebase" });
  });

  it("GET /api/kpis returns the KPI DTO", async () => {
    const app = await makeApp(deps);
    const res = await app.inject({ method: "GET", url: "/api/kpis" });
    expect(res.json().mrrAtRiskTotal).toBe(541488);
  });

  it("GET /api/at-risk passes validated filters through", async () => {
    const app = await makeApp(deps);
    const res = await app.inject({ method: "GET", url: "/api/at-risk?band=high&geo=LATAM&noCrm=true&limit=25" });
    expect(res.statusCode).toBe(200);
    expect(deps.getAtRisk).toHaveBeenCalledWith({ band: "high", geo: "LATAM", noCrm: true, limit: 25 });
  });

  it("GET /api/at-risk 400s on a bad band", async () => {
    const app = await makeApp(deps);
    const res = await app.inject({ method: "GET", url: "/api/at-risk?band=bogus" });
    expect(res.statusCode).toBe(400);
    expect(deps.getAtRisk).not.toHaveBeenCalled();
  });

  it("GET /api/user/:id 400s on an invalid id and 404s when missing", async () => {
    const app = await makeApp(mockDeps({ getUser: vi.fn(async () => null) }));
    expect((await app.inject({ method: "GET", url: "/api/user/bad'id" })).statusCode).toBe(400);
    expect((await app.inject({ method: "GET", url: "/api/user/usr_x" })).statusCode).toBe(404);
  });

  it("POST /api/genie/query requires a question", async () => {
    const app = await makeApp(deps);
    expect((await app.inject({ method: "POST", url: "/api/genie/query", payload: {} })).statusCode).toBe(400);
    const ok = await app.inject({ method: "POST", url: "/api/genie/query", payload: { question: "churn?" } });
    expect(ok.json().sql).toBe("SELECT 1");
  });

  it("POST /api/outreach is simulated-only", async () => {
    const app = await makeApp(deps);
    const res = await app.inject({ method: "POST", url: "/api/outreach", payload: { userId: "usr_1" } });
    expect(res.json()).toEqual({ logged: true, userId: "usr_1", simulated: true });
  });
});
