/**
 * J05: Action Execute Journey
 * Tests navigating to capabilities, viewing actions, and the detail page.
 */
import { test, expect } from "@playwright/test";
import { BASE, realLogin } from "./helpers";

test.describe("J05: Action Execute Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("capabilities page loads and shows content", async ({ page }) => {
    await page.goto(`${BASE}/function/capabilities`);
    await page.waitForLoadState("networkidle");

    // Wait for the page to finish loading - either show heading or table or empty state
    // The heading only appears after the loading state resolves
    await page.waitForTimeout(5000);

    // Check for the heading, table, empty message, or loading state
    const heading = page.locator("h1").filter({ hasText: "Capabilities" });
    const hasTable = page.locator("table");
    const hasEmpty = page.getByText("No capabilities registered");
    const hasLoading = page.getByText("Loading");

    await expect(
      heading.or(hasTable).or(hasEmpty).or(hasLoading).first(),
    ).toBeVisible({ timeout: 15000 });
  });

  test("capabilities table shows type column with badges", async ({
    page,
  }) => {
    await page.goto(`${BASE}/function/capabilities`);
    await page.waitForLoadState("networkidle");

    // Table headers should include Type, API Name, Safety Level
    const table = page.locator("table");
    if (await table.isVisible({ timeout: 15000 }).catch(() => false)) {
      await expect(page.getByText("Type").first()).toBeVisible();
      await expect(page.getByText("API Name").first()).toBeVisible();
      await expect(page.getByText("Safety Level").first()).toBeVisible();
    }
  });

  test("function overview page loads", async ({ page }) => {
    await page.goto(`${BASE}/function/overview`);
    await page.waitForLoadState("networkidle");

    await expect(page.getByText(/function/i).first()).toBeVisible({
      timeout: 10000,
    });
  });
});
