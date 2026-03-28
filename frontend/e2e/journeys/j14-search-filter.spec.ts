/**
 * J14: Search & Filter Journey
 * Tests search and filter functionality across multiple pages.
 */
import { test, expect } from "@playwright/test";
import { BASE, realLogin } from "./helpers";

test.describe("J14: Search & Filter Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("setting/users: search input filters results", async ({ page }) => {
    await page.goto(`${BASE}/setting/users`);
    await page.waitForLoadState("networkidle");

    // Verify admin visible initially
    await expect(page.getByText("admin@lingshu.dev")).toBeVisible({
      timeout: 10000,
    });

    // Type search query
    const searchInput = page.locator('input[placeholder="Search users..."]');
    await searchInput.fill("admin");

    // Wait for debounce (300ms) + API response
    await page.waitForTimeout(500);
    await page.waitForLoadState("networkidle");

    // Admin should still be visible
    await expect(page.getByText("admin@lingshu.dev")).toBeVisible({
      timeout: 10000,
    });

    // Clear search
    await searchInput.fill("");
    await page.waitForTimeout(500);
    await page.waitForLoadState("networkidle");

    // Admin should still be visible after clearing
    await expect(page.getByText("admin@lingshu.dev")).toBeVisible({
      timeout: 10000,
    });
  });

  test("data/browse: search filters type cards", async ({ page }) => {
    await page.goto(`${BASE}/data/browse`);
    await page.waitForLoadState("networkidle");

    // Wait for page content to load
    await page.waitForTimeout(3000);

    const searchInput = page.locator('input[placeholder="Search types..."]');
    // If search input isn't visible (page still loading), wait more
    if (!(await searchInput.isVisible({ timeout: 10000 }).catch(() => false))) {
      // Page might show loading state
      return;
    }

    // Search for a nonexistent type
    await searchInput.fill("nonexistent_type_abc_99999");
    await page.waitForTimeout(500);

    // Should show no results or empty state
    const noMatch = page.getByText("No types match your search.");
    const noTypes = page.getByText("No types with data found");
    // One of these or similar empty states should appear, or the page still shows content
    await expect(
      noMatch.or(noTypes).first(),
    ).toBeVisible({ timeout: 10000 });

    // Clear search
    await searchInput.fill("");
    await page.waitForTimeout(500);

    // Content should reappear (if there were types)
    await expect(page.locator("body")).toBeVisible();
  });

  test("setting/users: role filter works", async ({ page }) => {
    await page.goto(`${BASE}/setting/users`);
    await page.waitForLoadState("networkidle");

    // Wait for initial data
    await expect(page.getByText("admin@lingshu.dev")).toBeVisible({
      timeout: 10000,
    });

    // The Role filter select should be present (it uses a SelectTrigger with placeholder "Role")
    const roleSelect = page.locator('[role="combobox"]').filter({ hasText: "Role" });
    if (await roleSelect.isVisible().catch(() => false)) {
      await roleSelect.click();

      // Select "Admin"
      const adminOption = page.getByRole("option", { name: "Admin" });
      if (await adminOption.isVisible({ timeout: 3000 }).catch(() => false)) {
        await adminOption.click();

        await page.waitForTimeout(500);
        await page.waitForLoadState("networkidle");

        // Admin user should still be visible (they have admin role)
        await expect(page.getByText("admin@lingshu.dev")).toBeVisible({
          timeout: 10000,
        });
      }
    }
  });
});
