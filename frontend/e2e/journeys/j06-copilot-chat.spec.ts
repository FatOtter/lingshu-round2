/**
 * J06: Copilot Chat Journey
 * Tests the agent chat page: session creation, message sending, and response rendering.
 */
import { test, expect } from "@playwright/test";
import { BASE, realLogin } from "./helpers";

test.describe("J06: Copilot Chat Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("agent chat page creates session and shows empty state", async ({
    page,
  }) => {
    await page.goto(`${BASE}/agent/chat`);

    // Wait for session to be created (spinner disappears, empty state appears)
    await expect(
      page.getByText("Start a conversation with the Agent."),
    ).toBeVisible({ timeout: 15000 });

    // Input area should be present
    await expect(
      page.locator('textarea[placeholder="Type a message..."]'),
    ).toBeVisible();
  });

  test("send a message and wait for response", async ({ page }) => {
    await page.goto(`${BASE}/agent/chat`);

    // Wait for session to be ready
    await expect(
      page.getByText("Start a conversation with the Agent."),
    ).toBeVisible({ timeout: 15000 });

    // Type and send a message
    const textarea = page.locator('textarea[placeholder="Type a message..."]');
    await textarea.fill("Hello, what can you help me with?");

    // Click send button
    const sendButton = page.locator('button:has(svg)').last();
    await sendButton.click();

    // The user message should appear in the chat
    await expect(
      page.getByText("Hello, what can you help me with?"),
    ).toBeVisible({ timeout: 10000 });

    // Wait for an assistant response (or streaming indicator)
    const responseOrThinking = page
      .locator(".bg-muted")
      .or(page.getByText("Thinking..."));
    await expect(responseOrThinking.first()).toBeVisible({ timeout: 30000 });
  });

  test("send message via Enter key", async ({ page }) => {
    await page.goto(`${BASE}/agent/chat`);

    // Wait for ready
    await expect(
      page.getByText("Start a conversation with the Agent."),
    ).toBeVisible({ timeout: 15000 });

    const textarea = page.locator('textarea[placeholder="Type a message..."]');
    await textarea.fill("Test message via enter");
    await textarea.press("Enter");

    // User message should appear
    await expect(page.getByText("Test message via enter")).toBeVisible({
      timeout: 10000,
    });
  });
});
