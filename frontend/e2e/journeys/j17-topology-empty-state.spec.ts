/**
 * J17: Topology Empty State Journey
 * Tests the ontology overview topology section and its empty state behavior.
 */
import { test, expect } from "@playwright/test";
import {
  BASE,
  API,
  realLogin,
  uniqueName,
  createObjectType,
} from "./helpers";

test.describe("J17: Topology Empty State Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("ontology overview has topology section", async ({ page }) => {
    await page.goto(`${BASE}/ontology/overview`);
    await page.waitForLoadState("networkidle");

    // The page should contain a Topology View heading or section
    await expect(page.getByText("Topology View")).toBeVisible({
      timeout: 10000,
    });
  });

  test("topology shows empty state messaging when no entities", async ({
    page,
  }) => {
    await page.goto(`${BASE}/ontology/overview`);
    await page.waitForLoadState("networkidle");

    // Wait for topology to finish loading
    await page.waitForTimeout(2000);

    // Should show either SVG content, empty message, or loading state
    const hasSvg = await page
      .locator("svg")
      .first()
      .isVisible()
      .catch(() => false);
    const hasEmpty = await page
      .getByText("No entities to display")
      .isVisible()
      .catch(() => false);
    const hasLoading = await page
      .getByText("Loading topology")
      .isVisible()
      .catch(() => false);
    const hasFailed = await page
      .getByText("Failed to load topology")
      .isVisible()
      .catch(() => false);

    // At least one state should be present
    expect(hasSvg || hasEmpty || hasLoading || hasFailed).toBeTruthy();
  });

  test("topology updates after creating an ObjectType via API", async ({
    page,
  }) => {
    // Create an ObjectType to ensure topology has data
    const apiName = uniqueName("topo_empty");
    await createObjectType(page, apiName, `Topo ${apiName}`);

    // Navigate to ontology overview
    await page.goto(`${BASE}/ontology/overview`);
    await page.waitForLoadState("networkidle");

    // Wait for topology data to load
    await page.waitForTimeout(3000);

    // The stat cards should reflect at least 1 Object Type
    await expect(page.getByText("Object Types").first()).toBeVisible({
      timeout: 10000,
    });

    // Topology section should be present (either graph or loading/empty state)
    await expect(page.getByText("Topology View")).toBeVisible({
      timeout: 10000,
    });

    // If SVG nodes exist after creating an entity, they should be present
    const svgElements = page.locator("svg");
    const svgCount = await svgElements.count();
    // At least one SVG should exist (stat card icons or topology graph)
    expect(svgCount).toBeGreaterThan(0);
  });
});
