/**
 * R07: Function Module — Global Functions, Capabilities, Workflows, Executions
 * Covers: function CRUD, capability query, workflow CRUD, execution query, overview
 */
import { test, expect } from "@playwright/test";
import { BACKEND, getAuthHeaders, uniqueName, paginated } from "./helpers";

test.describe("R07: Global Functions", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("POST /functions creates a global function", async ({ request }) => {
    const name = uniqueName("gfn");
    const res = await request.post(`${BACKEND}/function/v1/functions`, {
      headers,
      data: {
        name,
        display_name: `Func ${name}`,
        description: "regression",
        engine: "python",
        code: "def run(params): return {'result': 'ok'}",
      },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.data.rid).toMatch(/^ri\.func\./);
  });

  test("POST /functions/query returns paginated functions", async ({ request }) => {
    const res = await request.post(`${BACKEND}/function/v1/functions/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.pagination).toBeTruthy();
  });

  test("GET /functions/{rid} returns details", async ({ request }) => {
    const name = uniqueName("fget");
    const createRes = await request.post(`${BACKEND}/function/v1/functions`, {
      headers,
      data: {
        name,
        display_name: name,
        description: "get test",
        engine: "python",
        code: "def run(params): return {}",
      },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.get(`${BACKEND}/function/v1/functions/${rid}`, { headers });
    expect(res.ok()).toBeTruthy();
  });

  test("PUT /functions/{rid} updates function", async ({ request }) => {
    const name = uniqueName("fupd");
    const createRes = await request.post(`${BACKEND}/function/v1/functions`, {
      headers,
      data: {
        name,
        display_name: name,
        description: "update",
        engine: "python",
        code: "def run(params): return {}",
      },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.put(`${BACKEND}/function/v1/functions/${rid}`, {
      headers,
      data: { display_name: `Updated ${name}` },
    });
    expect(res.ok()).toBeTruthy();
  });

  test("DELETE /functions/{rid} removes function", async ({ request }) => {
    const name = uniqueName("fdel");
    const createRes = await request.post(`${BACKEND}/function/v1/functions`, {
      headers,
      data: {
        name,
        display_name: name,
        description: "delete",
        engine: "python",
        code: "def run(params): return {}",
      },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.delete(`${BACKEND}/function/v1/functions/${rid}`, { headers });
    expect(res.ok()).toBeTruthy();
  });
});

test.describe("R07: Capabilities & Executions", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("POST /capabilities/query returns capability list (no pagination)", async ({
    request,
  }) => {
    const res = await request.post(`${BACKEND}/function/v1/capabilities/query`, {
      headers,
      data: {},
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body.data)).toBeTruthy();
  });

  test("POST /capabilities/query with type filter", async ({ request }) => {
    const res = await request.post(`${BACKEND}/function/v1/capabilities/query`, {
      headers,
      data: { capability_type: "action" },
    });
    expect(res.ok()).toBeTruthy();
  });

  test("POST /capabilities/query with function type filter", async ({ request }) => {
    const res = await request.post(`${BACKEND}/function/v1/capabilities/query`, {
      headers,
      data: { capability_type: "function" },
    });
    expect(res.ok()).toBeTruthy();
  });

  test("POST /executions/query returns paginated executions", async ({ request }) => {
    const res = await request.post(`${BACKEND}/function/v1/executions/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.pagination).toBeTruthy();
  });

  test("GET /overview returns function statistics", async ({ request }) => {
    const res = await request.get(`${BACKEND}/function/v1/overview`, { headers });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.data).toBeTruthy();
  });
});

test.describe("R07: Workflows", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("POST /workflows creates a workflow", async ({ request }) => {
    const name = uniqueName("wf");
    const res = await request.post(`${BACKEND}/function/v1/workflows`, {
      headers,
      data: {
        name,
        display_name: `WF ${name}`,
        description: "regression",
        definition: {
          nodes: [
            { id: "start", type: "start", label: "Start" },
            { id: "end", type: "end", label: "End" },
          ],
          edges: [{ source: "start", target: "end" }],
        },
      },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.data.rid).toMatch(/^ri\.workflow\./);
  });

  test("POST /workflows/query returns paginated workflows", async ({ request }) => {
    const res = await request.post(`${BACKEND}/function/v1/workflows/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.pagination).toBeTruthy();
  });

  test("GET /workflows/{rid} returns details", async ({ request }) => {
    const name = uniqueName("wget");
    const createRes = await request.post(`${BACKEND}/function/v1/workflows`, {
      headers,
      data: {
        name,
        display_name: name,
        description: "get",
        definition: {
          nodes: [{ id: "s", type: "start", label: "S" }],
          edges: [],
        },
      },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.get(`${BACKEND}/function/v1/workflows/${rid}`, { headers });
    expect(res.ok()).toBeTruthy();
  });

  test("PUT /workflows/{rid} updates workflow", async ({ request }) => {
    const name = uniqueName("wupd");
    const createRes = await request.post(`${BACKEND}/function/v1/workflows`, {
      headers,
      data: {
        name,
        display_name: name,
        description: "update",
        definition: {
          nodes: [{ id: "s", type: "start", label: "S" }],
          edges: [],
        },
      },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.put(`${BACKEND}/function/v1/workflows/${rid}`, {
      headers,
      data: { display_name: `Updated ${name}` },
    });
    expect(res.ok()).toBeTruthy();
  });

  test("DELETE /workflows/{rid} removes workflow", async ({ request }) => {
    const name = uniqueName("wdel");
    const createRes = await request.post(`${BACKEND}/function/v1/workflows`, {
      headers,
      data: {
        name,
        display_name: name,
        description: "delete",
        definition: {
          nodes: [{ id: "s", type: "start", label: "S" }],
          edges: [],
        },
      },
    });
    const rid = (await createRes.json()).data.rid;

    const res = await request.delete(`${BACKEND}/function/v1/workflows/${rid}`, { headers });
    expect(res.ok()).toBeTruthy();
  });
});
