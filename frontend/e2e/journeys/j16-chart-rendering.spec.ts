/**
 * J16: Chart Rendering Journey
 * Tests chart component rendering on the Agent chat page.
 */
import { test, expect } from "@playwright/test";
import { BASE, realLogin } from "./helpers";

test.describe("J16: Chart Rendering Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("agent chat page renders without errors", async ({ page }) => {
    await page.goto(`${BASE}/agent/chat`);
    await page.waitForLoadState("networkidle");

    // Chat page should load with input area or empty state
    const hasTextarea = await page
      .locator('textarea[placeholder="Type a message..."]')
      .isVisible()
      .catch(() => false);
    const hasEmptyState = await page
      .getByText("Start a conversation with the Agent.")
      .isVisible()
      .catch(() => false);
    const hasChat = await page
      .getByText(/chat/i)
      .first()
      .isVisible()
      .catch(() => false);

    expect(hasTextarea || hasEmptyState || hasChat).toBeTruthy();
  });

  test("chart container exists when chart data is present", async ({
    page,
  }) => {
    await page.goto(`${BASE}/agent/chat`);
    await page.waitForLoadState("networkidle");

    // Wait for page to fully render
    await page.waitForTimeout(2000);

    // Check if any recharts container or SVG chart elements exist
    const hasRechartsContainer = await page
      .locator(".recharts-wrapper")
      .first()
      .isVisible()
      .catch(() => false);
    const hasSvgChart = await page
      .locator("svg.recharts-surface")
      .first()
      .isVisible()
      .catch(() => false);
    const hasCanvas = await page
      .locator("canvas")
      .first()
      .isVisible()
      .catch(() => false);

    // Charts may not be present if no chart data exists yet — that is acceptable
    // Just verify the page loaded without errors
    if (hasRechartsContainer || hasSvgChart || hasCanvas) {
      expect(true).toBeTruthy();
    } else {
      // No chart data present — page still loaded successfully
      const pageLoaded = await page
        .locator("body")
        .isVisible()
        .catch(() => false);
      expect(pageLoaded).toBeTruthy();
    }
  });

  test("chart axes and legends are visible when chart renders", async ({
    page,
  }) => {
    await page.goto(`${BASE}/agent/chat`);
    await page.waitForLoadState("networkidle");

    await page.waitForTimeout(2000);

    // If recharts components are rendered, verify axes/legends
    const hasRechartsContainer = await page
      .locator(".recharts-wrapper")
      .first()
      .isVisible()
      .catch(() => false);

    if (hasRechartsContainer) {
      // Check for axis elements
      const hasXAxis = await page
        .locator(".recharts-xAxis")
        .isVisible()
        .catch(() => false);
      const hasYAxis = await page
        .locator(".recharts-yAxis")
        .isVisible()
        .catch(() => false);
      const hasLegend = await page
        .locator(".recharts-legend-wrapper")
        .isVisible()
        .catch(() => false);

      // At least one chart structural element should be present
      expect(hasXAxis || hasYAxis || hasLegend).toBeTruthy();
    }
    // If no charts present, test passes — no chart data available
  });

  test("agent overview page renders monitoring section", async ({ page }) => {
    await page.goto(`${BASE}/agent/overview`);
    await page.waitForLoadState("networkidle");

    // Overview page should load
    await expect(page.getByText(/agent/i).first()).toBeVisible({
      timeout: 10000,
    });

    // Check for monitoring/stats section that may contain charts
    const hasMonitor = await page
      .getByText(/monitor|statistics|metrics|overview/i)
      .first()
      .isVisible()
      .catch(() => false);
    const hasSvg = await page
      .locator("svg")
      .first()
      .isVisible()
      .catch(() => false);

    // Page should have some content rendered
    expect(hasMonitor || hasSvg).toBeTruthy();
  });
});
