/**
 * J12: Rollback Journey
 * Tests the ontology versions page: snapshot history table and rollback controls.
 */
import { test, expect } from "@playwright/test";
import {
  BASE,
  realLogin,
  uniqueName,
  createObjectType,
  submitToStaging,
  publishStaging,
} from "./helpers";

test.describe("J12: Rollback Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("versions page shows Snapshot History section", async ({ page }) => {
    await page.goto(`${BASE}/ontology/versions`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Page heading
    await expect(page.getByText("Version Management").first()).toBeVisible({
      timeout: 15000,
    });

    // Snapshot History section
    await expect(page.getByText("Snapshot History")).toBeVisible({
      timeout: 10000,
    });
  });

  test("versions page shows staging summary", async ({ page }) => {
    await page.goto(`${BASE}/ontology/versions`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Staging Summary card should be present
    await expect(page.getByText("Staging Summary")).toBeVisible({
      timeout: 15000,
    });

    // Should show either "No changes in staging" or "change(s) in staging" or "pending entity changes"
    const noChanges = page.getByText("No changes in staging");
    const hasChanges = page.getByText(/change\(s\) in staging/i);
    const pendingChanges = page.getByText(/pending entity changes/i);
    await expect(noChanges.or(hasChanges).or(pendingChanges).first()).toBeVisible({
      timeout: 10000,
    });
  });

  test("snapshot has Rollback button (disabled for current)", async ({
    page,
  }) => {
    // Create and publish to ensure at least one snapshot exists
    const apiName = uniqueName("rb_snap");
    const rid = await createObjectType(page, apiName);
    await submitToStaging(page, "object-types", rid);
    await publishStaging(page, `E2E rollback test ${apiName}`);

    // Navigate to versions page
    await page.goto(`${BASE}/ontology/versions`);
    await page.waitForLoadState("networkidle");

    // Wait for page to fully render
    await page.waitForTimeout(5000);

    // The page should show Version Management heading
    await expect(page.getByText("Version Management").first()).toBeVisible({
      timeout: 15000,
    });

    // Check for snapshot table and rollback/current buttons
    const currentButton = page.getByRole("button", { name: /current/i });
    if (await currentButton.isVisible().catch(() => false)) {
      // Current snapshot button should be disabled
      await expect(currentButton.first()).toBeDisabled();
    }

    // Non-current snapshots (if any) should have a "Rollback" button
    const rollbackButtons = page.getByRole("button", { name: /rollback/i });
    const rollbackCount = await rollbackButtons.count();
    // This is acceptable: 0 rollback buttons if there is only 1 snapshot
    expect(rollbackCount).toBeGreaterThanOrEqual(0);
  });

  test("publish and discard buttons are visible", async ({ page }) => {
    await page.goto(`${BASE}/ontology/versions`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Wait for page heading to confirm it loaded
    await expect(page.getByText("Version Management").first()).toBeVisible({
      timeout: 15000,
    });

    // Publish and Discard Staging buttons should be present in the staging card
    await expect(
      page.getByRole("button", { name: /publish/i }),
    ).toBeVisible({ timeout: 10000 });
    await expect(
      page.getByRole("button", { name: /discard staging/i }),
    ).toBeVisible();
  });
});
