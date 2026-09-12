// HTTP routes. `buildRoutes(deps)` returns a Fastify plugin bound to a DataApi, so
// tests register it with a mock and drive it via `app.inject(...)`.

import type { FastifyPluginAsync } from "fastify";
import {
  GEOS,
  RISK_BANDS,
  type AtRiskFilters,
  type RiskBand,
} from "../shared/api.js";
import type { DataApi } from "./data.js";
import { isValidUserId } from "./sql.js";

function parseFilters(q: Record<string, unknown>): AtRiskFilters {
  const f: AtRiskFilters = {};
  const band = q.band ? String(q.band) : "";
  if (band) {
    if (!(RISK_BANDS as string[]).includes(band)) throw new BadRequest(`invalid band: ${band}`);
    f.band = band as RiskBand;
  }
  const geo = q.geo ? String(q.geo) : "";
  if (geo) {
    if (!(GEOS as readonly string[]).includes(geo)) throw new BadRequest(`invalid geo: ${geo}`);
    f.geo = geo;
  }
  if (q.noCrm !== undefined) f.noCrm = String(q.noCrm) === "true";
  if (q.minScore !== undefined) f.minScore = Number(q.minScore);
  if (q.limit !== undefined) f.limit = Number(q.limit);
  return f;
}

class BadRequest extends Error {}

export function buildRoutes(deps: DataApi): FastifyPluginAsync {
  return async (app) => {
    app.get("/api/health", async () => ({
      status: "ok",
      doNowSource: deps.doNowSource(),
    }));

    app.get("/api/kpis", async () => deps.getKpis());
    app.get("/api/trend", async () => deps.getTrend());
    app.get("/api/geo-churn", async () => deps.getGeoChurn());
    app.get("/api/overview/so-what", async () => deps.getSoWhat());

    app.get("/api/at-risk", async (req, reply) => {
      try {
        return await deps.getAtRisk(parseFilters(req.query as Record<string, unknown>));
      } catch (e) {
        if (e instanceof BadRequest) return reply.code(400).send({ error: e.message });
        throw e;
      }
    });

    app.get("/api/do-now", async (req) => {
      const q = req.query as Record<string, unknown>;
      const limit = q.limit !== undefined ? Number(q.limit) : 100;
      return deps.getDoNow(limit);
    });

    app.get("/api/do-now/count", async () => ({ count: await deps.getDoNowCount() }));

    app.get<{ Params: { id: string } }>("/api/user/:id", async (req, reply) => {
      const { id } = req.params;
      if (!isValidUserId(id)) return reply.code(400).send({ error: "invalid user id" });
      const user = await deps.getUser(id);
      if (!user) return reply.code(404).send({ error: "not found" });
      return user;
    });

    app.get<{ Params: { id: string }; Querystring: { months?: string } }>(
      "/api/user/:id/coding-history",
      async (req, reply) => {
        const { id } = req.params;
        if (!isValidUserId(id)) return reply.code(400).send({ error: "invalid user id" });
        const months = req.query.months !== undefined ? Number(req.query.months) : 3;
        return deps.getCodingHistory(id, months);
      },
    );

    app.post<{ Body: { question?: string } }>("/api/genie/query", async (req, reply) => {
      const question = (req.body?.question ?? "").trim();
      if (!question) return reply.code(400).send({ error: "question is required" });
      return deps.ask(question);
    });

    app.post<{ Body: { userId?: string } }>("/api/outreach", async (req, reply) => {
      const userId = (req.body?.userId ?? "").trim();
      if (!isValidUserId(userId)) return reply.code(400).send({ error: "invalid user id" });
      return deps.outreach(userId);
    });
  };
}
