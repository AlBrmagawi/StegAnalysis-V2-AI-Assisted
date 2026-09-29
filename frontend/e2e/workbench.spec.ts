import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs/promises";
import path from "node:path";

test("real upload-to-report journey, citations, notes, provenance and reload", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByRole("button", { name: "New case", exact: true }).click();
  const name = `E2E evidence review ${Date.now()}`;
  await page.getByLabel("Case name").fill(name);
  await page
    .getByLabel("Description")
    .fill("Generated benign fixture. Real analysis, no mocked findings.");
  await page.getByRole("button", { name: "Create case", exact: true }).click();
  await page
    .getByLabel("Evidence files")
    .setInputFiles(path.resolve("../demo-fixtures/demo-lsb-landscape.png"));
  await page.getByRole("button", { name: "Add 1 file", exact: true }).click();
  await page
    .getByRole("button", { name: "Start analysis", exact: true })
    .click();
  await expect(
    page.getByText("Verified demonstration payload recovered", { exact: true }),
  ).toBeVisible({ timeout: 120_000 });
  await expect(
    page.getByRole("button", { name: "Run analysis", exact: true }),
  ).toBeEnabled({ timeout: 120_000 });
  await page
    .getByRole("button", {
      name: "Verified demonstration payload recovered",
      exact: true,
    })
    .click();
  await page
    .locator(".citation-link")
    .filter({ hasText: "recovered-demo-payload.txt" })
    .click();
  await expect(page.locator(".text-preview")).toContainText(
    "Benign StegAnalysis demonstration",
  );
  await page.getByLabel("Analyst review").selectOption("reviewed");
  await page
    .getByLabel("Review note")
    .fill("Verified generated payload and CRC; limited to demo framing.");
  await page.getByRole("button", { name: "Save review", exact: true }).click();
  await expect(page.getByText("Finding review saved.")).toBeVisible();
  await page.getByRole("tab", { name: "Provenance", exact: true }).click();
  await expect(page.locator(".provenance-node")).toHaveCount(2);
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page
    .getByLabel("Case notes")
    .fill(
      "Known demonstration payload recovered. No universal detection claim.",
    );
  await page.getByRole("button", { name: "Save notes", exact: true }).click();
  await expect(page.getByText("Case notes saved.")).toBeVisible();
  await page.getByRole("tab", { name: "Assistant", exact: true }).click();
  await page
    .getByLabel("Ask about selected evidence")
    .fill("What supports this conclusion?");
  await page
    .getByRole("button", { name: "Ask evidence guide", exact: true })
    .click();
  await expect(
    page.getByText("DETERMINISTIC GUIDE", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".citations button").first()).toContainText(
    "Verified demonstration",
  );
  await page
    .getByRole("button", { name: "Use as report draft", exact: true })
    .click();
  await expect(page.getByLabel("Report narrative")).toHaveValue(/FACTS/);
  await page
    .getByLabel("Report narrative")
    .fill(
      "Analyst reviewed the benign demonstration. Known payload recovered; scope limited to SADEMO1.",
    );
  await page
    .getByRole("button", { name: "Save narrative", exact: true })
    .click();
  await expect(page.getByText("Investigation narrative saved.")).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("link", { name: "HTML report Readable, self-contained report" })
    .click();
  const download = await downloadPromise;
  const downloadPath = await download.path();
  const html = await fs.readFile(downloadPath!, "utf8");
  expect(html).toContain("Known demonstration payload recovered.");
  expect(html).toContain("Verified demonstration payload recovered");
  expect(html).toContain("SHA-256");
  expect(html).not.toContain("<script");
  await page.reload();
  await page.getByRole("button").filter({ hasText: name }).click();
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await expect(page.getByLabel("Case notes")).toHaveValue(
    /Known demonstration payload/,
  );
  expect(errors).toEqual([]);
});

test("desktop and narrow layouts, themes, and accessible controls", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button")
    .filter({ hasText: "The quiet signal" })
    .first()
    .click();
  await expect(
    page.getByRole("region", { name: "Artifact viewer" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  await expect(page.locator("output")).toHaveText("125%");
  await page.getByLabel("Image channel").selectOption("G");
  await page.getByLabel("Image bit plane").selectOption("1");
  await expect(
    page.getByAltText("Selected derived view: G-bit-1.png"),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Measurements", exact: true }).click();
  await expect(
    page.getByRole("img", {
      name: "Shannon entropy from zero to eight bits per byte",
    }),
  ).toBeVisible();
  let accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  await page
    .getByRole("button", { name: "Switch to light theme", exact: true })
    .click();
  accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  await page.screenshot({ path: "../docs/screenshots/measurements-light.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page.getByLabel("Case notes").scrollIntoViewIfNeeded();
  await expect(
    page.getByRole("button", { name: "Save notes", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  ).toBe(false);
  await page
    .getByRole("button", { name: "Settings and tool health", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Settings & capabilities", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  ).toBe(false);
  await page.screenshot({ path: "../docs/screenshots/settings-narrow.png" });
});

test("cancel and retry plus malformed and unsupported evidence states", async ({
  page,
  request,
}) => {
  const headers = { "X-Steganalysis": "local" };
  const response = await request.post("/api/cases", {
    headers,
    data: { name: `E2E states ${Date.now()}` },
  });
  const c = await response.json();
  const upload = await request.post(`/api/cases/${c.id}/evidence`, {
    headers,
    multipart: {
      file: {
        name: "malformed.pdf",
        mimeType: "application/pdf",
        buffer: Buffer.from("%PDF-1.7\nmalformed"),
      },
    },
  });
  const a = await upload.json();
  const job = await (
    await request.post(`/api/cases/${c.id}/jobs`, {
      headers,
      data: { artifact_ids: [a.id], profile: "deep" },
    })
  ).json();
  await request.post(`/api/cases/${c.id}/jobs/${job.id}/cancel`, { headers });
  await page.goto("/");
  await page.getByRole("button").filter({ hasText: c.name }).click();
  await expect(page.getByText(/Last run cancelled/)).toBeVisible({
    timeout: 30_000,
  });
  await page
    .getByRole("button", { name: "Retry analysis", exact: true })
    .click();
  await expect(page.getByText(/Last run failed/)).toBeVisible({
    timeout: 120_000,
  });
  await page.getByRole("tab", { name: "Run history", exact: true }).click();
  await expect(
    page.locator(".run-row .badge").filter({ hasText: "failed" }),
  ).toBeVisible();
  const binary = await (
    await request.post(`/api/cases/${c.id}/evidence`, {
      headers,
      multipart: {
        file: {
          name: "unsupported.bin",
          mimeType: "application/octet-stream",
          buffer: Buffer.from([0, 1, 2, 3, 4, 5]),
        },
      },
    })
  ).json();
  await request.post(`/api/cases/${c.id}/jobs`, {
    headers,
    data: { artifact_ids: [binary.id], profile: "quick" },
  });
  await expect
    .poll(
      async () => {
        const state = await (await request.get(`/api/cases/${c.id}`)).json();
        return state.runs.some(
          (r: { status: string }) => r.status === "unsupported",
        );
      },
      { timeout: 120_000 },
    )
    .toBe(true);
  await page.reload();
  await page.getByRole("button").filter({ hasText: c.name }).click();
  await page.getByRole("tab", { name: "Run history", exact: true }).click();
  await expect(
    page.locator(".run-row .badge").filter({ hasText: "unsupported" }),
  ).toBeVisible();
});
