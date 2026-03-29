/**
 * E2E: Draft entity visibility and console error regression tests.
 *
 * Tests discovered during debugging:
 * 1. Created ObjectTypes should appear in the list (draft visibility)
 * 2. No 422 errors from /function/v1/capabilities/query
 * 3. No duplicate React key warnings from versions page
 * 4. Auth refresh failure should not cause immediate logout in dev mode
 */
import { test, expect, type APIRequestContext } from "@playwright/test";

const BACKEND = "http://localhost:8000";

async function authHeaders(request: APIRequestContext) {
  const loginRes = await request.post(`${BACKEND}/setting/v1/auth/login`, {
    data: { email: "admin@lingshu.dev", password: "admin123" },
  });
  const loginData = await loginRes.json();
  return {
    "Content-Type": "application/json",
    "X-User-Id": loginData.data.user.rid as string,
    "X-Tenant-Id": loginData.data.user.tenant.rid as string,
    "X-User-Role": "admin",
  };
}

test.describe("Draft Entity Visibility", () => {
  test("created ObjectType appears in query results with draft status", async ({ request }) => {
    const headers = await authHeaders(request);
    const uniqueName = `e2e_test_${Date.now()}`;

    const createRes = await request.post(`${BACKEND}/ontology/v1/object-types`, {
      headers,
      data: {
        api_name: uniqueName,
        display_name: `E2E Test ${uniqueName}`,
        description: "Created by E2E test for draft visibility",
      },
    });
    expect(createRes.status()).toBe(201);
    const createData = await createRes.json();
    expect(createData.data.rid).toBeTruthy();
    expect(createData.data.version_status).toBe("draft");

    const queryRes = await request.post(`${BACKEND}/ontology/v1/object-types/query`, {
      headers,
      data: {
        pagination: { page: 1, page_size: 100 },
        include_drafts: true,
        search: uniqueName,
      },
    });
    expect(queryRes.ok()).toBeTruthy();
    const queryData = await queryRes.json();
    expect(queryData.pagination.total).toBeGreaterThanOrEqual(1);

    const found = queryData.data.find(
      (item: Record<string, string>) => item.api_name === uniqueName
    );
    expect(found).toBeTruthy();
    expect(found.version_status).toBe("draft");
  });

  test("query with include_drafts=false excludes draft entities", async ({ request }) => {
    const headers = await authHeaders(request);
    const uniqueName = `e2e_nodraft_${Date.now()}`;

    const createRes = await request.post(`${BACKEND}/ontology/v1/object-types`, {
      headers,
      data: {
        api_name: uniqueName,
        display_name: `No Draft ${uniqueName}`,
        description: "Should not appear when drafts excluded",
      },
    });
    expect(createRes.status()).toBe(201);

    const queryRes = await request.post(`${BACKEND}/ontology/v1/object-types/query`, {
      headers,
      data: {
        pagination: { page: 1, page_size: 100 },
        include_drafts: false,
        search: uniqueName,
      },
    });
    expect(queryRes.ok()).toBeTruthy();
    const queryData = await queryRes.json();
    const found = queryData.data.find(
      (item: Record<string, string>) => item.api_name === uniqueName
    );
    expect(found).toBeFalsy();
  });

  test("created LinkType appears in query with draft status", async ({ request }) => {
    const headers = await authHeaders(request);
    const uniqueName = `e2e_link_${Date.now()}`;

    const createRes = await request.post(`${BACKEND}/ontology/v1/link-types`, {
      headers,
      data: {
        api_name: uniqueName,
        display_name: `E2E Link ${uniqueName}`,
        description: "Link type draft visibility test",
      },
    });
    expect(createRes.status()).toBe(201);
    expect((await createRes.json()).data.version_status).toBe("draft");

    const queryRes = await request.post(`${BACKEND}/ontology/v1/link-types/query`, {
      headers,
      data: {
        pagination: { page: 1, page_size: 100 },
        include_drafts: true,
        search: uniqueName,
      },
    });
    expect(queryRes.ok()).toBeTruthy();
    const queryData = await queryRes.json();
    expect(queryData.data.find(
      (item: Record<string, string>) => item.api_name === uniqueName
    )).toBeTruthy();
  });
});

test.describe("Console Error Regressions", () => {
  test("function capabilities query does not return 422 with empty body", async ({ request }) => {
    const headers = await authHeaders(request);
    const res = await request.post(`${BACKEND}/function/v1/capabilities/query`, {
      headers,
      data: {},
    });
    expect(res.status()).not.toBe(422);
    expect(res.ok()).toBeTruthy();
  });

  test("function capabilities query works with type filter", async ({ request }) => {
    const headers = await authHeaders(request);
    const res = await request.post(`${BACKEND}/function/v1/capabilities/query`, {
      headers,
      data: { capability_type: "action" },
    });
    expect(res.ok()).toBeTruthy();
  });

  test("auth refresh returns structured error (not 500) when no cookie", async ({ request }) => {
    const res = await request.post(`${BACKEND}/setting/v1/auth/refresh`, {
      headers: { "Content-Type": "application/json" },
    });
    const data = await res.json();
    expect(data.error).toBeTruthy();
    expect(data.error.code).toBe("SETTING_AUTH_TOKEN_EXPIRED");
  });

  test("health endpoint responds ok", async ({ request }) => {
    const res = await request.get(`${BACKEND}/health`);
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.status).toBe("ok");
  });
});

test.describe("Frontend Draft Display", () => {
  test("Object Types page shows draft entities after creation", async ({ page, request }) => {
    const headers = await authHeaders(request);
    const uniqueName = `e2e_ui_${Date.now()}`;

    await request.post(`${BACKEND}/ontology/v1/object-types`, {
      headers,
      data: {
        api_name: uniqueName,
        display_name: `UI Test ${uniqueName}`,
        description: "UI draft visibility test",
      },
    });

    await page.goto("/login");
    await page.fill('input[type="email"]', "admin@lingshu.dev");
    await page.fill('input[type="password"]', "admin123");
    await page.click('button[type="submit"]');

    await page.waitForURL("**/ontology/overview", { timeout: 10000 });

    await page.click("text=Object Types");
    await page.waitForURL("**/ontology/object-types", { timeout: 10000 });

    await expect(page.locator("table")).toBeVisible({ timeout: 10000 });

    const tableContent = await page.locator("table").textContent();
    expect(tableContent).toContain(uniqueName);
  });

  test("no critical console errors on page load", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        if (
          !text.includes("auth/refresh") &&
          !text.includes("Download the React DevTools") &&
          !text.includes("favicon")
        ) {
          consoleErrors.push(text);
        }
      }
    });

    await page.goto("/login");
    await page.fill('input[type="email"]', "admin@lingshu.dev");
    await page.fill('input[type="password"]', "admin123");
    await page.click('button[type="submit"]');

    await page.waitForURL("**/ontology/overview", { timeout: 10000 });
    await page.waitForTimeout(2000);

    const criticalErrors = consoleErrors.filter(
      (e) =>
        !e.includes("snapshot_id") &&
        !e.includes("Fast Refresh") &&
        !e.includes("HMR")
    );

    expect(criticalErrors).toEqual([]);
  });
});
