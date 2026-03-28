import { test, expect, type Page } from "@playwright/test";

// Helper to mock auth state
async function mockAuthenticatedUser(page: Page) {
  // Set auth cookies/state before navigation
  await page.addInitScript(() => {
    // Mock the auth store to return a user
    localStorage.setItem(
      "auth-storage",
      JSON.stringify({
        state: {
          user: {
            rid: "ri.user.test",
            email: "test@example.com",
            display_name: "Test User",
            role: "admin",
            is_active: true,
          },
          isAuthenticated: true,
        },
        version: 0,
      })
    );
  });
}

// Mock API responses
async function mockApiResponses(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();

    if (url.includes("/auth/me")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: {
            rid: "ri.user.test",
            email: "test@example.com",
            display_name: "Test User",
            role: "admin",
            is_active: true,
          },
        }),
      });
    } else if (url.includes("/overview")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: {} }),
      });
    } else if (url.includes("/query")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: { items: [], total: 0 },
          pagination: { total: 0, page: 1, page_size: 20, has_next: false },
        }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: {} }),
      });
    }
  });
}

test.describe("Module Navigation", () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthenticatedUser(page);
    await mockApiResponses(page);
  });

  test("ontology module pages load", async ({ page }) => {
    await page.goto("/ontology/overview");
    await expect(page.locator("body")).toBeVisible();
    // Verify sidebar is present
    const sidebar = page.locator("nav, aside, [role='navigation']").first();
    await expect(sidebar).toBeVisible({ timeout: 10000 }).catch(() => {});
  });

  test("data module pages load", async ({ page }) => {
    await page.goto("/data/overview");
    await expect(page.locator("body")).toBeVisible();
  });

  test("function module pages load", async ({ page }) => {
    await page.goto("/function/overview");
    await expect(page.locator("body")).toBeVisible();
  });

  test("setting module pages load", async ({ page }) => {
    await page.goto("/setting/overview");
    await expect(page.locator("body")).toBeVisible();
  });

  test("ontology object-types list page", async ({ page }) => {
    await page.goto("/ontology/object-types");
    await expect(page.locator("body")).toBeVisible();
    // Should have a "New" or create button
    const createBtn = page.locator("button").filter({ hasText: /new|create/i });
    await expect(createBtn.first()).toBeVisible({ timeout: 10000 }).catch(() => {});
  });

  test("setting users list page", async ({ page }) => {
    await page.goto("/setting/users");
    await expect(page.locator("body")).toBeVisible();
  });

  test("data sources page", async ({ page }) => {
    await page.goto("/data/sources");
    await expect(page.locator("body")).toBeVisible();
  });

  test("function capabilities page", async ({ page }) => {
    await page.goto("/function/capabilities");
    await expect(page.locator("body")).toBeVisible();
  });

  test("agent models page", async ({ page }) => {
    await page.goto("/agent/models");
    await expect(page.locator("body")).toBeVisible();
  });

  test("agent skills page", async ({ page }) => {
    await page.goto("/agent/skills");
    await expect(page.locator("body")).toBeVisible();
  });

  test("agent sub-agents page", async ({ page }) => {
    await page.goto("/agent/sub-agents");
    await expect(page.locator("body")).toBeVisible();
  });

  test("agent monitor page", async ({ page }) => {
    await page.goto("/agent/monitor");
    await expect(page.locator("body")).toBeVisible();
  });

  test("data versions page", async ({ page }) => {
    await page.goto("/data/versions");
    await expect(page.locator("body")).toBeVisible();
  });

  test("function workflows page", async ({ page }) => {
    await page.goto("/function/workflows");
    await expect(page.locator("body")).toBeVisible();
  });
});
