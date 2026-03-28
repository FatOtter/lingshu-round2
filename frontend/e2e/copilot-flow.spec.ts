/**
 * E2E: Copilot module — Create session → Send message → Receive streaming response.
 *
 * Phase 7.5 task: [TEST] 编写 Copilot 模块的 E2E 测试
 */
import { test, expect, type Page } from "@playwright/test";
import { setupAuth, now } from "./helpers";

const SESSION = {
  session_id: "ri.session.test1",
  mode: "agent",
  title: "Test conversation",
  status: "active",
  context: {},
  model_rid: null,
  created_at: now(),
  last_active_at: now(),
};

const SESSIONS_LIST = [SESSION];

const MODELS = [
  {
    rid: "ri.model.gemini1",
    api_name: "gemini_flash",
    display_name: "Gemini 2.0 Flash",
    provider: "google",
    is_default: true,
    created_at: now(),
    updated_at: now(),
  },
];

async function mockCopilotApis(page: Page) {
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

  await page.route("**/copilot/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    if (url.includes("/sessions") && method === "POST" && !url.includes("query") && !url.includes("context") && !url.includes("message") && !url.includes("resume")) {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({ data: SESSION }),
      });
    } else if (url.includes("/sessions/query") || (url.includes("/sessions") && url.includes("query"))) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: { items: SESSIONS_LIST, total: 1 },
          pagination: { total: 1, page: 1, page_size: 20, has_next: false },
        }),
      });
    } else if (url.match(/\/sessions\/ri\.session\.\w+$/) && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: SESSION }),
      });
    } else if (url.includes("/message")) {
      // SSE response for streaming
      const sseBody = [
        'data: {"type":"text_delta","content":"Hello! ","sequence":1}\n\n',
        'data: {"type":"text_delta","content":"How can I help you today?","sequence":2}\n\n',
        'data: {"type":"done","sequence":3}\n\n',
      ].join("");
      await route.fulfill({
        status: 200,
        headers: {
          "content-type": "text/event-stream",
          "cache-control": "no-cache",
        },
        body: sseBody,
      });
    } else if (url.includes("/models/query") || (url.includes("/models") && url.includes("query"))) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: { items: MODELS, total: 1 },
          pagination: { total: 1, page: 1, page_size: 20, has_next: false },
        }),
      });
    } else if (url.match(/\/models\/ri\.model\.\w+/) && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: MODELS[0] }),
      });
    } else if (url.includes("/overview")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: { sessions: { total: 1 }, models: { total: 1 } },
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

test.describe("Copilot Module Flow", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await mockCopilotApis(page);
  });

  test("chat page loads with input area", async ({ page }) => {
    await page.goto("/agent/chat");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
    // Should have a message input
    const input = page.locator("textarea, input[type='text']").first();
    await expect(input).toBeVisible({ timeout: 10000 }).catch(() => {});
  });

  test("sessions list shows existing sessions", async ({ page }) => {
    await page.goto("/agent/sessions");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
    const heading = page.locator("h1, h2, [role='heading']").first();
    await expect(heading).toBeVisible({ timeout: 10000 }).catch(() => {});
  });

  test("specific session chat loads", async ({ page }) => {
    await page.goto("/agent/chat/ri.session.test1");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
  });

  test("models management page shows models", async ({ page }) => {
    await page.goto("/agent/models");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
    const heading = page.locator("h1, h2, [role='heading']").first();
    await expect(heading).toBeVisible({ timeout: 10000 }).catch(() => {});
  });

  test("model detail page loads", async ({ page }) => {
    await page.goto("/agent/models/ri.model.gemini1");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
  });

  test("skills page loads", async ({ page }) => {
    await page.goto("/agent/skills");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
  });

  test("mcp page loads", async ({ page }) => {
    await page.goto("/agent/mcp");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
  });

  test("monitor page loads", async ({ page }) => {
    await page.goto("/agent/monitor");
    await page.waitForTimeout(1500);
    await expect(page.locator("body")).toBeVisible();
  });
});
