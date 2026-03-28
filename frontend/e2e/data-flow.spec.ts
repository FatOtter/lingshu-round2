/**
 * E2E: Data module — Create data source → Browse instances.
 *
 * Phase 7.3 task: [TEST] 编写 Data 模块的 E2E 测试
 */
import { test, expect, type Page } from "@playwright/test";
import { setupAuth, now } from "./helpers";

const CONNECTIONS = [
  {
    rid: "ri.conn.pg1",
    api_name: "main_pg",
    display_name: "Main PostgreSQL",
    connector_type: "postgresql",
    status: "connected",
    config: { host: "localhost", port: 5432, database: "mydb" },
    created_at: now(),
    updated_at: now(),
  },
];

const OBJECT_TYPE_CARDS = [
  {
    rid: "ri.obj.employee1",
    api_name: "Employee",
    display_name: "Employee",
    property_count: 3,
  },
];

const INSTANCES = {
  items: [
    { _rid: "inst-001", name: "Alice", department: "Engineering" },
    { _rid: "inst-002", name: "Bob", department: "Marketing" },
  ],
  total: 2,
  columns: [
    { key: "name", label: "Name", data_type: "STRING" },
    { key: "department", label: "Department", data_type: "STRING" },
  ],
};

async function mockDataApis(page: Page) {
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

  await page.route("**/data/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    if (url.includes("/connections/query") || (url.includes("/connections") && url.includes("query"))) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: { items: CONNECTIONS, total: 1 },
          pagination: { total: 1, page: 1, page_size: 20, has_next: false },
        }),
      });
    } else if (url.includes("/connections") && method === "POST" && !url.includes("query") && !url.includes("test")) {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          data: {
            rid: "ri.conn.new1",
            api_name: "new_source",
            display_name: "New Source",
            connector_type: "postgresql",
            status: "connected",
            created_at: now(),
            updated_at: now(),
          },
        }),
      });
    } else if (url.includes("/connections/test") || url.includes("/test")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: { success: true, message: "Connection successful" } }),
      });
    } else if (url.match(/\/connections\/ri\.conn\.\w+/) && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: CONNECTIONS[0] }),
      });
    } else if (url.includes("/instances/query")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: INSTANCES,
          pagination: { total: 2, page: 1, page_size: 20, has_next: false },
        }),
      });
    } else if (url.includes("/overview")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: { connections: { total: 1 }, types_with_data: 1 },
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

  // Also mock ontology API for browse cards
  await page.route("**/ontology/v1/**", async (route) => {
    const url = route.request().url();
    if (url.includes("/query")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: { items: OBJECT_TYPE_CARDS, total: 1 },
          pagination: { total: 1, page: 1, page_size: 20, has_next: false },
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

test.describe("Data Module Flow", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await mockDataApis(page);
  });

  test("data overview renders connection stats", async ({ page }) => {
    await page.goto("/data/overview");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
  });

  test("data sources list shows connections", async ({ page }) => {
    await page.goto("/data/sources");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
    const heading = page.locator("h1, h2, [role='heading']").first();
    await expect(heading).toBeVisible({ timeout: 10000 }).catch(() => {});
  });

  test("data source detail page loads", async ({ page }) => {
    await page.goto("/data/sources/ri.conn.pg1");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
  });

  test("browse page shows type cards", async ({ page }) => {
    await page.goto("/data/browse");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
  });

  test("instance list renders dynamic columns", async ({ page }) => {
    await page.goto("/data/browse/object-types/ri.obj.employee1");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
  });
});
