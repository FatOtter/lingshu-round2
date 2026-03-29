/**
 * Shared helpers for regression E2E tests.
 * All tests in this directory target the backend directly via API (no Docker frontend needed).
 * Backend must be running on BACKEND_URL with LINGSHU_AUTH_MODE=dev.
 */
import { expect, type APIRequestContext } from "@playwright/test";

export const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export interface AuthHeaders {
  "Content-Type": string;
  "X-User-Id": string;
  "X-Tenant-Id": string;
  "X-Role": string;
}

/** Login via API and return dev-mode bypass headers */
export async function getAuthHeaders(
  request: APIRequestContext,
): Promise<AuthHeaders> {
  const loginRes = await request.post(`${BACKEND}/setting/v1/auth/login`, {
    data: { email: "admin@lingshu.dev", password: "admin123" },
  });
  expect(loginRes.ok()).toBeTruthy();
  const body = await loginRes.json();
  return {
    "Content-Type": "application/json",
    "X-User-Id": body.data.user.rid,
    "X-Tenant-Id": body.data.user.tenant.rid,
    "X-Role": "admin",
  };
}

/** Generate a unique name to avoid test data collisions */
export function uniqueName(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

/** Standard pagination body */
export function paginated(page = 1, pageSize = 20) {
  return { pagination: { page, page_size: pageSize } };
}
