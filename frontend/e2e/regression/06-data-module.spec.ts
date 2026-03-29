/**
 * R06: Data Module — Connections, Instances, Branches, Overview
 * Covers: connection CRUD + test, instance query, branch operations, overview
 */
import { test, expect } from "@playwright/test";
import { BACKEND, getAuthHeaders, uniqueName, paginated } from "./helpers";

test.describe("R06: Data Connections", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("POST /connections creates a connection", async ({ request }) => {
    const name = uniqueName("conn");
    const res = await request.post(`${BACKEND}/data/v1/connections`, {
      headers,
      data: {
        name,
        display_name: `Connection ${name}`,
        connector_type: "postgresql",
        config: {
          host: "localhost",
          port: 5432,
          database: "test",
          username: "test",
          password: "test",
        },
      },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.data.rid).toMatch(/^ri\.conn\./);
    expect(body.data.name).toBe(name);
  });

  test("POST /connections/query returns paginated connections", async ({ request }) => {
    const res = await request.post(`${BACKEND}/data/v1/connections/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.pagination).toBeTruthy();
    expect(Array.isArray(body.data)).toBeTruthy();
  });

  test("GET /connections/{rid} returns details", async ({ request }) => {
    const name = uniqueName("cget");
    const createRes = await request.post(`${BACKEND}/data/v1/connections`, {
      headers,
      data: {
        name,
        display_name: name,
        connector_type: "postgresql",
        config: { host: "localhost", port: 5432, database: "t", username: "t", password: "t" },
      },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.get(`${BACKEND}/data/v1/connections/${rid}`, { headers });
    expect(res.ok()).toBeTruthy();
    expect((await res.json()).data.rid).toBe(rid);
  });

  test("PUT /connections/{rid} updates connection", async ({ request }) => {
    const name = uniqueName("cupd");
    const createRes = await request.post(`${BACKEND}/data/v1/connections`, {
      headers,
      data: {
        name,
        display_name: name,
        connector_type: "postgresql",
        config: { host: "localhost", port: 5432, database: "t", username: "t", password: "t" },
      },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.put(`${BACKEND}/data/v1/connections/${rid}`, {
      headers,
      data: { display_name: `Updated ${name}` },
    });
    expect(res.ok()).toBeTruthy();
  });

  test("DELETE /connections/{rid} removes connection", async ({ request }) => {
    const name = uniqueName("cdel");
    const createRes = await request.post(`${BACKEND}/data/v1/connections`, {
      headers,
      data: {
        name,
        display_name: name,
        connector_type: "postgresql",
        config: { host: "localhost", port: 5432, database: "t", username: "t", password: "t" },
      },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.delete(`${BACKEND}/data/v1/connections/${rid}`, { headers });
    expect(res.ok()).toBeTruthy();
  });

  test("POST /connections/{rid}/test tests connection", async ({ request }) => {
    const name = uniqueName("ctest");
    const createRes = await request.post(`${BACKEND}/data/v1/connections`, {
      headers,
      data: {
        name,
        display_name: name,
        connector_type: "postgresql",
        config: { host: "localhost", port: 5432, database: "t", username: "t", password: "t" },
      },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.post(`${BACKEND}/data/v1/connections/${rid}/test`, {
      headers,
    });
    const body = await res.json();
    expect(body.data).toBeTruthy();
  });
});

test.describe("R06: Data Overview & Branches", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("GET /overview returns data statistics", async ({ request }) => {
    const res = await request.get(`${BACKEND}/data/v1/overview`, { headers });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.data).toBeTruthy();
  });

  test("GET /branches returns branch list (or unavailable)", async ({ request }) => {
    const res = await request.get(`${BACKEND}/data/v1/branches`, { headers });
    const body = await res.json();
    if (res.ok()) {
      expect(Array.isArray(body.data)).toBeTruthy();
    } else {
      expect(body.error.code).toBe("DATA_BRANCH_UNAVAILABLE");
    }
  });
});
