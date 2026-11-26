// ABOUTME: Browser tests for the settings page, run by Playwright against the static server.
// ABOUTME: Each test starts from a fresh browser context, so localStorage starts empty.
const { test, expect } = require("@playwright/test");

test("saved settings survive a reload", async ({ page }) => {
  await page.goto("/settings.html");
  await page.selectOption("select[name=theme]", "dark");
  await page.fill("input[name=fontSize]", "20");
  await page.click("button[type=submit]");
  await expect(page.locator("#status")).toHaveText("Saved");
  await page.reload();
  await expect(page.locator("select[name=theme]")).toHaveValue("dark");
  await expect(page.locator("input[name=fontSize]")).toHaveValue("20");
});
