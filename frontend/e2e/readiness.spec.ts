import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs/promises";

const headers = { "X-Steganalysis": "local" };
async function demo(page: Page) {
  await page.goto("/");
  await page
    .getByRole("button")
    .filter({ hasText: "The quiet signal" })
    .first()
    .click();
  await expect(
    page.getByRole("region", { name: "Artifact viewer" }),
  ).toBeVisible();
}
async function accessibility(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    result.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.target),
    })),
  ).toEqual([]);
}

test("case search, sorting, named dialogs, keyboard focus and Escape", async ({
  page,
  request,
}) => {
  const suffix = Date.now();
  for (const name of [`Zebra keyboard ${suffix}`, `Alpha keyboard ${suffix}`]) {
    expect(
      (await request.post("/api/cases", { headers, data: { name } })).status(),
    ).toBe(201);
  }
  await page.goto("/");
  await page.getByLabel("Search cases").fill(`keyboard ${suffix}`);
  await page.getByLabel("Sort cases").selectOption("name");
  const matches = page.locator(".case-row");
  await expect(matches).toHaveCount(2);
  await expect(matches.first()).toContainText("Alpha keyboard");
  await page.getByLabel("Search cases").fill("no-such-investigation");
  await expect(matches).toHaveCount(0);
  await page.getByRole("button", { name: "New case", exact: true }).focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog");
  await expect(dialog).toHaveAccessibleName("New investigation");
  await expect(page.getByLabel("Case name")).toBeFocused();
  await expect(
    page.getByRole("button", { name: "Create case", exact: true }),
  ).toBeDisabled();
  await accessibility(page);
  for (let i = 0; i < 8; i++) {
    await page.keyboard.press("Tab");
    expect(
      await dialog.evaluate((el) => el.contains(document.activeElement)),
    ).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "New case", exact: true }),
  ).toBeFocused();
});

