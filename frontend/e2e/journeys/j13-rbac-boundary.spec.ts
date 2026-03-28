/**
 * J13: RBAC Boundary Journey
 * Tests that an admin user can access all pages successfully.
 * Note: Full RBAC boundary testing (e.g., viewer role seeing 403) requires
 * creating users with different roles, which depends on backend RBAC enforcement.
 */
import { test, expect } from "@playwright/test";
import { BASE, API, realLogin } from "./helpers";

test.describe("J13: RBAC Boundary Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("admin can access all module overviews", async ({ page }) => {
    const modules = [
      { path: "/ontology/overview", text: /ontology/i },
      { path: "/data/overview", text: /data/i },
      { path: "/function/overview", text: /function/i },
      { path: "/agent/overview", text: /agent/i },
      { path: "/setting/overview", text: /setting/i },
    ];

    for (const mod of modules) {
      await page.goto(`${BASE}${mod.path}`);
      await page.waitForLoadState("networkidle");
      await expect(page.getByText(mod.text).first()).toBeVisible({
        timeout: 10000,
      });
    }
  });

  test("admin can access user management", async ({ page }) => {
    await page.goto(`${BASE}/setting/users`);
    await page.waitForLoadState("networkidle");

    // Admin should see the users table with their own account
    await expect(page.getByText("admin@lingshu.dev")).toBeVisible({
      timeout: 10000,
    });
  });

  test("admin can access tenant management", async ({ page }) => {
    await page.goto(`${BASE}/setting/tenants`);
    await page.waitForLoadState("networkidle");

    // Admin should see the default tenant
    await expect(page.getByText(/Default/).first()).toBeVisible({
      timeout: 10000,
    });
  });

  test("/auth/me returns admin user info", async ({ page }) => {
    const resp = await page.request.get(`${API}/setting/v1/auth/me`);
    expect(resp.ok()).toBeTruthy();

    const body = await resp.json();
    expect(body.data.email).toBe("admin@lingshu.dev");
    expect(body.data.role).toBe("admin");
  });

  test("unauthenticated request to protected endpoint returns 401", async ({
    page,
  }) => {
    // Make a request without cookies
    const resp = await page.request.get(`${API}/setting/v1/auth/me`, {
      headers: { Cookie: "" },
    });

    // Should be 401 or 403
    expect(resp.status()).toBeGreaterThanOrEqual(400);
    expect(resp.status()).toBeLessThan(500);
  });
});
