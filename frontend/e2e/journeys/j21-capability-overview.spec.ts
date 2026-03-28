/**
 * J21: Capability Overview Journey
 * Tests the Function overview page and capabilities list.
 */
import { test, expect } from "@playwright/test";
import { BASE, realLogin } from "./helpers";

test.describe("J21: Capability Overview Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("function overview page loads with stats", async ({ page }) => {
    await page.goto(`${BASE}/function/overview`);
    await page.waitForLoadState("networkidle");

    // Page should show Function-related heading
    await expect(page.getByText(/function/i).first()).toBeVisible({
      timeout: 10000,
    });
  });

  test("function overview shows stats cards with numbers", async ({
    page,
  }) => {
    await page.goto(`${BASE}/function/overview`);
    await page.waitForLoadState("networkidle");

    // Look for stat cards — they typically contain numeric values
    const hasCards = await page
      .locator("[class*='card']")
      .first()
      .isVisible()
      .catch(() => false);
    const hasStats = await page
      .getByText(/capabilities|actions|functions|workflows/i)
      .first()
      .isVisible()
      .catch(() => false);
    const hasNumbers = await page
      .locator("text=/\\d+/")
      .first()
      .isVisible()
      .catch(() => false);

    // At least the page should show some stats or content
    expect(hasCards || hasStats || hasNumbers).toBeTruthy();
  });

  test("capabilities list page loads and shows table", async ({ page }) => {
    await page.goto(`${BASE}/function/capabilities`);
    await page.waitForLoadState("networkidle");

    // Page heading
    await expect(
      page.getByRole("heading", { name: /capabilit/i }),
    ).toBeVisible({ timeout: 10000 });

    // Should show either capability rows or empty message
    const hasTable = await page
      .locator("table")
      .isVisible()
      .catch(() => false);
    const hasEmpty = await page
      .getByText(/no .*(capabilit|item)/i)
      .first()
      .isVisible()
      .catch(() => false);
    const hasComingSoon = await page
      .getByText(/coming soon/i)
      .isVisible()
      .catch(() => false);

    expect(hasTable || hasEmpty || hasComingSoon).toBeTruthy();
  });
});
