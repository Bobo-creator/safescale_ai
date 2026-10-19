import { defineConfig, devices } from "@playwright/test";

// Local: starts the API (real models, Supabase) and the dev server. Deployed: set BASE_URL and
// run only the @smoke tests, e.g. BASE_URL=https://… npx playwright test --grep @smoke
const baseURL = process.env.BASE_URL ?? "http://localhost:3000";
const local = !process.env.BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 30_000 }, // explanations take ~10 s
  fullyParallel: false, // each test calls paid APIs; keep them sequential and cheap
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: { baseURL, trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "phone", use: { ...devices["Pixel 7"] }, grep: /@phone/ },
  ],
  webServer: local
    ? [
        {
          command: "uv run uvicorn safescale.api.app:app --port 8000",
          cwd: "../pipeline",
          url: "http://127.0.0.1:8000/api/health",
          reuseExistingServer: false,
          timeout: 60_000,
          env: {
            RATE_LIMIT_SALT: "e2e",
            // The whole suite comes from one IP; production limits stay as configured.
            LIMIT_ANALYSES_PER_HOUR: "200",
            LIMIT_EXPLANATIONS_PER_HOUR: "100",
          },
        },
        {
          command: "npm run dev -- --port 3000",
          url: "http://localhost:3000",
          reuseExistingServer: false,
          timeout: 60_000,
        },
      ]
    : undefined,
});
