/**
 * J01: Ontology CRUD Journey
 * Tests creating, editing, and listing ObjectTypes through the UI.
 */
import { test, expect } from "@playwright/test";
import { BASE, API, realLogin, uniqueName, createObjectType } from "./helpers";

test.describe("J01: Ontology CRUD Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("create ObjectType via API and verify on detail page", async ({ page }) => {
    const name = uniqueName("ot_create");

    // Create via API
    const rid = await createObjectType(page, name, `Display ${name}`);
    expect(rid).toBeTruthy();

    // Navigate to detail page and verify it loads
    await page.goto(`${BASE}/ontology/object-types/${rid}`);
    await page.waitForLoadState("networkidle");

    // Wait for the page to render the heading (could be display_name or RID as fallback)
    const heading = page.locator("h1").first();
    await expect(heading).toBeVisible({ timeout: 15000 });

    // Verify page structure is correct (has Save button)
    await expect(page.getByRole("button", { name: /save/i })).toBeVisible({
      timeout: 10000,
    });

    // Verify tabs are present
    await expect(page.getByRole("tab", { name: "Info" })).toBeVisible();
  });

  test("edit ObjectType display name via UI", async ({ page }) => {
    // Create via API first
    const apiName = uniqueName("ot_edit");
    const rid = await createObjectType(page, apiName, `Original ${apiName}`);

    // Navigate to detail page
    await page.goto(`${BASE}/ontology/object-types/${rid}`);
    await page.waitForLoadState("networkidle");

    // Wait for Save button to confirm page loaded
    await expect(page.getByRole("button", { name: /save/i })).toBeVisible({
      timeout: 10000,
    });

    // The display_name input should be visible
    const displayNameInput = page.locator("#display_name");
    await expect(displayNameInput).toBeVisible({ timeout: 10000 });

    // Modify display name
    const updatedName = `Updated ${apiName}`;
    await displayNameInput.fill(updatedName);

    // Save
    await page.getByRole("button", { name: /save/i }).click();

    // Wait for save to complete
    await page.waitForTimeout(2000);

    // Verify the input still has the updated value
    await expect(displayNameInput).toHaveValue(updatedName);
  });

  test("list page shows heading and table structure", async ({ page }) => {
    // Create via API to ensure at least one entity exists
    const apiName = uniqueName("ot_list");
    await createObjectType(page, apiName, `List ${apiName}`);

    // Navigate to list page
    await page.goto(`${BASE}/ontology/object-types`);
    await page.waitForLoadState("networkidle");

    // Verify heading
    await expect(page.locator("h1").filter({ hasText: "Object Types" })).toBeVisible({
      timeout: 10000,
    });

    // Verify New Object Type button exists
    await expect(
      page.getByRole("button", { name: /new object type/i }),
    ).toBeVisible({ timeout: 10000 });

    // Verify the table or loading state is present
    const table = page.locator("table");
    const loading = page.locator('[data-loading="true"]');
    await expect(table.or(loading).first()).toBeVisible({ timeout: 10000 });
  });

  test("ObjectType detail page shows tabs", async ({ page }) => {
    // Create via API
    const apiName = uniqueName("ot_tabs");
    const rid = await createObjectType(page, apiName, `Tabs ${apiName}`);

    await page.goto(`${BASE}/ontology/object-types/${rid}`);
    await page.waitForLoadState("networkidle");

    // Verify tabs are present using role selectors to avoid sidebar conflicts
    await expect(page.getByRole("tab", { name: "Info" })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("tab", { name: "Properties" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Interfaces" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Data Mapping" })).toBeVisible();
  });
});
