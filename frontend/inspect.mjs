import { chromium } from "@playwright/test";
import fs from "node:fs";
fs.mkdirSync("../docs/screenshots", { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({
  viewport: { width: 1536, height: 1000 },
  deviceScaleFactor: 1,
});
page.on("pageerror", (error) => console.log("PAGE_ERROR", error.message));
await page.goto(process.env.STEG_SCREENSHOT_URL || "http://127.0.0.1:8000");
await page.getByRole("heading", { name: "Your investigations" }).waitFor();
await page
  .getByRole("button")
  .filter({ hasText: "The quiet signal" })
  .first()
  .waitFor();
await page.screenshot({
  path: "../docs/screenshots/cases-desktop.png",
  fullPage: true,
});
await page
  .getByRole("button")
  .filter({ hasText: "The quiet signal" })
  .first()
  .click();
await page.getByRole("region", { name: "Artifact viewer" }).waitFor();
await page.waitForTimeout(800);
await page.screenshot({
  path: "../docs/screenshots/investigation-desktop.png",
  fullPage: true,
});
await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({
  path: "../docs/screenshots/investigation-narrow.png",
  fullPage: true,
});
console.log(
  JSON.stringify({
    title: await page.title(),
    overflow: await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  }),
);
await page.setViewportSize({ width: 1536, height: 1000 });
await page.getByRole("button", { name: "Reports", exact: true }).click();
await page
  .getByRole("heading", { name: "Investigation report", exact: true })
  .waitFor();
await page.screenshot({
  path: "../docs/screenshots/reports-desktop.png",
  fullPage: true,
});
await page.setViewportSize({ width: 320, height: 1000 });
await page.screenshot({
  path: "../docs/screenshots/reports-narrow.png",
  fullPage: true,
});
console.log(
  JSON.stringify({
    reportPlaceholder: await page
      .getByLabel("Report narrative")
      .getAttribute("placeholder"),
  }),
);
await browser.close();
