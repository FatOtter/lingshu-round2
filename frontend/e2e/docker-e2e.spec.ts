/**
 * Real E2E tests against Docker deployment (localhost:3100 / localhost:8100).
 * No mocks — tests real login, real API calls, real page rendering.
 */
import { test, expect, type Page } from "@playwright/test";

const BASE = "http://localhost:3100";
const API = "http://localhost:8100";

/** Login via API, inject cookies into browser context */
async function realLogin(page: Page) {
  // Login via API to get cookies
  const resp = await page.request.post(`${API}/setting/v1/auth/login`, {
    data: { email: "admin@lingshu.dev", password: "admin123" },
  });
  expect(resp.ok()).toBeTruthy();

  // Extract Set-Cookie headers and inject them
  const headers = resp.headersArray();
  const cookies: Array<{
    name: string;
    value: string;
    domain: string;
    path: string;
    httpOnly: boolean;
    sameSite: "Lax" | "Strict" | "None";
  }> = [];
  for (const h of headers) {
    if (h.name.toLowerCase() === "set-cookie") {
      const parts = h.value.split(";");
      const [nameVal] = parts;
      const [name, ...rest] = nameVal.split("=");
      const value = rest.join("=");
      const pathMatch = h.value.match(/Path=([^;]+)/i);
      cookies.push({
        name: name.trim(),
        value: value.trim(),
        domain: "localhost",
        path: pathMatch ? pathMatch[1] : "/",
        httpOnly: true,
        sameSite: "Lax",
      });
    }
  }
  await page.context().addCookies(cookies);
}

