import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  define: {
    "import.meta.env.VITE_API_BASE_URL": JSON.stringify("http://127.0.0.1:8031/api"),
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globalSetup: "./test-integration/globalSetup.mjs",
    include: ["src/integration/**/*.test.tsx"],
    fileParallelism: false,
  },
})
