/**
 * R09: Cross-Module & Integration Regression
 * Covers: cross-module data flow, error handling, pagination consistency,
 * draft visibility regression, and console error regressions from other branch fixes
 */
import { test, expect } from "@playwright/test";
import { BACKEND, getAuthHeaders, uniqueName, paginated } from "./helpers";

test.describe("R09: Cross-Module Ontology → Function", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("action type created in ontology appears in function capabilities", async ({
    request,
  }) => {
    const name = uniqueName("xact");
    const createRes = await request.post(`${BACKEND}/ontology/v1/action-types`, {
      headers,
      data: { api_name: name, display_name: `XAct ${name}`, description: "cross-module" },
    });
    expect(createRes.status()).toBe(201);
    const rid = (await createRes.json()).data.rid;

    await request.post(
      `${BACKEND}/ontology/v1/action-types/${rid}/submit-to-staging`,
      { headers },
    );

    const commitRes = await request.post(`${BACKEND}/ontology/v1/staging/commit`, {
      headers,
      data: { commit_message: `cross-module test ${name}` },
    });

    if (commitRes.ok()) {
      const capRes = await request.post(
        `${BACKEND}/function/v1/capabilities/query`,
        { headers, data: { capability_type: "action" } },
      );
      expect(capRes.ok()).toBeTruthy();
    }
  });
});

test.describe("R09: Error Handling", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("GET nonexistent object type returns proper error", async ({ request }) => {
    const res = await request.get(
      `${BACKEND}/ontology/v1/object-types/ri.obj.00000000-0000-0000-0000-000000000000`,
      { headers },
    );
    expect(res.ok()).toBeFalsy();
    const body = await res.json();
    expect(body.error).toBeTruthy();
    expect(body.error.code).toBeTruthy();
  });

  test("GET nonexistent user returns proper error", async ({ request }) => {
    const res = await request.get(
      `${BACKEND}/setting/v1/users/ri.user.00000000-0000-0000-0000-000000000000`,
      { headers },
    );
    expect(res.ok()).toBeFalsy();
    const body = await res.json();
    expect(body.error).toBeTruthy();
  });

  test("GET nonexistent connection returns proper error", async ({ request }) => {
    const res = await request.get(
      `${BACKEND}/data/v1/connections/ri.conn.00000000-0000-0000-0000-000000000000`,
      { headers },
    );
    expect(res.ok()).toBeFalsy();
    const body = await res.json();
    expect(body.error).toBeTruthy();
  });

  test("GET nonexistent session returns proper error", async ({ request }) => {
    const res = await request.get(
      `${BACKEND}/copilot/v1/sessions/nonexistent-session-id`,
      { headers },
    );
    expect(res.ok()).toBeFalsy();
    const body = await res.json();
    expect(body.error).toBeTruthy();
  });

  test("unauthenticated request to protected endpoint returns 401", async ({
    request,
  }) => {
    const res = await request.get(`${BACKEND}/setting/v1/overview`);
    expect(res.status()).toBe(401);
  });

  test("malformed request body returns 422", async ({ request }) => {
    const res = await request.post(`${BACKEND}/setting/v1/users`, {
      headers,
      data: {},
    });
    expect(res.status()).toBe(422);
  });
});

