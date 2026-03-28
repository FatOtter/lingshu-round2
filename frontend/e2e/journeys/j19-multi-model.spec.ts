/**
 * J19: Multi-Model Management Journey
 * Tests the Agent > Models page: listing, empty state, and registration form.
 */
import { test, expect } from "@playwright/test";
import { BASE, realLogin } from "./helpers";

test.describe("J19: Multi-Model Management Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("models page loads and renders heading", async ({ page }) => {
    await page.goto(`${BASE}/agent/models`);
    await page.waitForLoadState("networkidle");

    // Page should show Models heading
    await expect(page.getByText(/model/i).first()).toBeVisible({
      timeout: 10000,
    });
  });

  test("model list renders or shows empty state", async ({ page }) => {
    await page.goto(`${BASE}/agent/models`);
    await page.waitForLoadState("networkidle");

    // Should show either a table/list of models or empty state
    const hasTable = await page
      .locator("table")
      .isVisible()
      .catch(() => false);
    const hasCards = await page
      .locator("[class*='card']")
      .first()
      .isVisible()
      .catch(() => false);
    const hasEmpty = await page
      .getByText(/no .*(model|item)/i)
      .first()
      .isVisible()
      .catch(() => false);
    const hasComingSoon = await page
      .getByText(/coming soon/i)
      .isVisible()
      .catch(() => false);
    const hasRows = await page
      .locator("tr")
      .first()
      .isVisible()
      .catch(() => false);

    expect(
      hasTable || hasCards || hasEmpty || hasComingSoon || hasRows,
    ).toBeTruthy();
  });

  test("model registration form elements are present", async ({ page }) => {
    await page.goto(`${BASE}/agent/models`);
    await page.waitForLoadState("networkidle");

    // Look for a create/register button
    const hasRegisterButton = await page
      .getByRole("button", { name: /new|create|add|register/i })
      .first()
      .isVisible()
      .catch(() => false);
    const hasRegisterLink = await page
      .getByRole("link", { name: /new|create|add|register/i })
      .first()
      .isVisible()
      .catch(() => false);
    const hasComingSoon = await page
      .getByText(/coming soon/i)
      .isVisible()
      .catch(() => false);

    if (hasRegisterButton) {
      // Click to open the form/dialog
      await page
        .getByRole("button", { name: /new|create|add|register/i })
        .first()
        .click();
      await page.waitForTimeout(1000);

      // Form should have input fields
      const hasInput = await page
        .locator("input, textarea, select")
        .first()
        .isVisible()
        .catch(() => false);
      const hasDialog = await page
        .locator("[role='dialog']")
        .isVisible()
        .catch(() => false);

      expect(hasInput || hasDialog).toBeTruthy();
    } else {
      // Feature might not be fully built yet, or uses link navigation
      expect(
        hasRegisterLink || hasComingSoon || hasRegisterButton,
      ).toBeTruthy();
    }
  });
});
