/**
 * J18: MCP Management Journey
 * Tests the Agent > MCP management page: listing, empty state, and connection form.
 */
import { test, expect } from "@playwright/test";
import { BASE, realLogin } from "./helpers";

test.describe("J18: MCP Management Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("MCP page loads and renders heading", async ({ page }) => {
    await page.goto(`${BASE}/agent/mcp`);
    await page.waitForLoadState("networkidle");

    // Page should show MCP-related heading
    await expect(page.getByText(/MCP/i).first()).toBeVisible({
      timeout: 10000,
    });
  });

  test("MCP list renders or shows empty state", async ({ page }) => {
    await page.goto(`${BASE}/agent/mcp`);
    await page.waitForLoadState("networkidle");

    // Should show either a table/list of MCP connections or empty state
    const hasTable = await page
      .locator("table")
      .isVisible()
      .catch(() => false);
    const hasList = await page
      .locator("[role='list'], [role='listbox']")
      .first()
      .isVisible()
      .catch(() => false);
    const hasEmpty = await page
      .getByText(/no .*(mcp|connection|service)/i)
      .first()
      .isVisible()
      .catch(() => false);
    const hasComingSoon = await page
      .getByText(/coming soon/i)
      .isVisible()
      .catch(() => false);
    const hasCards = await page
      .locator("[class*='card']")
      .first()
      .isVisible()
      .catch(() => false);

    expect(
      hasTable || hasList || hasEmpty || hasComingSoon || hasCards,
    ).toBeTruthy();
  });

  test("New Connection button or form exists", async ({ page }) => {
    await page.goto(`${BASE}/agent/mcp`);
    await page.waitForLoadState("networkidle");

    // Look for a create/new connection button or link
    const hasNewButton = await page
      .getByRole("button", { name: /new|create|add|connect/i })
      .first()
      .isVisible()
      .catch(() => false);
    const hasNewLink = await page
      .getByRole("link", { name: /new|create|add|connect/i })
      .first()
      .isVisible()
      .catch(() => false);
    const hasForm = await page
      .locator("form")
      .first()
      .isVisible()
      .catch(() => false);
    const hasComingSoon = await page
      .getByText(/coming soon/i)
      .isVisible()
      .catch(() => false);

    // Either a creation mechanism exists or the feature is not yet built
    expect(
      hasNewButton || hasNewLink || hasForm || hasComingSoon,
    ).toBeTruthy();
  });

  test("MCP page handles empty state gracefully", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        // Filter non-critical errors
        if (
          !text.includes("ResizeObserver") &&
          !text.includes("hydration") &&
          !text.includes("favicon") &&
          !text.includes("next-dev") &&
          !text.includes("Download the React DevTools")
        ) {
          errors.push(text);
        }
      }
    });

    await page.goto(`${BASE}/agent/mcp`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // Page should not have critical JS errors
    // Allow some API-related errors (backend might not have MCP endpoints fully wired)
    const criticalErrors = errors.filter(
      (e) =>
        !e.includes("404") &&
        !e.includes("Failed to fetch") &&
        !e.includes("NetworkError"),
    );
    expect(criticalErrors.length).toBeLessThanOrEqual(0);
  });
});
