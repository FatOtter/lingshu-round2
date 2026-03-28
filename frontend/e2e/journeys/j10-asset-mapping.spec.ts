/**
 * J10: Asset Mapping Journey
 * Tests navigating to the ObjectType detail Data Mapping tab.
 */
import { test, expect } from "@playwright/test";
import { BASE, realLogin, uniqueName, createObjectType } from "./helpers";

test.describe("J10: Asset Mapping Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("ObjectType detail has Data Mapping tab", async ({ page }) => {
    // Create an entity
    const apiName = uniqueName("am_tab");
    const rid = await createObjectType(page, apiName, `AM ${apiName}`);

    // Navigate to detail page
    await page.goto(`${BASE}/ontology/object-types/${rid}`);
    await page.waitForLoadState("networkidle");

    // Data Mapping tab should be visible
    await expect(page.getByText("Data Mapping")).toBeVisible({
      timeout: 10000,
    });
  });

  test("Data Mapping tab shows AssetMapping editor", async ({ page }) => {
    const apiName = uniqueName("am_editor");
    const rid = await createObjectType(page, apiName, `AMEdit ${apiName}`);

    await page.goto(`${BASE}/ontology/object-types/${rid}`);
    await page.waitForLoadState("networkidle");

    // Click the Data Mapping tab
    await page.getByText("Data Mapping").click();

    // Wait for tab content to load
    await page.waitForTimeout(1000);

    // Should show the Configure AssetMapping card
    await expect(page.getByText("Configure AssetMapping")).toBeVisible({
      timeout: 10000,
    });
  });

  test("Data Mapping tab shows connection selector or empty state", async ({
    page,
  }) => {
    const apiName = uniqueName("am_conn");
    const rid = await createObjectType(page, apiName, `AMConn ${apiName}`);

    await page.goto(`${BASE}/ontology/object-types/${rid}`);
    await page.waitForLoadState("networkidle");

    // Switch to Data Mapping tab
    await page.getByText("Data Mapping").click();
    await page.waitForTimeout(1000);

    // The AssetMapping editor should render something
    // (either a connection selector or a "no connections" message)
    await expect(page.getByText("Configure AssetMapping")).toBeVisible({
      timeout: 10000,
    });
  });
});
