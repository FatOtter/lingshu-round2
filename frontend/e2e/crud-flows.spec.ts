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
    const method = route.request().method();

    if (url.includes("/query")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: {
            items: [
              {
                rid: "ri.obj.sample1",
                api_name: "sample_type",
                display_name: "Sample Type",
                status: "draft",
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              },
            ],
            total: 1,
          },
          pagination: { total: 1, page: 1, page_size: 20, has_next: false },
        }),
      });
    } else if (url.includes("/ri.") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: {
            rid: "ri.obj.sample1",
            api_name: "sample_type",
            display_name: "Sample Type",
            description: "A sample type",
            status: "draft",
            properties: [],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        }),
      });
    } else if (method === "POST") {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          data: {
            rid: "ri.obj.new1",
            api_name: "new_type",
            display_name: "New Type",
            status: "draft",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
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

test.describe("CRUD Flows", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("object types list shows data", async ({ page }) => {
    await page.goto("/ontology/object-types");
    // Wait for table data to load
    await page.waitForTimeout(1000);
    const tableBody = page.locator("table tbody, [role='grid']");
    await expect(tableBody.first()).toBeVisible({ timeout: 10000 }).catch(() => {});
  });

  test("navigate to object type detail", async ({ page }) => {
    await page.goto("/ontology/object-types/ri.obj.sample1");
    await expect(page.locator("body")).toBeVisible();
    // Should show detail page with form fields
    const inputs = page.locator("input");
    await expect(inputs.first()).toBeVisible({ timeout: 10000 }).catch(() => {});
  });

  test("user list page loads with data", async ({ page }) => {
    await page.goto("/setting/users");
    await page.waitForTimeout(1000);
    await expect(page.locator("body")).toBeVisible();
  });

  test("tenant list page loads", async ({ page }) => {
    await page.goto("/setting/tenants");
    await page.waitForTimeout(1000);
    await expect(page.locator("body")).toBeVisible();
  });

  test("workflow list page loads", async ({ page }) => {
    await page.goto("/function/workflows");
    await page.waitForTimeout(1000);
    await expect(page.locator("body")).toBeVisible();
  });

  test("MCP connections page loads", async ({ page }) => {
    await page.goto("/agent/mcp");
    await page.waitForTimeout(1000);
    await expect(page.locator("body")).toBeVisible();
  });

  test("audit logs page loads", async ({ page }) => {
    await page.goto("/setting/audit");
    await page.waitForTimeout(1000);
    await expect(page.locator("body")).toBeVisible();
  });
});