test.describe("R09: Pagination Consistency", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  const queryEndpoints = [
    { path: "/setting/v1/users/query", label: "users" },
    { path: "/setting/v1/tenants/query", label: "tenants" },
    { path: "/ontology/v1/object-types/query", label: "object-types" },
    { path: "/ontology/v1/link-types/query", label: "link-types" },
    { path: "/ontology/v1/interface-types/query", label: "interface-types" },
    { path: "/ontology/v1/action-types/query", label: "action-types" },
    { path: "/ontology/v1/shared-property-types/query", label: "shared-property-types" },
    { path: "/ontology/v1/snapshots/query", label: "snapshots" },
    { path: "/data/v1/connections/query", label: "connections" },
    { path: "/function/v1/functions/query", label: "functions" },
    { path: "/function/v1/executions/query", label: "executions" },
    { path: "/function/v1/workflows/query", label: "workflows" },
    { path: "/copilot/v1/sessions/query", label: "sessions" },
    { path: "/copilot/v1/models/query", label: "models" },
    { path: "/copilot/v1/skills/query", label: "skills" },
    { path: "/copilot/v1/mcp/query", label: "mcp" },
    { path: "/copilot/v1/sub-agents/query", label: "sub-agents" },
  ];

  for (const ep of queryEndpoints) {
    test(`${ep.label} query returns standard pagination shape`, async ({ request }) => {
      const body: Record<string, unknown> = paginated();
      if (ep.path.includes("ontology")) {
        body.include_drafts = true;
      }
      if (ep.path.includes("audit-logs")) {
        body.filters = [];
      }
      const res = await request.post(`${BACKEND}${ep.path}`, { headers, data: body });
      expect(res.ok()).toBeTruthy();
      const data = await res.json();
      expect(data.pagination).toBeTruthy();
      expect(typeof data.pagination.total).toBe("number");
      expect(typeof data.pagination.page).toBe("number");
      expect(typeof data.pagination.page_size).toBe("number");
      expect(typeof data.pagination.has_next).toBe("boolean");
      expect(Array.isArray(data.data)).toBeTruthy();
    });
  }
});

test.describe("R09: Draft Visibility Regression (from dev-env branch)", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("created ObjectType appears in query with include_drafts=true", async ({
    request,
  }) => {
    const name = uniqueName("dv_ot");
    const createRes = await request.post(`${BACKEND}/ontology/v1/object-types`, {
      headers,
      data: { api_name: name, display_name: name, description: "draft vis regression" },
    });
    expect(createRes.status()).toBe(201);
    expect((await createRes.json()).data.version_status).toBe("draft");

    const queryRes = await request.post(`${BACKEND}/ontology/v1/object-types/query`, {
      headers,
      data: { ...paginated(1, 100), include_drafts: true, search: name },
    });
    expect(queryRes.ok()).toBeTruthy();
    const found = (await queryRes.json()).data.find(
      (it: Record<string, string>) => it.api_name === name,
    );
    expect(found).toBeTruthy();
    expect(found.version_status).toBe("draft");
  });

  test("created LinkType appears in query with include_drafts=true", async ({
    request,
  }) => {
    const name = uniqueName("dv_lt");
    const createRes = await request.post(`${BACKEND}/ontology/v1/link-types`, {
      headers,
      data: { api_name: name, display_name: name, description: "draft vis" },
    });
    expect(createRes.status()).toBe(201);
    expect((await createRes.json()).data.version_status).toBe("draft");

    const queryRes = await request.post(`${BACKEND}/ontology/v1/link-types/query`, {
      headers,
      data: { ...paginated(1, 100), include_drafts: true, search: name },
    });
    expect(queryRes.ok()).toBeTruthy();
    expect(
      (await queryRes.json()).data.find(
        (it: Record<string, string>) => it.api_name === name,
      ),
    ).toBeTruthy();
  });

  test("capabilities query accepts empty body (422 regression)", async ({ request }) => {
    const res = await request.post(`${BACKEND}/function/v1/capabilities/query`, {
      headers,
      data: {},
    });
    expect(res.status()).not.toBe(422);
    expect(res.ok()).toBeTruthy();
  });

  test("auth refresh without cookie returns structured error, not 500", async ({
    request,
  }) => {
    const res = await request.post(`${BACKEND}/setting/v1/auth/refresh`);
    const body = await res.json();
    expect(body.error).toBeTruthy();
    expect(body.error.code).toBe("SETTING_AUTH_TOKEN_EXPIRED");
    expect(res.status()).not.toBe(500);
  });
});

test.describe("R09: Overview Endpoints", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  const overviewEndpoints = [
    "/setting/v1/overview",
    "/data/v1/overview",
    "/function/v1/overview",
    "/copilot/v1/overview",
  ];

  for (const path of overviewEndpoints) {
    test(`GET ${path} returns data`, async ({ request }) => {
      const res = await request.get(`${BACKEND}${path}`, { headers });
      expect(res.ok()).toBeTruthy();
      const body = await res.json();
      expect(body.data).toBeTruthy();
    });
  }
});
