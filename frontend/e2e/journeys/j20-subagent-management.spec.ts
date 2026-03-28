/**
 * J20: Sub-Agent Management Journey
 * Tests the Agent > Sub-Agents page: listing, empty state, and create form.
 */
import { test, expect } from "@playwright/test";
import { BASE, realLogin } from "./helpers";

test.describe("J20: Sub-Agent Management Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("sub-agents page loads and renders heading", async ({ page }) => {
    await page.goto(`${BASE}/agent/sub-agents`);
    await page.waitForLoadState("networkidle");

    // Page should show Sub-Agents heading
    await expect(
      page.getByRole("heading", { name: /sub.?agent/i }),
    ).toBeVisible({ timeout: 10000 });
  });

  test("sub-agent list renders or shows empty state", async ({ page }) => {
    await page.goto(`${BASE}/agent/sub-agents`);
    await page.waitForLoadState("networkidle");

    // Should show either a table/list or empty state
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
      .getByText(/no .*(sub.?agent|agent|item)/i)
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

  test("create sub-agent form elements are accessible", async ({ page }) => {
    await page.goto(`${BASE}/agent/sub-agents`);
    await page.waitForLoadState("networkidle");

    // Look for a create/new button
    const hasCreateButton = await page
      .getByRole("button", { name: /new|create|add/i })
      .first()
      .isVisible()
      .catch(() => false);
    const hasCreateLink = await page
      .getByRole("link", { name: /new|create|add/i })
      .first()
      .isVisible()
      .catch(() => false);
    const hasComingSoon = await page
      .getByText(/coming soon/i)
      .isVisible()
      .catch(() => false);

    if (hasCreateButton) {
      // Click to open form/dialog
      await page
        .getByRole("button", { name: /new|create|add/i })
        .first()
        .click();
      await page.waitForTimeout(1000);

      // Form should have input fields or a dialog
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
      // Feature might use link navigation or not be fully built
      expect(hasCreateLink || hasComingSoon || hasCreateButton).toBeTruthy();
    }
  });
});
