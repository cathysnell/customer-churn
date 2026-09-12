// Typed API client. Talks to the Fastify backend; shapes come from the shared contract.

import type {
  AtRiskFilters,
  AtRiskUser,
  CodingPoint,
  GenieAnswer,
  GeoChurn,
  Kpis,
  OutreachResult,
  TrendPoint,
  UserDetail,
} from "../../shared/api";

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${url}`);
  return (await res.json()) as T;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${url}`);
  return (await res.json()) as T;
}

/** Pure — builds the /api/at-risk querystring from filters (exported for testing). */
export function atRiskUrl(f: AtRiskFilters = {}): string {
  const p = new URLSearchParams();
  if (f.band) p.set("band", f.band);
  if (f.geo) p.set("geo", f.geo);
  if (f.noCrm) p.set("noCrm", "true");
  if (f.minScore !== undefined) p.set("minScore", String(f.minScore));
  if (f.limit !== undefined) p.set("limit", String(f.limit));
  const qs = p.toString();
  return qs ? `/api/at-risk?${qs}` : "/api/at-risk";
}

export const api = {
  kpis: () => getJson<Kpis>("/api/kpis"),
  trend: () => getJson<TrendPoint[]>("/api/trend"),
  geoChurn: () => getJson<GeoChurn[]>("/api/geo-churn"),
  atRisk: (f: AtRiskFilters = {}) => getJson<AtRiskUser[]>(atRiskUrl(f)),
  doNow: (limit = 100) => getJson<AtRiskUser[]>(`/api/do-now?limit=${limit}`),
  doNowCount: () => getJson<{ count: number }>("/api/do-now/count"),
  user: (id: string) => getJson<UserDetail>(`/api/user/${encodeURIComponent(id)}`),
  codingHistory: (id: string, months = 3) =>
    getJson<CodingPoint[]>(`/api/user/${encodeURIComponent(id)}/coding-history?months=${months}`),
  ask: (question: string) => postJson<GenieAnswer>("/api/genie/query", { question }),
  outreach: (userId: string) => postJson<OutreachResult>("/api/outreach", { userId }),
};
