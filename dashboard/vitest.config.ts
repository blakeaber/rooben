import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  esbuild: {
    jsx: "automatic",
    jsxImportSource: "react",
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    // Only pick up our test.tsx files — avoid collecting node_modules or .next
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: [
        "src/components/workflows/StatusBadge.tsx",
        "src/components/shared/EmptyStateCard.tsx",
        "src/components/shared/BudgetGauge.tsx",
        "src/components/setup/SetupGate.tsx",
        "src/components/layout/Sidebar.tsx",
      ],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
