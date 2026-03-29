/**
 * R02: Setting — Users CRUD Regression
 * Covers: create, query, get, update, delete, reset-password
 */
import { test, expect } from "@playwright/test";
import { BACKEND, getAuthHeaders, uniqueName, paginated } from "./helpers";

test.describe("R02: Users CRUD", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("POST /users creates a new user", async ({ request }) => {
    const name = uniqueName("usr");
    const res = await request.post(`${BACKEND}/setting/v1/users`, {
      headers,
      data: {
        email: `${name}@test.dev`,
        display_name: `Test ${name}`,
        password: "Test1234!",
        role: "viewer",
      },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.data.rid).toMatch(/^ri\.user\./);
    expect(body.data.email).toBe(`${name}@test.dev`);
  });

  test("POST /users/query returns paginated users", async ({ request }) => {
    const res = await request.post(`${BACKEND}/setting/v1/users/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.pagination).toBeTruthy();
    expect(body.pagination.total).toBeGreaterThanOrEqual(1);
    expect(Array.isArray(body.data)).toBeTruthy();
    expect(body.data[0].email).toBeTruthy();
  });

  test("GET /users/{rid} returns user details", async ({ request }) => {
    const queryRes = await request.post(`${BACKEND}/setting/v1/users/query`, {
      headers,
      data: paginated(),
    });
    const users = (await queryRes.json()).data;
    const rid = users[0].rid;

    const res = await request.get(`${BACKEND}/setting/v1/users/${rid}`, { headers });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.data.rid).toBe(rid);
    expect(body.data.email).toBeTruthy();
  });

  test("PUT /users/{rid} updates a user", async ({ request }) => {
    const name = uniqueName("upd");
    const createRes = await request.post(`${BACKEND}/setting/v1/users`, {
      headers,
      data: {
        email: `${name}@test.dev`,
        display_name: `Original ${name}`,
        password: "Test1234!",
        role: "viewer",
      },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.put(`${BACKEND}/setting/v1/users/${rid}`, {
      headers,
      data: { display_name: `Updated ${name}` },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.data.display_name).toBe(`Updated ${name}`);
  });

  test("POST /users/{rid}/reset-password resets password", async ({ request }) => {
    const name = uniqueName("rst");
    const createRes = await request.post(`${BACKEND}/setting/v1/users`, {
      headers,
      data: {
        email: `${name}@test.dev`,
        display_name: name,
        password: "Test1234!",
        role: "viewer",
      },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.post(
      `${BACKEND}/setting/v1/users/${rid}/reset-password`,
      { headers, data: { new_password: "NewPass5678!" } },
    );
    expect(res.ok()).toBeTruthy();
  });

  test("DELETE /users/{rid} disables user", async ({ request }) => {
    const name = uniqueName("del");
    const createRes = await request.post(`${BACKEND}/setting/v1/users`, {
      headers,
      data: {
        email: `${name}@test.dev`,
        display_name: name,
        password: "Test1234!",
        role: "viewer",
      },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.delete(`${BACKEND}/setting/v1/users/${rid}`, { headers });
    expect(res.ok()).toBeTruthy();
  });
});
