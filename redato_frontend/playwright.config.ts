import { defineConfig, devices } from "@playwright/test";

const isCI = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./tests-e2e",
  testMatch: /.*\.spec\.ts$/,
  // Tests share a stateful mock-backend (in-memory). Rodar em paralelo
  // gerava races (atividade criada num teste vazia o catalog do outro,
  // aluno marcado inativo some da lista do próximo). Custo: ~30-40s vs
  // ~10s. Aceitável pra smoke tests determinísticos.
  fullyParallel: false,
  workers: 1,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  reporter: isCI ? "github" : [["list"]],
  use: {
    baseURL: "http://localhost:3010",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "node tests-e2e/mock-backend.mjs",
      port: 8091,
      reuseExistingServer: !isCI,
      env: { MOCK_PORT: "8091" },
    },
    {
      command: "npx next dev -p 3010",
      port: 3010,
      reuseExistingServer: !isCI,
      env: {
        NEXT_PUBLIC_API_URL: "http://localhost:8091",
        REDATO_SESSION_COOKIE: "redato_session",
      },
    },
  ],
});
