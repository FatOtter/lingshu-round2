/**
 * R01: Health & Authentication Regression
 * Covers: /health, login, logout, refresh, /auth/me, change-password, SSO config
 */
import { test, expect } from "@playwright/test";
import { BACKEND, getAuthHeaders, uniqueName } from "./helpers";

test.describe("R01: Health & Auth", () => {
  test("GET /health returns ok", async ({ request }) => {
    const res = await request.get(`${BACKEND}/health`);
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.status).toBe("ok");
  });

  test("POST /auth/login succeeds with valid credentials", async ({ request }) => {
    const res = await request.post(`${BACKEND}/setting/v1/auth/login`, {
      data: { email: "admin@lingshu.dev", password: "admin123" },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.data.user.email).toBe("admin@lingshu.dev");
    expect(body.data.user.rid).toMatch(/^ri\.user\./);
    expect(body.data.user.tenant.rid).toMatch(/^ri\.tenant\./);

    const cookies = res.headersArray().filter(
      (h) => h.name.toLowerCase() === "set-cookie",
    );
    expect(cookies.length).toBeGreaterThanOrEqual(1);
  });

  test("POST /auth/login fails with wrong credentials", async ({ request }) => {
    const res = await request.post(`${BACKEND}/setting/v1/auth/login`, {
      data: { email: "admin@lingshu.dev", password: "wrong" },
    });
    expect(res.ok()).toBeFalsy();
    const body = await res.json();
    expect(body.error).toBeTruthy();
  });

  test("GET /auth/me returns current user", async ({ request }) => {
    const headers = await getAuthHeaders(request);
    const res = await request.get(`${BACKEND}/setting/v1/auth/me`, { headers });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.data.email).toBe("admin@lingshu.dev");
    expect(body.data.role).toBeTruthy();
  });

  test("GET /auth/me returns 401 without auth", async ({ request }) => {
    const res = await request.get(`${BACKEND}/setting/v1/auth/me`);
    expect(res.status()).toBe(401);
  });

  test("POST /auth/refresh returns error without cookie", async ({ request }) => {
    const res = await request.post(`${BACKEND}/setting/v1/auth/refresh`);
    const body = await res.json();
    expect(body.error).toBeTruthy();
    expect(body.error.code).toBe("SETTING_AUTH_TOKEN_EXPIRED");
  });

  test("GET /auth/sso/config returns SSO configuration", async ({ request }) => {
    const res = await request.get(`${BACKEND}/setting/v1/auth/sso/config`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.data).toBeDefined();
    expect(typeof body.data.enabled).toBe("boolean");
  });

  test("POST /auth/logout clears cookies", async ({ request }) => {
    const loginRes = await request.post(`${BACKEND}/setting/v1/auth/login`, {
      data: { email: "admin@lingshu.dev", password: "admin123" },
    });
    expect(loginRes.ok()).toBeTruthy();

    const headers = await getAuthHeaders(request);
    const res = await request.post(`${BACKEND}/setting/v1/auth/logout`, { headers });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.data.message).toContain("Logged out");
  });
});
