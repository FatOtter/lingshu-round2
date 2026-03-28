/**
 * J07: Shell SSE Journey
 * Tests the Copilot Shell panel: open/close, send message, receive response.
 */
import { test, expect } from "@playwright/test";
import { BASE, realLogin } from "./helpers";

test.describe("J07: Shell SSE Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("open Shell panel via header button", async ({ page }) => {
    // Navigate to a non-agent page (Shell button hidden on agent pages)
    await page.goto(`${BASE}/ontology/overview`);
    await page.waitForLoadState("networkidle");

    // Click the Copilot toggle button in the header
    const toggleButton = page.locator(
      'button[aria-label="Toggle Copilot Shell"]',
    );
    await expect(toggleButton).toBeVisible({ timeout: 10000 });
    await toggleButton.click();

    // Shell panel should appear with "Copilot" header
    await expect(page.getByText("Copilot").last()).toBeVisible({
      timeout: 10000,
    });

    // The empty state or session loading should be visible
    const readyState = page
      .getByText("Ask me anything about your current context.")
      .or(page.locator(".animate-spin"));
    await expect(readyState.first()).toBeVisible({ timeout: 10000 });
  });

  test("close Shell and reopen preserves panel", async ({ page }) => {
    await page.goto(`${BASE}/ontology/overview`);
    await page.waitForLoadState("networkidle");

    const toggleButton = page.locator(
      'button[aria-label="Toggle Copilot Shell"]',
    );

    // Open
    await toggleButton.click();
    await expect(page.getByText("Copilot").last()).toBeVisible({
      timeout: 10000,
    });

    // Close via the toggle button again
    await toggleButton.click();
    await page.waitForTimeout(500);

    // Reopen
    await toggleButton.click();
    await expect(page.getByText("Copilot").last()).toBeVisible({
      timeout: 10000,
    });
  });

  test("Shell sends message and gets response", async ({ page }) => {
    await page.goto(`${BASE}/ontology/overview`);
    await page.waitForLoadState("networkidle");

    // Open Shell
    const toggleButton = page.locator(
      'button[aria-label="Toggle Copilot Shell"]',
    );
    await toggleButton.click();

    // Wait for session to be ready
    await expect(
      page.getByText("Ask me anything about your current context."),
    ).toBeVisible({ timeout: 15000 });

    // Type a message
    const textarea = page.locator('textarea[placeholder="Ask Copilot..."]');
    await textarea.fill("Hello from Shell");
    await textarea.press("Enter");

    // User message should appear
    await expect(page.getByText("Hello from Shell")).toBeVisible({
      timeout: 10000,
    });

    // Wait for response (Thinking... or actual response text)
    const response = page
      .locator(".bg-muted")
      .or(page.getByText("Thinking..."));
    await expect(response.first()).toBeVisible({ timeout: 30000 });
  });

  test("Shell button is hidden on agent module pages", async ({ page }) => {
    await page.goto(`${BASE}/agent/overview`);
    await page.waitForLoadState("networkidle");

    // The toggle button should not be present on agent pages
    const toggleButton = page.locator(
      'button[aria-label="Toggle Copilot Shell"]',
    );
    await expect(toggleButton).not.toBeVisible({ timeout: 5000 });
  });
});
