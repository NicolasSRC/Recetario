import { defineConfig } from "@playwright/test";

const isWindows = process.platform === "win32";
const python =
  process.env.PYTHON ?? (isWindows ? "..\\.venv\\Scripts\\python.exe" : "python");

const apiUrl = "http://127.0.0.1:8010";
const webUrl = "http://127.0.0.1:3100";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI
    ? [["github"], ["html", { open: "never" }]]
    : [["list"]],
  use: {
    baseURL: webUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    channel: process.env.CI ? undefined : "msedge",
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn tests.e2e_app:app --host 127.0.0.1 --port 8010`,
      cwd: "../backend",
      url: `${apiUrl}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
      url: webUrl,
      env: { NEXT_PUBLIC_API_URL: apiUrl },
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
    },
  ],
});
