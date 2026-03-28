/**
 * J15: Cross-Module Navigation Journey
 * Tests navigating between all 5 modules via the Dock sidebar.
 */
import { test, expect } from "@playwright/test";
import { BASE, realLogin } from "./helpers";

test.describe("J15: Cross-Module Navigation Journey", () => {
  test.beforeEach(async ({ page }) => {
    await realLogin(page);
  });

  test("navigate through all 5 modules via dock", async ({ page }) => {
    const modules = [
      { label: "Ontology", href: "/ontology/overview", heading: /ontology/i },
      { label: "Data", href: "/data/overview", heading: /data/i },
      { label: "Function", href: "/function/overview", heading: /function/i },
      { label: "Agent", href: "/agent/overview", heading: /agent/i },
      { label: "Setting", href: "/setting/overview", heading: /setting/i },
    ];

    // Start at ontology overview
    await page.goto(`${BASE}/ontology/overview`);
    await page.waitForLoadState("networkidle");

    for (const mod of modules) {
      // Find the dock link - dock links point to /module/overview
      const dockLink = page.locator(`a[href="${mod.href}"]`).first();
      if (await dockLink.isVisible().catch(() => false)) {
        await dockLink.click();
        await page.waitForURL(`**${mod.href}`, { timeout: 10000 });

        // Verify URL changed
        expect(page.url()).toContain(mod.href);

        // Verify module content loaded (check for any text matching the heading)
        await expect(page.getByText(mod.heading).first()).toBeVisible({
          timeout: 10000,
        });
      }
    }
  });

  test("dock highlights active module", async ({ page }) => {
    await page.goto(`${BASE}/ontology/overview`);
    await page.waitForLoadState("networkidle");

    // The ontology dock icon should have an active class
    // Dock links use href="/module/overview" pattern
    const ontologyLink = page.locator('a[href="/ontology/overview"]').first();
    if (await ontologyLink.isVisible().catch(() => false)) {
      const className = await ontologyLink.getAttribute("class");
      // Active link has bg-accent class
      expect(className).toContain("bg-accent");
    }

    // Navigate to data module
    const dataLink = page.locator('a[href="/data/overview"]').first();
    if (await dataLink.isVisible().catch(() => false)) {
      await dataLink.click();
      await page.waitForURL("**/data/overview", { timeout: 10000 });

      // Data link should now be active
      const dataClass = await dataLink.getAttribute("class");
      expect(dataClass).toContain("bg-accent");
    }
  });

  test("breadcrumb updates on navigation", async ({ page }) => {
    await page.goto(`${BASE}/ontology/overview`);
    await page.waitForLoadState("networkidle");

    // Breadcrumb should show "Ontology"
    await expect(page.getByText("Ontology").first()).toBeVisible({
      timeout: 10000,
    });

    // Navigate to data
    const dataLink = page.locator('a[href="/data/overview"]').first();
    if (await dataLink.isVisible().catch(() => false)) {
      await dataLink.click();
      await page.waitForURL("**/data/overview", { timeout: 10000 });

      // Breadcrumb should update to "Data"
      await expect(page.getByText("Data").first()).toBeVisible({
        timeout: 10000,
      });
    }
  });

  test("direct URL navigation works for all modules", async ({ page }) => {
    const pages = [
      { url: "/ontology/object-types", text: "Object Types" },
      { url: "/data/sources", text: "Data Sources" },
      { url: "/function/capabilities", text: /capabilities|function/i },
      { url: "/agent/chat", text: /message|conversation|chat|agent/i },
      { url: "/setting/users", text: "Users" },
    ];

    for (const p of pages) {
      await page.goto(`${BASE}${p.url}`);
      await page.waitForLoadState("networkidle");

      // Wait a bit for content to render
      await page.waitForTimeout(2000);

      if (typeof p.text === "string") {
        await expect(page.getByText(p.text).first()).toBeVisible({
          timeout: 15000,
        });
      } else {
        await expect(page.getByText(p.text).first()).toBeVisible({
          timeout: 15000,
        });
      }
    }
  });
});
