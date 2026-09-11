import { describe, expect, it } from "vitest";
import { loadConfig, missingWarehouseConfig } from "./config.js";

describe("loadConfig", () => {
  it("normalizes the host and derives the warehouse http path", () => {
    const cfg = loadConfig({
      DATABRICKS_HOST: "example.cloud.databricks.com/",
      DATABRICKS_TOKEN: "dapi123",
      DATABRICKS_WAREHOUSE_ID: "128c306447d9ef00",
    });
    expect(cfg.host).toBe("https://example.cloud.databricks.com");
    expect(cfg.warehouseHttpPath).toBe("/sql/1.0/warehouses/128c306447d9ef00");
    expect(cfg.catalog).toBe("dev_churn");
    expect(cfg.port).toBe(8000);
  });

  it("defaults the port to DATABRICKS_APP_PORT when PORT is unset", () => {
    expect(loadConfig({ DATABRICKS_APP_PORT: "8123" }).port).toBe(8123);
    expect(loadConfig({ PORT: "9000", DATABRICKS_APP_PORT: "8123" }).port).toBe(9000);
  });

  it("disables lakebase unless host+user+password are all present", () => {
    expect(loadConfig({ LAKEBASE_HOST: "h", LAKEBASE_USER: "u" }).lakebase).toBeNull();
    const cfg = loadConfig({
      LAKEBASE_HOST: "pg.example.com",
      LAKEBASE_USER: "app_sp",
      LAKEBASE_PASSWORD: "secret",
      LAKEBASE_SSL: "false",
    });
    expect(cfg.lakebase).toMatchObject({
      host: "pg.example.com",
      database: "databricks_postgres",
      ssl: false,
    });
  });

  it("reports missing warehouse config", () => {
    expect(missingWarehouseConfig(loadConfig({}))).toEqual([
      "DATABRICKS_HOST",
      "DATABRICKS_TOKEN",
      "DATABRICKS_WAREHOUSE_ID",
    ]);
    expect(
      missingWarehouseConfig(
        loadConfig({
          DATABRICKS_HOST: "h",
          DATABRICKS_TOKEN: "t",
          DATABRICKS_WAREHOUSE_ID: "w",
        }),
      ),
    ).toEqual([]);
  });
});
