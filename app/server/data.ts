// Data layer — the high-level operations the routes call, wiring the pure SQL layer
// to the executors. Exposed behind the `DataApi` interface so routes can be tested
// against an in-memory mock with no live connections.

import type {
  AtRiskFilters,
  AtRiskUser,
  CodingPoint,
  GenieAnswer,
  GeoChurn,
  Kpis,
  OutreachResult,
  SoWhat,
  TrendPoint,
  UserDetail,
} from "../shared/api.js";
import type { AppConfig, LakebaseConfig } from "./config.js";
import {
  NARRATIVE_TTL_MS,
  SO_WHAT_CACHE_KEY,
  SO_WHAT_FALLBACK,
  SO_WHAT_PROMPT,
} from "./constants.js";
import { queryWarehouse } from "./databricks.js";
import { queryDoNow, readNarrative, writeNarrative } from "./lakebase.js";
import { askGenie, cleanNarrative } from "./genie.js";
import {
  activeSubscribersSql,
  atRiskSql,
  buildKpis,
  codingHistorySql,
  doNowCountSql,
  geoChurnSql,
  latestChurnPct,
  latestChurnSql,
  num,
  mapAtRisk,
  mapCodingHistory,
  mapGeo,
  mapMrrByBand,
  mapTrend,
  mapUserDetail,
  mrrByBandSql,
  trendSql,
  userDetailSql,
} from "./sql.js";

export interface DataApi {
  getKpis(): Promise<Kpis>;
  getTrend(): Promise<TrendPoint[]>;
  getGeoChurn(): Promise<GeoChurn[]>;
  getAtRisk(filters: AtRiskFilters): Promise<AtRiskUser[]>;
  getDoNow(limit: number): Promise<AtRiskUser[]>;
  getDoNowCount(): Promise<number>;
  getUser(id: string): Promise<UserDetail | null>;
  getCodingHistory(id: string, months: number): Promise<CodingPoint[]>;
  ask(question: string): Promise<GenieAnswer>;
  getSoWhat(): Promise<SoWhat>;
  outreach(userId: string): OutreachResult;
  doNowSource(): "lakebase" | "warehouse";
}

export function createDataApi(cfg: AppConfig): DataApi {
  const cat = cfg.catalog;
  const wh = (sql: string) => queryWarehouse(cfg, sql);

  const fallbackNarrative = (): SoWhat => ({
    body: SO_WHAT_FALLBACK,
    generatedAt: new Date().toISOString(),
    source: "fallback",
  });

  // Ask Genie for a fresh qualitative narrative, tidy it, and cache it in Lakebase.
  // On any Genie failure, cache the templated fallback so we don't re-hit Genie on
  // every page load (the box refreshes on the next weekly window or redeploy).
  async function refreshNarrative(lb: LakebaseConfig): Promise<SoWhat> {
    try {
      const ans = await askGenie(cfg, SO_WHAT_PROMPT);
      const body = cleanNarrative(ans.text);
      if (!body) throw new Error("empty genie narrative");
      await writeNarrative(lb, SO_WHAT_CACHE_KEY, body, "genie");
      return { body, generatedAt: new Date().toISOString(), source: "genie" };
    } catch {
      try {
        await writeNarrative(lb, SO_WHAT_CACHE_KEY, SO_WHAT_FALLBACK, "fallback");
      } catch {
        /* cache write best-effort */
      }
      return fallbackNarrative();
    }
  }

  return {
    async getKpis() {
      const [mrrRows, churnRows, activeRows] = await Promise.all([
        wh(mrrByBandSql(cat)),
        wh(latestChurnSql(cat)),
        wh(activeSubscribersSql(cat)),
      ]);
      return buildKpis(mapMrrByBand(mrrRows), latestChurnPct(churnRows), num(activeRows[0]?.n));
    },
    async getTrend() {
      return mapTrend(await wh(trendSql(cat)));
    },
    async getGeoChurn() {
      return mapGeo(await wh(geoChurnSql(cat)));
    },
    async getAtRisk(filters) {
      return mapAtRisk(await wh(atRiskSql(cat, filters)));
    },
    async getDoNow(limit) {
      if (cfg.lakebase) return mapAtRisk(await queryDoNow(cfg.lakebase, limit));
      // Fallback: same cohort via the warehouse.
      return mapAtRisk(
        await wh(atRiskSql(cat, { band: "high", noCrm: true, limit })),
      );
    },
    async getDoNowCount() {
      // Uncapped COUNT from the governed warehouse — the banner's true cohort size,
      // independent of the (capped) row list above.
      const rows = await wh(doNowCountSql(cat));
      return Math.round(num(rows[0]?.n));
    },
    async getUser(id) {
      const rows = await wh(userDetailSql(cat, id));
      return mapUserDetail(rows[0]);
    },
    async getCodingHistory(id, months) {
      return mapCodingHistory(await wh(codingHistorySql(cat, id, months)));
    },
    async ask(question) {
      return askGenie(cfg, question);
    },
    async getSoWhat() {
      // No Lakebase wired → serve the templated fallback (fast, no pill, no cache).
      if (!cfg.lakebase) return fallbackNarrative();
      const lb = cfg.lakebase;

      let cached;
      try {
        cached = await readNarrative(lb, SO_WHAT_CACHE_KEY);
      } catch {
        // Cache table missing / read failed — degrade to fallback without caching.
        return fallbackNarrative();
      }

      const toDto = (r: NonNullable<typeof cached>): SoWhat => ({
        body: r.body,
        generatedAt: r.generatedAt,
        source: r.source === "genie" ? "genie" : "fallback",
      });
      const fresh =
        cached != null && Date.now() - Date.parse(cached.generatedAt) < NARRATIVE_TTL_MS;

      if (cached && fresh) return toDto(cached);
      if (cached) {
        // Stale-while-revalidate: return the stale copy now, refresh in the background.
        void refreshNarrative(lb).catch(() => {});
        return toDto(cached);
      }
      // Nothing cached yet — generate synchronously on this first load.
      return refreshNarrative(lb);
    },
    outreach(userId) {
      // This build never sends externally — the action is logged in-memory only.
      return { logged: true, userId, simulated: true };
    },
    doNowSource() {
      return cfg.lakebase ? "lakebase" : "warehouse";
    },
  };
}
