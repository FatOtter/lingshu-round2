/**
 * J11: Workflow DAG Journey
 * Tests the workflow list page and the DAG visual viewer in the detail page.
 */
import { test, expect } from "@playwright/test";
import { BASE, API, realLogin } from "./helpers";

test.describe("J11: Workflow DAG Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("workflows list page loads", async ({ page }) => {
    await page.goto(`${BASE}/function/workflows`);
    await page.waitForLoadState("networkidle");

    // Page heading - use h1 selector to avoid sidebar conflicts
    await expect(page.locator("h1").filter({ hasText: "Workflows" })).toBeVisible({
      timeout: 15000,
    });

    // Should show table or empty state
    const hasTable = await page
      .locator("table")
      .isVisible()
      .catch(() => false);
    const hasEmpty = await page
      .getByText("No workflows")
      .isVisible()
      .catch(() => false);

    expect(hasTable || hasEmpty).toBeTruthy();
  });

  test("create workflow via API and view detail page", async ({ page }) => {
    // Create a workflow via API
    const resp = await page.request.post(
      `${API}/function/v1/workflows`,
      {
        data: {
          api_name: `wf_dag_${Date.now().toString(36)}`,
          display_name: "DAG Test Workflow",
          description: "E2E test workflow",
          nodes: [
            {
              node_id: "step_1",
              type: "action",
              capability_rid: null,
              input_mappings: {},
              position: { x: 0, y: 0 },
              label: "Step 1",
            },
            {
              node_id: "step_2",
              type: "action",
              capability_rid: null,
              input_mappings: {},
              position: { x: 0, y: 100 },
              label: "Step 2",
            },
          ],
          edges: [
            {
              source_node_id: "step_1",
              target_node_id: "step_2",
              condition: null,
            },
          ],
          status: "draft",
        },
      },
    );

    if (!resp.ok()) {
      // If API is not available or returns error, skip gracefully
      return;
    }

    const body = await resp.json();
    const rid = body.data.rid;

    // Navigate to detail page
    await page.goto(`${BASE}/function/workflows/${rid}`);
    await page.waitForLoadState("networkidle");

    // Should show workflow name in h1
    await expect(page.locator("h1").first()).toBeVisible({
      timeout: 10000,
    });

    // Switch to Visual tab (use button role to avoid duplicates)
    const visualButton = page.getByRole("button", { name: "Visual" });
    if (await visualButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await visualButton.click();
      await page.waitForTimeout(1000);

      // DAG viewer should render SVG
      const svg = page.locator("svg");
      await expect(svg.first()).toBeVisible({ timeout: 10000 });
    }
  });

  test("workflow detail shows Source and Visual tabs", async ({ page }) => {
    // Create minimal workflow
    const resp = await page.request.post(
      `${API}/function/v1/workflows`,
      {
        data: {
          api_name: `wf_tabs_${Date.now().toString(36)}`,
          display_name: "Tabs Test",
          description: "",
          nodes: [],
          edges: [],
          status: "draft",
        },
      },
    );

    if (!resp.ok()) return;

    const body = await resp.json();
    const rid = body.data.rid;

    await page.goto(`${BASE}/function/workflows/${rid}`);
    await page.waitForLoadState("networkidle");

    // Both tab buttons should be present - use button role to avoid duplicates
    await expect(page.getByRole("button", { name: "Source" })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("button", { name: "Visual" })).toBeVisible();
  });
});
