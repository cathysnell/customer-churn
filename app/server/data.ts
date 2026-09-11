// Data layer — the high-level operations the routes call, wiring the pure SQL layer
// to the executors. Exposed behind the `DataApi` interface so routes can be tested
// against an in-memory mock with no live connections.

import type {
  AtRiskFilters,
  AtRiskUser,
  GenieAnswer,
  GeoChurn,
  Kpis,
  OutreachResult,
  TrendPoint,
  UserDetail,
} from "../shared/api.js";
import type { AppConfig } from "./config.js";
import { queryWarehouse } from "./databricks.js";
import { queryDoNow } from "./lakebase.js";
import { askGenie } from "./genie.js";
import {
  atRiskSql,
  buildKpis,
  geoChurnSql,
  latestChurnPct,
  latestChurnSql,
  mapAtRisk,
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
  getUser(id: string): Promise<UserDetail | null>;
  ask(question: string): Promise<GenieAnswer>;
  outreach(userId: string): OutreachResult;
  doNowSource(): "lakebase" | "warehouse";
}

export function createDataApi(cfg: AppConfig): DataApi {
  const cat = cfg.catalog;
  const wh = (sql: string) => queryWarehouse(cfg, sql);

  return {
    async getKpis() {
      const [mrrRows, churnRows] = await Promise.all([
        wh(mrrByBandSql(cat)),
        wh(latestChurnSql(cat)),
      ]);
      return buildKpis(mapMrrByBand(mrrRows), latestChurnPct(churnRows));
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
    async getUser(id) {
      const rows = await wh(userDetailSql(cat, id));
      return mapUserDetail(rows[0]);
    },
    async ask(question) {
      return askGenie(cfg, question);
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
