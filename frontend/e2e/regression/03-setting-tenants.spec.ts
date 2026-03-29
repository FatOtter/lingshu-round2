/**
 * R03: Setting — Tenants, Members, Roles, Audit, Overview Regression
 * Covers: tenant CRUD, member management, role CRUD, audit logs, overview
 */
import { test, expect } from "@playwright/test";
import { BACKEND, getAuthHeaders, uniqueName, paginated } from "./helpers";

test.describe("R03: Tenants & Members", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("POST /tenants creates a tenant", async ({ request }) => {
    const name = uniqueName("tnt");
    const res = await request.post(`${BACKEND}/setting/v1/tenants`, {
      headers,
      data: { display_name: `Tenant ${name}` },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.data.rid).toMatch(/^ri\.tenant\./);
    expect(body.data.display_name).toBe(`Tenant ${name}`);
  });

  test("POST /tenants/query returns paginated tenants", async ({ request }) => {
    const res = await request.post(`${BACKEND}/setting/v1/tenants/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.pagination.total).toBeGreaterThanOrEqual(1);
    expect(Array.isArray(body.data)).toBeTruthy();
  });

  test("GET /tenants/{rid} returns details", async ({ request }) => {
    const queryRes = await request.post(`${BACKEND}/setting/v1/tenants/query`, {
      headers,
      data: paginated(),
    });
    const tenants = (await queryRes.json()).data;
    const rid = tenants[0].rid;

    const res = await request.get(`${BACKEND}/setting/v1/tenants/${rid}`, { headers });
    expect(res.ok()).toBeTruthy();
    expect((await res.json()).data.rid).toBe(rid);
  });

  test("PUT /tenants/{rid} updates tenant", async ({ request }) => {
    const name = uniqueName("tupd");
    const createRes = await request.post(`${BACKEND}/setting/v1/tenants`, {
      headers,
      data: { display_name: `Original ${name}` },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.put(`${BACKEND}/setting/v1/tenants/${rid}`, {
      headers,
      data: { display_name: `Updated ${name}` },
    });
    expect(res.ok()).toBeTruthy();
    expect((await res.json()).data.display_name).toBe(`Updated ${name}`);
  });

  test("DELETE /tenants/{rid} disables tenant", async ({ request }) => {
    const name = uniqueName("tdel");
    const createRes = await request.post(`${BACKEND}/setting/v1/tenants`, {
      headers,
      data: { display_name: name },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.delete(`${BACKEND}/setting/v1/tenants/${rid}`, { headers });
    expect(res.ok()).toBeTruthy();
  });

  test("POST /tenants/{rid}/members adds member", async ({ request }) => {
    const queryRes = await request.post(`${BACKEND}/setting/v1/tenants/query`, {
      headers,
      data: paginated(),
    });
    const tenantRid = (await queryRes.json()).data[0].rid;

    const userName = uniqueName("mbr");
    const userRes = await request.post(`${BACKEND}/setting/v1/users`, {
      headers,
      data: {
        email: `${userName}@test.dev`,
        display_name: userName,
        password: "Test1234!",
        role: "viewer",
      },
    });
    const userRid = (await userRes.json()).data.rid;

    const res = await request.post(
      `${BACKEND}/setting/v1/tenants/${tenantRid}/members`,
      { headers, data: { user_rid: userRid, role: "viewer" } },
    );
    expect(res.status()).toBe(201);
  });

  test("POST /tenants/{rid}/members/query returns paginated members", async ({ request }) => {
    const queryRes = await request.post(`${BACKEND}/setting/v1/tenants/query`, {
      headers,
      data: paginated(),
    });
    const tenantRid = (await queryRes.json()).data[0].rid;

    const res = await request.post(
      `${BACKEND}/setting/v1/tenants/${tenantRid}/members/query`,
      { headers, data: paginated() },
    );
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.pagination).toBeTruthy();
  });
});

test.describe("R03: Roles", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("POST /roles creates a role", async ({ request }) => {
    const name = uniqueName("role");
    const res = await request.post(`${BACKEND}/setting/v1/roles`, {
      headers,
      data: { name, display_name: `Role ${name}`, permissions: [{ resource_type: "ontology", action: "read" }] },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.data.name).toBe(name);
  });

  test("POST /roles/query returns paginated roles", async ({ request }) => {
    const res = await request.post(`${BACKEND}/setting/v1/roles/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.pagination).toBeTruthy();
  });

  test("GET /roles/{rid} returns role details", async ({ request }) => {
    const name = uniqueName("rget");
    const createRes = await request.post(`${BACKEND}/setting/v1/roles`, {
      headers,
      data: { name, display_name: name, permissions: [{ resource_type: "ontology", action: "read" }] },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.get(`${BACKEND}/setting/v1/roles/${rid}`, { headers });
    expect(res.ok()).toBeTruthy();
    expect((await res.json()).data.rid).toBe(rid);
  });

  test("PUT /roles/{rid} updates role", async ({ request }) => {
    const name = uniqueName("rupd");
    const createRes = await request.post(`${BACKEND}/setting/v1/roles`, {
      headers,
      data: { name, display_name: name, permissions: [{ resource_type: "ontology", action: "read" }] },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.put(`${BACKEND}/setting/v1/roles/${rid}`, {
      headers,
      data: { name: `updated_${name}`, description: "Updated description" },
    });
    expect(res.ok()).toBeTruthy();
  });

  test("DELETE /roles/{rid} removes role", async ({ request }) => {
    const name = uniqueName("rdel");
    const createRes = await request.post(`${BACKEND}/setting/v1/roles`, {
      headers,
      data: { name, display_name: name, permissions: [{ resource_type: "ontology", action: "read" }] },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.delete(`${BACKEND}/setting/v1/roles/${rid}`, { headers });
    expect(res.ok()).toBeTruthy();
  });
});

test.describe("R03: Audit Logs & Overview", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("POST /audit-logs/query returns paginated audit logs", async ({ request }) => {
    const res = await request.post(`${BACKEND}/setting/v1/audit-logs/query`, {
      headers,
      data: { ...paginated(), filters: [] },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.pagination).toBeTruthy();
    expect(Array.isArray(body.data)).toBeTruthy();
  });

  test("GET /overview returns setting statistics", async ({ request }) => {
    const res = await request.get(`${BACKEND}/setting/v1/overview`, { headers });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.data).toBeTruthy();
  });
});
