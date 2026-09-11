import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Default env is node (backend tests). Frontend component tests opt into jsdom
// with a `// @vitest-environment jsdom` docblock at the top of the file.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "node",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["server/**/*.test.ts", "src/**/*.test.{ts,tsx}"],
  },
});
