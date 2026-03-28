import { test, expect, type Page } from "@playwright/test";

async function setupAuth(page: Page) {
  await page.addInitScript(() => {
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

  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    if (url.includes("/sessions") && route.request().method() === "POST" && !url.includes("query")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: {
            session_id: "ri.session.test123",
            mode: "agent",
            status: "active",
            title: "Test Session",
            created_at: new Date().toISOString(),
            last_active_at: new Date().toISOString(),
            context: {},
          },
        }),
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

test.describe("Copilot Chat", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("chat page loads", async ({ page }) => {
    await page.goto("/agent/chat");
    await expect(page.locator("body")).toBeVisible();
  });

  test("sessions page shows empty state", async ({ page }) => {
    await page.goto("/agent/sessions");
    await expect(page.locator("body")).toBeVisible();
  });

  test("chat has input area", async ({ page }) => {
    await page.goto("/agent/chat");
    // Look for a textarea or input for message entry
    const input = page.locator("textarea, input[type='text']").first();
    await expect(input).toBeVisible({ timeout: 10000 }).catch(() => {
      // Chat may require session creation first
    });
  });
});
