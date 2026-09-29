import { test, expect } from "@playwright/test";

const headers = { "X-Steganalysis": "local" };

test("stale notes and report editors preserve changes from another client", async ({
  page,
  request,
}) => {
  const name = `QC independent edits ${Date.now()}`;
  const response = await request.post("/api/cases", {
    headers,
    data: { name },
  });
  expect(response.status()).toBe(201);
  const caseId = (await response.json()).id;
  const endpoint = `/api/cases/${caseId}`;
  await page.goto("/");
  await page.getByRole("button").filter({ hasText: name }).click();
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page.getByLabel("Case notes").fill("Notes from this browser");

  expect(
    (
      await request.patch(endpoint, {
        headers,
        data: {
          report_draft: "New report from another client",
          report_author: "model",
        },
      })
    ).ok(),
  ).toBe(true);
  await page.getByRole("button", { name: "Save notes", exact: true }).click();
  await expect(page.getByText("Case notes saved.")).toBeVisible();
  let saved = (await (await request.get(endpoint)).json()).case;
  expect(saved.notes).toBe("Notes from this browser");
  expect(saved.report_draft).toBe("New report from another client");
  expect(saved.report_author).toBe("model");

  await page.getByRole("button", { name: "Reports", exact: true }).click();
  await page
    .getByLabel("Report narrative")
    .fill("Edited report from this browser");
  expect(
    (
      await request.patch(endpoint, {
        headers,
        data: { notes: "New notes from another client" },
      })
    ).ok(),
  ).toBe(true);
  await page.route(`**${endpoint}`, async (route) => {
    if (route.request().method() === "PATCH") {
      await route.fulfill({
        status: 503,
        json: { detail: "Temporary save failure; retry" },
      });
    } else {
      await route.continue();
    }
  });
  await page
    .getByRole("button", { name: "Save narrative", exact: true })
    .click();
  await expect(
    page.getByText("Temporary save failure; retry", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Report narrative")).toHaveValue(
    "Edited report from this browser",
  );
  saved = (await (await request.get(endpoint)).json()).case;
  expect(saved.report_draft).toBe("New report from another client");
  await page.unroute(`**${endpoint}`);
  await page
    .getByRole("button", { name: "Save narrative", exact: true })
    .click();
  await expect(page.getByText("Investigation narrative saved.")).toBeVisible();
  saved = (await (await request.get(endpoint)).json()).case;
  expect(saved.notes).toBe("New notes from another client");
  expect(saved.report_draft).toBe("Edited report from this browser");

  const report = await (await request.get(`${endpoint}/report.json`)).json();
  expect(report.case).toEqual(saved);
});

test("assistant report drafting preserves newer notes from another client", async ({
  page,
  request,
}) => {
  const name = `QC assistant edits ${Date.now()}`;
  const response = await request.post("/api/cases", {
    headers,
    data: { name },
  });
  expect(response.status()).toBe(201);
  const endpoint = `/api/cases/${(await response.json()).id}`;
  await page.goto("/");
  await page.getByRole("button").filter({ hasText: name }).click();
  await page.getByRole("tab", { name: "Assistant", exact: true }).click();
  await page
    .getByLabel("Ask about selected evidence")
    .fill("What should I examine next?");
  await page
    .getByRole("button", { name: "Ask evidence guide", exact: true })
    .click();
  await expect(
    page.getByText("DETERMINISTIC GUIDE", { exact: true }),
  ).toBeVisible();
  expect(
    (
      await request.patch(endpoint, {
        headers,
        data: { notes: "Keep the later observation" },
      })
    ).ok(),
  ).toBe(true);
  await page
    .getByRole("button", { name: "Use as report draft", exact: true })
    .click();
  await expect(page.getByLabel("Report narrative")).toHaveValue(/FACTS/);
  const saved = (await (await request.get(endpoint)).json()).case;
  expect(saved.notes).toBe("Keep the later observation");
  expect(saved.report_author).toBe("deterministic");
});
