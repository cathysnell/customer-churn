// SQL warehouse executor. Thin wrapper over @databricks/sql that runs a statement
// and returns rows as plain objects keyed by column alias.

import { DBSQLClient } from "@databricks/sql";
import type { AppConfig } from "./config.js";
import type { Row } from "./sql.js";

export async function queryWarehouse(cfg: AppConfig, sql: string): Promise<Row[]> {
  const client = new DBSQLClient();
  const host = cfg.host.replace(/^https?:\/\//, "");
  await client.connect({ host, path: cfg.warehouseHttpPath, token: cfg.token });
  try {
    const session = await client.openSession();
    try {
      const op = await session.executeStatement(sql, { runAsync: true });
      const rows = (await op.fetchAll()) as Row[];
      await op.close();
      return rows;
    } finally {
      await session.close();
    }
  } finally {
    await client.close();
  }
}
