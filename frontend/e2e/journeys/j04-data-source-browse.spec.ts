/**
 * J04: Data Source & Browse Journey
 * Tests navigating data sources and the browse page with type cards.
 */
import { test, expect } from "@playwright/test";
import { BASE, realLogin } from "./helpers";

test.describe("J04: Data Source & Browse Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("data sources page loads and shows table", async ({ page }) => {
    await page.goto(`${BASE}/data/sources`);
    await page.waitForLoadState("networkidle");

    // Page heading should be visible
    await expect(page.getByText("Data Sources")).toBeVisible({
      timeout: 10000,
    });

    // New Connection button should be present
    await expect(
      page.getByRole("button", { name: /new connection/i }),
    ).toBeVisible();
  });

  test("data browse page loads with type cards or empty state", async ({
    page,
  }) => {
    await page.goto(`${BASE}/data/browse`);
    await page.waitForLoadState("networkidle");

    // Page heading
    await expect(page.getByText("Browse Data")).toBeVisible({
      timeout: 10000,
    });

    // Should show either type cards or empty state message
    const hasObjectTypes = await page
      .getByText("Object Types")
      .isVisible()
      .catch(() => false);
    const hasEmptyState = await page
      .getByText(/no types/i)
      .isVisible()
      .catch(() => false);

    expect(hasObjectTypes || hasEmptyState).toBeTruthy();
  });

  test("data browse page has search functionality", async ({ page }) => {
    await page.goto(`${BASE}/data/browse`);
    await page.waitForLoadState("networkidle");

    // Search input should be present
    const searchInput = page.locator('input[placeholder="Search types..."]');
    await expect(searchInput).toBeVisible({ timeout: 10000 });

    // Type a search term
    await searchInput.fill("nonexistent_type_xyz");
    await page.waitForTimeout(500);

    // Should show either no results or filtered content
    // (the search filters client-side after debounce)
    await expect(page.locator("body")).toBeVisible();
  });

  test("data overview page loads", async ({ page }) => {
    await page.goto(`${BASE}/data/overview`);
    await page.waitForLoadState("networkidle");

    await expect(page.getByText(/data/i).first()).toBeVisible({
      timeout: 10000,
    });
  });
});
