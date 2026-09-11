// Server entry. Loads config, wires the real DataApi, serves the built frontend
// (dist/) plus the /api routes, and listens on the Apps-provided port.

import { existsSync } from "node:fs";
import { join } from "node:path";
import Fastify from "fastify";
import fastifyStatic from "@fastify/static";
import { loadConfig, missingWarehouseConfig } from "./config.js";
import { createDataApi } from "./data.js";
import { buildRoutes } from "./routes.js";

const cfg = loadConfig(process.env);
const app = Fastify({ logger: true });

const missing = missingWarehouseConfig(cfg);
if (missing.length) {
  app.log.warn(
    `Missing warehouse config: ${missing.join(", ")} — data endpoints will error until set.`,
  );
}

await app.register(buildRoutes(createDataApi(cfg)));

// Serve the built SPA when present; fall back to index.html for client-side views.
const dist = join(import.meta.dirname, "..", "dist");
if (existsSync(dist)) {
  await app.register(fastifyStatic, { root: dist });
  app.setNotFoundHandler((req, reply) => {
    if (req.raw.url?.startsWith("/api")) return reply.code(404).send({ error: "not found" });
    return reply.sendFile("index.html");
  });
} else {
  app.log.warn(`No dist/ found at ${dist} — run \`npm run build\` to serve the UI.`);
}

try {
  await app.listen({ port: cfg.port, host: "0.0.0.0" });
} catch (err) {
  app.log.error(err);
  process.exit(1);
}
