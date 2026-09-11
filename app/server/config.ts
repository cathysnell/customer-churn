// Runtime configuration, loaded from the environment. `loadConfig` is pure (takes
// an env record) so it can be unit-tested without touching process.env.

export interface LakebaseConfig {
  host: string;
  port: number;
  database: string;
  user: string;
  password: string;
  ssl: boolean;
}

export interface AppConfig {
  host: string; // https://<workspace>
  token: string;
  warehouseId: string;
  warehouseHttpPath: string;
  genieSpaceId: string;
  catalog: string;
  port: number;
  lakebase: LakebaseConfig | null; // null → do-now queue falls back to the warehouse
}

type Env = Record<string, string | undefined>;

function normalizeHost(raw: string): string {
  let h = raw.trim().replace(/\/+$/, "");
  if (h && !/^https?:\/\//.test(h)) h = `https://${h}`;
  return h;
}

function loadLakebase(env: Env): LakebaseConfig | null {
  const host = env.LAKEBASE_HOST?.trim();
  const user = env.LAKEBASE_USER?.trim();
  const password = env.LAKEBASE_PASSWORD?.trim();
  if (!host || !user || !password) return null; // incomplete → disabled
  return {
    host,
    port: Number(env.LAKEBASE_PORT ?? 5432),
    database: env.LAKEBASE_DATABASE?.trim() || "databricks_postgres",
    user,
    password,
    ssl: (env.LAKEBASE_SSL ?? "true").toLowerCase() !== "false",
  };
}

export function loadConfig(env: Env): AppConfig {
  const host = normalizeHost(
    env.DATABRICKS_HOST ?? env.DATABRICKS_SERVER_HOSTNAME ?? "",
  );
  const warehouseId = (env.DATABRICKS_WAREHOUSE_ID ?? "").trim();
  return {
    host,
    token: env.DATABRICKS_TOKEN ?? "",
    warehouseId,
    warehouseHttpPath: warehouseId ? `/sql/1.0/warehouses/${warehouseId}` : "",
    genieSpaceId: (env.GENIE_SPACE_ID ?? "").trim(),
    catalog: (env.DATA_CATALOG ?? "dev_churn").trim(),
    port: Number(env.PORT ?? env.DATABRICKS_APP_PORT ?? 8000),
    lakebase: loadLakebase(env),
  };
}

/** Fields required for the warehouse-backed endpoints to work. */
export function missingWarehouseConfig(cfg: AppConfig): string[] {
  const missing: string[] = [];
  if (!cfg.host) missing.push("DATABRICKS_HOST");
  if (!cfg.token) missing.push("DATABRICKS_TOKEN");
  if (!cfg.warehouseId) missing.push("DATABRICKS_WAREHOUSE_ID");
  return missing;
}
