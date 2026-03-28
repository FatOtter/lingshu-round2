/**
 * J03: Entity Delete Journey
 * Tests deleting an orphan entity via the UI and verifying the list updates.
 */
import { test, expect } from "@playwright/test";
import { BASE, API, realLogin, uniqueName, createObjectType } from "./helpers";

test.describe("J03: Entity Delete Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("delete orphan entity via detail page", async ({ page }) => {
    // Create an entity via API
    const apiName = uniqueName("del_orphan");
    const rid = await createObjectType(page, apiName, `Delete ${apiName}`);

    // Navigate to the detail page
    await page.goto(`${BASE}/ontology/object-types/${rid}`);
    await page.waitForLoadState("networkidle");

    // Click the Delete button
    await expect(
      page.getByRole("button", { name: /delete/i }),
    ).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: /delete/i }).click();

    // Confirm in the dialog
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible({ timeout: 5000 });
    await dialog.getByRole("button", { name: /delete/i }).click();

    // Should redirect back to the list page
    await page.waitForURL("**/ontology/object-types", { timeout: 15000 });

    // The entity should no longer be visible
    await page.waitForLoadState("networkidle");
    const entityVisible = await page
      .getByText(apiName)
      .first()
      .isVisible()
      .catch(() => false);
    expect(entityVisible).toBeFalsy();
  });

  test("delete via API and verify list is updated", async ({ page }) => {
    // Create entity
    const apiName = uniqueName("del_api");
    const rid = await createObjectType(page, apiName, `ApiDel ${apiName}`);

    // Acquire lock and delete via API
    await page.request.post(`${API}/ontology/v1/object-types/${rid}/lock`);
    const delResp = await page.request.delete(
      `${API}/ontology/v1/object-types/${rid}`,
    );
    expect(delResp.ok()).toBeTruthy();

    // Navigate to the list page and confirm entity is gone
    await page.goto(`${BASE}/ontology/object-types`);
    await page.waitForLoadState("networkidle");

    // Wait a moment for data to settle, then check
    await page.waitForTimeout(1000);
    const visible = await page
      .getByText(apiName)
      .first()
      .isVisible()
      .catch(() => false);
    expect(visible).toBeFalsy();
  });
});
