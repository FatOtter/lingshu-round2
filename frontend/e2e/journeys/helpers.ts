import { expect, type Page } from "@playwright/test";

export const BASE = "http://localhost:3100";
export const API = "http://localhost:8100";

/** Login via API and inject cookies into browser context */
export async function realLogin(page: Page) {
  const resp = await page.request.post(`${API}/setting/v1/auth/login`, {
    data: { email: "admin@lingshu.dev", password: "admin123" },
  });
  expect(resp.ok()).toBeTruthy();

  const headers = resp.headersArray();
  const cookies: Array<{
    name: string;
    value: string;
    domain: string;
    path: string;
    httpOnly: boolean;
    sameSite: "Lax" | "Strict" | "None";
  }> = [];
  for (const h of headers) {
    if (h.name.toLowerCase() === "set-cookie") {
      const parts = h.value.split(";");
      const [nameVal] = parts;
      const [name, ...rest] = nameVal.split("=");
      const value = rest.join("=");
      const pathMatch = h.value.match(/Path=([^;]+)/i);
      cookies.push({
        name: name.trim(),
        value: value.trim(),
        domain: "localhost",
        path: pathMatch ? pathMatch[1] : "/",
        httpOnly: true,
        sameSite: "Lax",
      });
    }
  }
  await page.context().addCookies(cookies);
}

/** Create an ObjectType via API and return its RID */
export async function createObjectType(
  page: Page,
  apiName: string,
  displayName?: string,
): Promise<string> {
  const resp = await page.request.post(`${API}/ontology/v1/object-types`, {
    data: {
      api_name: apiName,
      display_name: displayName ?? apiName,
      description: `E2E test entity ${apiName}`,
    },
  });
  expect(resp.ok()).toBeTruthy();
  const body = await resp.json();
  return body.data.rid;
}

/** Submit entity to staging via API */
export async function submitToStaging(
  page: Page,
  entityType: string,
  rid: string,
) {
  const resp = await page.request.post(
    `${API}/ontology/v1/${entityType}/${rid}/submit-to-staging`,
  );
  return resp;
}

/** Publish all staging changes */
export async function publishStaging(page: Page, message?: string) {
  const resp = await page.request.post(`${API}/ontology/v1/staging/commit`, {
    data: { commit_message: message ?? "E2E test publish" },
  });
  return resp;
}

/** Acquire edit lock on entity */
export async function acquireLock(
  page: Page,
  entityType: string,
  rid: string,
) {
  return page.request.post(`${API}/ontology/v1/${entityType}/${rid}/lock`);
}

/** Delete entity via API */
export async function deleteEntity(
  page: Page,
  entityType: string,
  rid: string,
) {
  await acquireLock(page, entityType, rid);
  return page.request.delete(`${API}/ontology/v1/${entityType}/${rid}`);
}

/** Generate unique test name to avoid conflicts */
export function uniqueName(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}`;
}

/** Filter known non-critical console errors */
export function isNonCriticalError(message: string): boolean {
  return (
    message.includes("ResizeObserver") ||
    message.includes("hydration") ||
    message.includes("favicon") ||
    message.includes("next-dev") ||
    message.includes("Download the React DevTools")
  );
}
