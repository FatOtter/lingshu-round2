/**
 * Shared E2E test helpers: auth setup, API mocking, common selectors.
 */
import type { Page } from "@playwright/test";

/** Inject an authenticated user into localStorage before page load. */
export async function setupAuth(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem(
      "auth-storage",
      JSON.stringify({
        state: {
          user: {
            rid: "ri.user.admin1",
            email: "admin@lingshu.dev",
            display_name: "Admin User",
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

/** Mock /auth/me to return the admin user. */
export async function mockAuthMe(page: Page) {
  await page.route("**/setting/v1/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: {
          rid: "ri.user.admin1",
          email: "admin@lingshu.dev",
          display_name: "Admin User",
          role: "admin",
          is_active: true,
        },
      }),
    });
  });
}

/**
 * Mock all /api/v1 endpoints with sensible defaults.
 * Override specific routes BEFORE calling this function.
 */
export async function mockAllApis(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();

    if (url.includes("/auth/me")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: {
            rid: "ri.user.admin1",
            email: "admin@lingshu.dev",
            display_name: "Admin User",
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

/** ISO timestamp helper */
export function now() {
  return new Date().toISOString();
}
