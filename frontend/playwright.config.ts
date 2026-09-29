import { defineConfig } from "@playwright/test";
import path from "node:path";
const root = path.resolve("..");
const python = path.join(
  root,
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
const external = process.env.STEG_E2E_BASE_URL;
const baseURL = external || "http://127.0.0.1:18765";
export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  expect: { timeout: 15_000 },
  workers: 1,
  projects: [
    { name: "chromium", use: { browserName: "chromium" } },
    { name: "firefox", use: { browserName: "firefox" } },
    { name: "webkit", use: { browserName: "webkit" } },
  ],
  use: {
    baseURL,
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: external
    ? undefined
    : {
        command: `"${python}" scripts/e2e_server.py --port 18765`,
        cwd: root,
        url: `${baseURL}/api/cases`,
        timeout: 180_000,
        reuseExistingServer: false,
        gracefulShutdown: { signal: "SIGTERM", timeout: 10_000 },
      },
  reporter: [["list"], ["html", { open: "never" }]],
});
