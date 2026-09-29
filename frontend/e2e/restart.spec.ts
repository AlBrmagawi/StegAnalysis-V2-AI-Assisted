import { test, expect } from "@playwright/test";
import { execFile, spawn, type ChildProcess } from "node:child_process";
import net from "node:net";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

test("browser notes and report persist across an actual API process restart", async ({
  page,
  request,
}) => {
  const root = path.resolve("..");
  const port = await new Promise<number>((resolve, reject) => {
    const socket = net.createServer();
    socket.once("error", reject);
    socket.listen(0, "127.0.0.1", () => {
      const address = socket.address() as net.AddressInfo;
      socket.close(() => resolve(address.port));
    });
  });
  const baseURL = `http://127.0.0.1:${port}`;
  const python = path.join(
    root,
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
  const data = await fs.mkdtemp(
    path.join(os.tmpdir(), "steganalysis-browser-"),
  );
  let server: ChildProcess | undefined;
  const start = async () => {
    server = spawn(
      python,
      ["-m", "steganalysis.cli", "serve", "--port", String(port)],
      {
        cwd: root,
        env: { ...process.env, STEG_DATA_DIR: data },
        stdio: "ignore",
        windowsHide: true,
      },
    );
    await expect
      .poll(
        async () => {
          try {
            return (await request.get(`${baseURL}/api/cases`)).status();
          } catch {
            return 0;
          }
        },
        { timeout: 30000 },
      )
      .toBe(200);
  };
  const stop = async () => {
    if (server && server.exitCode === null) {
      const child = server;
      await new Promise<void>((resolve, reject) => {
        const timer = setTimeout(
          () => reject(new Error("Server did not stop")),
          10000,
        );
        child.once("exit", () => {
          clearTimeout(timer);
          resolve();
        });
        if (process.platform === "win32" && child.pid) {
          execFile(
            "taskkill",
            ["/PID", String(child.pid), "/T", "/F"],
            { windowsHide: true },
            (error) => {
              if (error && child.exitCode === null) reject(error);
            },
          );
        } else {
          child.kill("SIGTERM");
        }
      });
      await expect
        .poll(
          async () => {
            try {
              return (
                await request.get(`${baseURL}/api/cases`, { timeout: 1000 })
              ).status();
            } catch {
              return 0;
            }
          },
          { timeout: 15000 },
        )
        .toBe(0);
    }
  };
  try {
    await start();
    await page.goto(baseURL);
    await page.getByRole("button", { name: "New case", exact: true }).click();
    await page.getByLabel("Case name").fill("Restart persistence proof");
    await page
      .getByRole("button", { name: "Create case", exact: true })
      .click();
    await page.getByLabel("Evidence files").setInputFiles({
      name: "generated.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Benign  text with a spacing indicator.\n"),
    });
    await page.getByRole("button", { name: "Add 1 file", exact: true }).click();
    await page.getByRole("radio", { name: /Quick/ }).check();
    await page
      .getByRole("button", { name: "Start analysis", exact: true })
      .click();
    await expect(
      page.getByText("Unusual whitespace sequences", { exact: true }),
    ).toBeVisible({ timeout: 60000 });
    await expect(
      page.getByRole("button", { name: "Run analysis", exact: true }),
    ).toBeEnabled();
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await page
      .getByLabel("Case notes")
      .fill("Preserved across a stopped and restarted API process.");
    await page.getByRole("button", { name: "Save notes", exact: true }).click();
    await expect(page.getByText("Case notes saved.")).toBeVisible();
    await stop();
    await start();
    await page.reload();
    await page
      .getByRole("button")
      .filter({ hasText: "Restart persistence proof" })
      .click();
    await page.getByRole("tab", { name: "Notes", exact: true }).click();
    await expect(page.getByLabel("Case notes")).toHaveValue(
      "Preserved across a stopped and restarted API process.",
    );
    const list = await (await request.get(`${baseURL}/api/cases`)).json();
    const report = await request.get(
      `${baseURL}/api/cases/${list[0].id}/report.json`,
    );
    expect((await report.json()).case.notes).toContain("Preserved across");
  } finally {
    await stop();
    const resolved = path.resolve(data);
    if (
      resolved.startsWith(path.resolve(os.tmpdir()) + path.sep) &&
      path.basename(resolved).startsWith("steganalysis-browser-")
    ) {
      await fs.rm(resolved, {
        recursive: true,
        force: true,
        maxRetries: 10,
        retryDelay: 200,
      });
    }
  }
});