test.describe("Login Flow", () => {
  test("login page renders", async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await expect(page.getByText("LingShu")).toBeVisible({ timeout: 10000 });
    await expect(page.locator('input[type="email"], input[name="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });

  test("real login with admin credentials", async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.locator('input[type="email"], input[name="email"]').fill("admin@lingshu.dev");
    await page.locator('input[type="password"]').fill("admin123");
    await page.locator('button[type="submit"]').click();
    // Should redirect away from login after success
    await page.waitForURL((url) => !url.pathname.includes("/login"), { timeout: 15000 });
    // Should land on an authenticated page
    const url = page.url();
    expect(url).not.toContain("/login");
  });
});

test.describe("Authenticated Pages", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  // ── Ontology Module ──
  test("ontology overview loads", async ({ page }) => {
    await page.goto(`${BASE}/ontology/overview`);
    await expect(page.locator("body")).toBeVisible();
    // Should show heading or module content
    await expect(page.getByText(/ontology/i).first()).toBeVisible({ timeout: 10000 });
  });

  test("ontology object-types page loads", async ({ page }) => {
    await page.goto(`${BASE}/ontology/object-types`);
    await expect(page.locator("body")).toBeVisible();
    await page.waitForLoadState("networkidle");
    // Page should render without 500/CORS errors
    const pageText = await page.locator("body").innerText();
    expect(pageText).not.toContain("500");
  });

  test("ontology link-types page loads", async ({ page }) => {
    await page.goto(`${BASE}/ontology/link-types`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  test("ontology interface-types page loads", async ({ page }) => {
    await page.goto(`${BASE}/ontology/interface-types`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  test("ontology action-types page loads", async ({ page }) => {
    await page.goto(`${BASE}/ontology/action-types`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  test("ontology shared-property-types page loads", async ({ page }) => {
    await page.goto(`${BASE}/ontology/shared-property-types`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  test("ontology versions page loads", async ({ page }) => {
    await page.goto(`${BASE}/ontology/versions`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  // ── Data Module ──
  test("data overview loads", async ({ page }) => {
    await page.goto(`${BASE}/data/overview`);
    await expect(page.locator("body")).toBeVisible();
    await expect(page.getByText(/data/i).first()).toBeVisible({ timeout: 10000 });
  });

  test("data sources page loads", async ({ page }) => {
    await page.goto(`${BASE}/data/sources`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  test("data browse page loads", async ({ page }) => {
    await page.goto(`${BASE}/data/browse`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  // ── Function Module ──
  test("function overview loads", async ({ page }) => {
    await page.goto(`${BASE}/function/overview`);
    await expect(page.locator("body")).toBeVisible();
    await expect(page.getByText(/function/i).first()).toBeVisible({ timeout: 10000 });
  });

  test("function capabilities page loads", async ({ page }) => {
    await page.goto(`${BASE}/function/capabilities`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  // ── Agent Module ──
  test("agent overview loads", async ({ page }) => {
    await page.goto(`${BASE}/agent/overview`);
    await expect(page.locator("body")).toBeVisible();
    await expect(page.getByText(/agent/i).first()).toBeVisible({ timeout: 10000 });
  });

  test("agent chat page loads", async ({ page }) => {
    await page.goto(`${BASE}/agent/chat`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  test("agent models page loads", async ({ page }) => {
    await page.goto(`${BASE}/agent/models`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  test("agent skills page loads", async ({ page }) => {
    await page.goto(`${BASE}/agent/skills`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  test("agent mcp page loads", async ({ page }) => {
    await page.goto(`${BASE}/agent/mcp`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  test("agent sessions page loads", async ({ page }) => {
    await page.goto(`${BASE}/agent/sessions`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  test("agent sub-agents page loads", async ({ page }) => {
    await page.goto(`${BASE}/agent/sub-agents`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  test("agent monitor page loads", async ({ page }) => {
    await page.goto(`${BASE}/agent/monitor`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  // ── Setting Module ──
  test("setting overview loads", async ({ page }) => {
    await page.goto(`${BASE}/setting/overview`);
    await expect(page.locator("body")).toBeVisible();
    await expect(page.getByText(/setting/i).first()).toBeVisible({ timeout: 10000 });
  });

  test("setting users page loads", async ({ page }) => {
    await page.goto(`${BASE}/setting/users`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
    // Page should render the users management UI
    await expect(page.getByText(/users/i).first()).toBeVisible({ timeout: 10000 });
  });

  test("setting tenants page loads", async ({ page }) => {
    await page.goto(`${BASE}/setting/tenants`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
    // Page should render the tenants management UI
    await expect(page.getByText(/tenants/i).first()).toBeVisible({ timeout: 10000 });
  });

  test("setting audit page loads", async ({ page }) => {
    await page.goto(`${BASE}/setting/audit`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  // ── Navigation ──
  test("dock navigation between modules", async ({ page }) => {
    await page.goto(`${BASE}/ontology/overview`);
    await page.waitForLoadState("networkidle");

    // Click Data module in dock
    const dataLink = page.locator('nav a[href="/data/overview"]');
    if (await dataLink.isVisible()) {
      await dataLink.click();
      await page.waitForURL("**/data/overview");
      expect(page.url()).toContain("/data/overview");
    }
  });

  // ── API Health ──
  test("backend API is healthy", async ({ page }) => {
    const resp = await page.request.get(`${API}/health`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.status).toBe("ok");
  });

  test("authenticated API calls work", async ({ page }) => {
    await realLogin(page);

    // Test /auth/me
    const meResp = await page.request.get(`${API}/setting/v1/auth/me`);
    expect(meResp.ok()).toBeTruthy();
    const me = await meResp.json();
    expect(me.data.email).toBe("admin@lingshu.dev");

    // Test ontology query
    const ontResp = await page.request.post(`${API}/ontology/v1/object-types/query`, {
      data: { page: 1, page_size: 20 },
    });
    expect(ontResp.ok()).toBeTruthy();

    // Test setting tenants query
    const tenResp = await page.request.post(`${API}/setting/v1/tenants/query`, {
      data: { page: 1, page_size: 20 },
    });
    expect(tenResp.ok()).toBeTruthy();
    const tenants = await tenResp.json();
    expect(tenants.data.length).toBeGreaterThan(0);
  });

  // ── Data Rendering Verification ──
  test("setting users table shows admin user", async ({ page }) => {
    await page.goto(`${BASE}/setting/users`);
    await page.waitForLoadState("networkidle");
    // The seeded admin user should appear in the table
    await expect(page.getByText("admin@lingshu.dev")).toBeVisible({ timeout: 10000 });
  });

  test("setting tenants table shows default tenant", async ({ page }) => {
    await page.goto(`${BASE}/setting/tenants`);
    await page.waitForLoadState("networkidle");
    // The seeded default tenant should appear
    await expect(page.getByText(/Default/)).toBeVisible({ timeout: 10000 });
  });

  test("setting overview shows user count", async ({ page }) => {
    await page.goto(`${BASE}/setting/overview`);
    await page.waitForLoadState("networkidle");
    // Total Users card should show at least 1
    const userCount = page.locator("text=Total Users").locator("..").locator("..").locator(".text-2xl");
    await expect(userCount).toBeVisible({ timeout: 10000 });
    const count = await userCount.innerText();
    expect(Number(count)).toBeGreaterThan(0);
  });

  // ── Console Error Check ──
  test("no console errors on ontology page", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    page.on("console", (msg) => {
      if (msg.type() === "error" && !msg.text().includes("favicon")) {
        errors.push(msg.text());
      }
    });

    await page.goto(`${BASE}/ontology/overview`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Filter out known non-critical errors
    const criticalErrors = errors.filter(
      (e) => !e.includes("ResizeObserver") && !e.includes("hydration")
    );
    expect(criticalErrors).toHaveLength(0);
  });
});
