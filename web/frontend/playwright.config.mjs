import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: /ui\\.spec\\.js/,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:5189",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    viewport: { width: 1365, height: 850 },
  },
  projects: [{ name:"Chromium", use:{ ...devices["Desktop Chrome"] } }],
  webServer: {
    command:"npm run preview -- --host 127.0.0.1 --port 5189 --strictPort",
    url:"http://127.0.0.1:5189/app",
    reuseExistingServer: !process.env.CI,
    timeout:120_000,
  },
});