test("upload validation, drag-and-drop, removal, and duplicate identity", async ({
  page,
  request,
}) => {
  const name = `Upload controls ${Date.now()}`;
  const c = await (
    await request.post("/api/cases", { headers, data: { name } })
  ).json();
  await page.goto("/");
  await page.getByRole("button").filter({ hasText: name }).click();
  await page
    .getByRole("button", { name: "Add evidence", exact: true })
    .first()
    .click();
  await page.getByLabel("Evidence files").setInputFiles({
    name: "empty.txt",
    mimeType: "text/plain",
    buffer: Buffer.alloc(0),
  });
  await expect(page.getByRole("alert")).toContainText("must contain data");
  const transfer = await page.evaluateHandle(() => {
    const data = new DataTransfer();
    data.items.add(
      new File(["Safe duplicate bytes\n"], "dropped.txt", {
        type: "text/plain",
      }),
    );
    return data;
  });
  await page
    .locator(".dropzone")
    .dispatchEvent("drop", { dataTransfer: transfer });
  await expect(
    page.getByRole("button", { name: "Remove dropped.txt" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Remove dropped.txt" }).click();
  await expect(
    page.getByRole("button", { name: "Add files", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Evidence files").setInputFiles([
    {
      name: "first.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Safe duplicate bytes\n"),
    },
    {
      name: "renamed.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Safe duplicate bytes\n"),
    },
  ]);
  await accessibility(page);
  await page.getByRole("button", { name: "Add 2 files", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveAccessibleName(
    "Configure analysis",
  );
  const snapshot = await (await request.get(`/api/cases/${c.id}`)).json();
  expect(snapshot.artifacts).toHaveLength(1);
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
});

test("PDF attachment, Unicode locations, WAV playback, waveform and spectrogram", async ({
  page,
}) => {
  await demo(page);
  const tree = page.getByRole("complementary", { name: "Evidence tree" });
  await tree
    .getByRole("button")
    .filter({ hasText: "demo-attachment.pdf" })
    .first()
    .click();
  await expect(
    page.getByRole("region", { name: "Artifact viewer" }),
  ).toContainText("known-attachment.txt");
  await tree
    .getByRole("button")
    .filter({ hasText: "known-attachment.txt" })
    .first()
    .click();
  await expect(page.locator(".text-preview")).toContainText(
    "Known benign PDF attachment",
  );
  await tree
    .getByRole("button")
    .filter({ hasText: "demo-unicode.txt" })
    .first()
    .click();
  await expect(page.locator(".text-preview")).toContainText(
    "Investigation note",
  );
  await page.getByLabel("Search findings").fill("Invisible Unicode");
  await page.locator(".finding-title").first().click();
  await expect(page.locator(".finding-detail")).toContainText("byte");
  await tree
    .getByRole("button")
    .filter({ hasText: "demo-sample-lsb.wav" })
    .first()
    .click();
  await expect(page.locator("audio")).toBeVisible();
  await expect
    .poll(() =>
      page.locator("audio").evaluate((el: HTMLAudioElement) => el.readyState),
    )
    .toBeGreaterThan(0);
  await page.locator("audio").evaluate((el: HTMLAudioElement) => el.play());
  await expect
    .poll(() =>
      page.locator("audio").evaluate((el: HTMLAudioElement) => el.currentTime),
    )
    .toBeGreaterThan(0);
  await expect(page.getByRole("img", { name: /waveform/i })).toBeVisible();
  await expect(page.getByRole("img", { name: /spectrogram/i })).toBeVisible();
});

test("image views, synchronized pan, keyboard resize and finding filters", async ({
  page,
}) => {
  await demo(page);
  await page.getByRole("tab", { name: "Preview", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("tab", { name: "Measurements", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("End");
  await expect(
    page.getByRole("tab", { name: "Run history", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Home");
  await expect(
    page.getByRole("tab", { name: "Preview", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  const separator = page.getByRole("separator", {
    name: "Resize evidence tree",
  });
  const before = Number(await separator.getAttribute("aria-valuenow"));
  await separator.focus();
  await page.keyboard.press("ArrowRight");
  await expect(separator).toHaveAttribute("aria-valuenow", String(before + 20));
  for (const mode of [
    "channel",
    "negative",
    "grayscale",
    "residual",
    "bit-plane",
  ]) {
    await page.getByLabel("Derived image view").selectOption(mode);
    await expect(page.getByAltText(/Selected derived view:/)).toBeVisible();
  }
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  const frame = page.locator(".image-frame").first();
  const box = (await frame.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    box.x + box.width / 2 + 35,
    box.y + box.height / 2 + 20,
  );
  await page.mouse.up();
  const transforms = await page
    .locator(".image-frame img")
    .evaluateAll((images) =>
      images.map((img) => (img as HTMLElement).style.transform),
    );
  expect(transforms).toHaveLength(2);
  expect(transforms[0]).toEqual(transforms[1]);
  expect(transforms[0]).toContain("35px");
  await page.getByRole("button", { name: "Reset image view" }).click();
  await expect(page.locator("output")).toHaveText("100%");
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await expect(page.locator(".image-frame img")).toHaveCount(1);
  await page.getByLabel("Filter finding category").selectOption("recovered");
  await expect(page.locator(".finding-card")).toHaveCount(2);
  await page.getByLabel("Sort findings").selectOption("title");
  await page.getByLabel("Search findings").fill("no-such-finding");
  await expect(page.locator(".finding-card")).toHaveCount(0);
});

test("failed uploads can be retried, and Escape cannot hide an active upload", async ({
  page,
  request,
}) => {
  const name = `Upload retry ${Date.now()}`;
  const c = await (
    await request.post("/api/cases", { headers, data: { name } })
  ).json();
  await page.goto("/");
  await page.getByRole("button").filter({ hasText: name }).click();
  await page
    .getByRole("button", { name: "Add evidence", exact: true })
    .first()
    .click();
  await page.getByLabel("Evidence files").setInputFiles(
    Array.from({ length: 17 }, (_, i) => ({
      name: `file-${i}.txt`,
      mimeType: "text/plain",
      buffer: Buffer.from("small"),
    })),
  );
  await expect(page.getByRole("alert")).toContainText("up to 16");
  await page.getByLabel("Evidence files").setInputFiles({
    name: "retry.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Safe retry bytes\n"),
  });
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(`**/api/cases/${c.id}/evidence`, async (route) => {
    await gate;
    await route.fulfill({
      status: 503,
      json: { detail: "Temporary ingestion failure; retry" },
    });
  });
  await page.getByRole("button", { name: "Add 1 file", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Ingesting evidence…" }),
  ).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeVisible();
  release();
  await expect(page.getByRole("alert")).toContainText(
    "Temporary ingestion failure",
  );
  await page.unroute(`**/api/cases/${c.id}/evidence`);
  await page.getByRole("button", { name: "Add 1 file", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveAccessibleName(
    "Configure analysis",
  );
  expect(
    (await (await request.get(`/api/cases/${c.id}`)).json()).artifacts,
  ).toHaveLength(1);
});

test("Deep profile, configurable entropy and rerun history", async ({
  page,
  request,
}) => {
  const name = `Deep settings ${Date.now()}`;
  const c = await (
    await request.post("/api/cases", { headers, data: { name } })
  ).json();
  await request.post(`/api/cases/${c.id}/evidence`, {
    headers,
    multipart: {
      file: {
        name: "settings.txt",
        mimeType: "text/plain",
        buffer: Buffer.from("Safe  text control\n"),
      },
    },
  });
  await page.goto("/");
  await page.getByRole("button").filter({ hasText: name }).click();
  await page.getByRole("button", { name: "Run analysis", exact: true }).click();
  await page.getByRole("radio", { name: /^Deep/ }).check();
  await page.getByLabel("Entropy window / stride").selectOption("1024");
  await accessibility(page);
  await page
    .getByRole("button", { name: "Start analysis", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/cases/${c.id}`)).json()).jobs[0]
          ?.status,
      { timeout: 120_000 },
    )
    .toBe("completed");
  await expect(
    page.getByRole("button", { name: "Run analysis", exact: true }),
  ).toBeEnabled({ timeout: 120_000 });
  const result = await (await request.get(`/api/cases/${c.id}`)).json();
  expect(result.jobs[0].profile).toBe("deep");
  expect(
    result.runs.find((r: { analyzer: string }) => r.analyzer === "bytes").result
      .window,
  ).toBe(1024);
  await page.getByRole("button", { name: "Run analysis", exact: true }).click();
  await page.getByRole("radio", { name: /^Quick/ }).check();
  await page
    .getByRole("button", { name: "Start analysis", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/cases/${c.id}`)).json()).jobs.filter(
          (job: { status: string }) => job.status === "completed",
        ).length,
      { timeout: 120_000 },
    )
    .toBe(2);
  await expect(
    page.getByRole("button", { name: "Run analysis", exact: true }),
  ).toBeEnabled({ timeout: 120_000 });
  await page.getByRole("tab", { name: "Run history", exact: true }).click();
  await expect(page.locator(".run-group")).toHaveCount(2);
  await page.locator(".run-row summary").first().click();
  await expect(page.locator(".run-row[open] pre")).toContainText(
    "entropy_window",
  );
});

for (const width of [320, 768, 1536]) {
  test(`all primary screens remain accessible at ${width}px in both themes`, async ({
    page,
  }) => {
    test.setTimeout(240_000);
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    for (const theme of ["dark", "light"]) {
      await demo(page);
      if (theme === "light")
        await page
          .getByRole("button", { name: "Switch to light theme" })
          .click();
      for (const tab of [
        "Preview",
        "Measurements",
        "Provenance",
        "Run history",
        "Assistant",
        "Notes",
      ]) {
        await page.getByRole("tab", { name: tab, exact: true }).click();
        await accessibility(page);
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
          ),
        ).toBe(false);
      }
      await page.getByRole("button", { name: "Reports", exact: true }).click();
      await accessibility(page);
      await page.screenshot({
        path: test.info().outputPath(`reports-${width}-${theme}.png`),
        fullPage: true,
      });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
      ).toBe(false);
      await page
        .getByRole("button", { name: "Settings and tool health" })
        .click();
      await accessibility(page);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
      ).toBe(false);
      await page
        .getByRole("button", { name: "Cases", exact: true })
        .first()
        .click();
      await accessibility(page);
      await page.getByRole("button", { name: "New case", exact: true }).click();
      await accessibility(page);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
      ).toBe(false);
      await page.keyboard.press("Escape");
    }
  });
}

test("hosted UI requires payload review and explicit consent; errors stay actionable", async ({
  page,
}) => {
  let sends = 0;
  await page.route("**/api/health", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.providers.hosted = { available: true, label: "TEST STUB" };
    await route.fulfill({ response, json: body });
  });
  await page.route("**/assistant/preview", (route) =>
    route.fulfill({
      json: {
        digest: "test-consent",
        payload: { question: "Explain selected evidence", evidence: [] },
        bytes: 100,
        destination: { host: "stub.invalid" },
      },
    }),
  );
  await page.route(/\/assistant$/, async (route) => {
    sends++;
    expect(route.request().postDataJSON().consent_digest).toBe("test-consent");
    await route.fulfill({
      status: 502,
      json: { detail: "Provider quota/rate limit reached" },
    });
  });
  await demo(page);
  await page.getByRole("tab", { name: "Assistant", exact: true }).click();
  await page.getByLabel("Assistant provider").selectOption("hosted");
  await page
    .getByLabel("Ask about selected evidence")
    .fill("Explain selected evidence");
  await page.getByRole("button", { name: "Preview hosted request" }).click();
  await expect(page.getByRole("dialog")).toHaveAccessibleName(
    "Review hosted transmission",
  );
  await expect(page.getByRole("dialog")).toContainText("stub.invalid");
  expect(sends).toBe(0);
  await page.getByRole("button", { name: "Keep local" }).click();
  expect(sends).toBe(0);
  await page.getByRole("button", { name: "Preview hosted request" }).click();
  await page
    .getByRole("button", { name: "Approve & send this payload" })
    .click();
  await expect(page.getByRole("alert")).toContainText("quota/rate limit");
  expect(sends).toBe(1);
});

test("JSON download preserves real evidence and review decisions", async ({
  page,
}) => {
  await demo(page);
  await page
    .getByRole("button", {
      name: "Verified demonstration payload recovered",
      exact: true,
    })
    .first()
    .click();
  await page.getByLabel("Analyst review").selectOption("false_positive");
  await page
    .getByLabel("Review note")
    .fill(
      "Test review classification only; the fixture is intentionally embedded.",
    );
  await page.getByRole("button", { name: "Save review", exact: true }).click();
  await expect(page.getByText("Finding review saved.")).toBeVisible();
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  const pending = page.waitForEvent("download");
  await page
    .getByRole("link", {
      name: "Structured JSON Full evidence & provenance records",
    })
    .click();
  const download = await pending;
  const report = JSON.parse(
    await fs.readFile((await download.path())!, "utf8"),
  );
  expect(
    report.artifacts.some((a: { sha256: string }) =>
      /^[a-f0-9]{64}$/.test(a.sha256),
    ),
  ).toBe(true);
  expect(
    report.findings.some(
      (f: { review: { status: string; note: string } }) =>
        f.review.status === "false_positive" &&
        f.review.note.startsWith("Test review classification"),
    ),
  ).toBe(true);
  expect(report.runs.length).toBeGreaterThan(0);
});
