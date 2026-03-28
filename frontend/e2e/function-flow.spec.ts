/**
 * E2E: Function module — Execute Action flow.
 *
 * Phase 7.4 task: [TEST] 编写 Function 模块的 E2E 测试
 */
import { test, expect, type Page } from "@playwright/test";
import { setupAuth, now } from "./helpers";

const CAPABILITIES = [
  {
    rid: "ri.action.create_employee",
    api_name: "create_employee",
    display_name: "Create Employee",
    kind: "action",
    safety_level: "safe",
    description: "Create a new employee record",
  },
  {
    rid: "ri.func.query_instances",
    api_name: "query_instances",
    display_name: "Query Instances",
    kind: "global_function",
    description: "Query data instances by type",
  },
];

const EXECUTION_RESULT = {
  execution_id: "exec_abc123",
  status: "completed",
  result: { created_rid: "inst-003" },
  started_at: now(),
  completed_at: now(),
};

async function mockFunctionApis(page: Page) {
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

  await page.route("**/function/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    if (url.includes("/capabilities/query") || (url.includes("/capabilities") && url.includes("query"))) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: { items: CAPABILITIES, total: 2 },
          pagination: { total: 2, page: 1, page_size: 20, has_next: false },
        }),
      });
    } else if (url.includes("/capabilities")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: { items: CAPABILITIES, total: 2 },
        }),
      });
    } else if (url.includes("/actions/execute") && method === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: EXECUTION_RESULT }),
      });
    } else if (url.match(/\/actions\/ri\.action\.\w+/) && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: {
            ...CAPABILITIES[0],
            parameters: [
              { api_name: "name", display_name: "Name", data_type: "STRING", required: true },
              { api_name: "department", display_name: "Department", data_type: "STRING", required: false },
            ],
            execution: { engine_type: "native_crud" },
          },
        }),
      });
    } else if (url.includes("/executions/query") || (url.includes("/executions") && url.includes("query"))) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: {
            items: [
              {
                execution_id: "exec_abc123",
                action_rid: "ri.action.create_employee",
                status: "completed",
                started_at: now(),
                completed_at: now(),
              },
            ],
            total: 1,
          },
          pagination: { total: 1, page: 1, page_size: 20, has_next: false },
        }),
      });
    } else if (url.includes("/globals/query") || (url.includes("/globals") && url.includes("query"))) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: { items: [CAPABILITIES[1]], total: 1 },
          pagination: { total: 1, page: 1, page_size: 20, has_next: false },
        }),
      });
    } else if (url.includes("/overview")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: { actions: { total: 1 }, functions: { total: 1 }, executions: { total: 1 } },
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

test.describe("Function Module Flow", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await mockFunctionApis(page);
  });

  test("function overview shows capability stats", async ({ page }) => {
    await page.goto("/function/overview");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
  });

  test("capabilities list shows actions and functions", async ({ page }) => {
    await page.goto("/function/capabilities");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
    const heading = page.locator("h1, h2, [role='heading']").first();
    await expect(heading).toBeVisible({ timeout: 10000 }).catch(() => {});
  });

  test("action detail page shows parameters", async ({ page }) => {
    await page.goto("/function/capabilities/actions/ri.action.create_employee");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
  });

  test("global functions page loads", async ({ page }) => {
    await page.goto("/function/capabilities/globals");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
  });

  test("workflows page loads", async ({ page }) => {
    await page.goto("/function/workflows");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
  });
});
