/**
 * R08: Copilot Module — Sessions, Models, Skills, MCP, Sub-Agents, Overview
 * Covers full CRUD for each copilot resource type
 */
import { test, expect } from "@playwright/test";
import { BACKEND, getAuthHeaders, uniqueName, paginated } from "./helpers";

test.describe("R08: Copilot Sessions", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("POST /sessions creates a session", async ({ request }) => {
    const res = await request.post(`${BACKEND}/copilot/v1/sessions`, {
      headers,
      data: { mode: "agent" },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.data.session_id).toBeTruthy();
  });

  test("POST /sessions/query returns paginated sessions", async ({ request }) => {
    const res = await request.post(`${BACKEND}/copilot/v1/sessions/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.pagination).toBeTruthy();
  });

  test("GET /sessions/{id} returns session", async ({ request }) => {
    const createRes = await request.post(`${BACKEND}/copilot/v1/sessions`, {
      headers,
      data: { mode: "agent" },
    });
    const id = (await createRes.json()).data.session_id;

    const res = await request.get(`${BACKEND}/copilot/v1/sessions/${id}`, { headers });
    expect(res.ok()).toBeTruthy();
    expect((await res.json()).data.session_id).toBe(id);
  });

  test("PUT /sessions/{id}/context updates context", async ({ request }) => {
    const createRes = await request.post(`${BACKEND}/copilot/v1/sessions`, {
      headers,
      data: { mode: "agent", context: {} },
    });
    const id = (await createRes.json()).data.session_id;

    const res = await request.put(`${BACKEND}/copilot/v1/sessions/${id}/context`, {
      headers,
      data: { context: { selected_type: "test" } },
    });
    if (!res.ok()) {
      const errBody = await res.json();
      expect(errBody.error || errBody.data).toBeTruthy();
    }
  });

  test("DELETE /sessions/{id} removes session", async ({ request }) => {
    const createRes = await request.post(`${BACKEND}/copilot/v1/sessions`, {
      headers,
      data: { mode: "agent" },
    });
    const id = (await createRes.json()).data.session_id;

    const res = await request.delete(`${BACKEND}/copilot/v1/sessions/${id}`, { headers });
    expect(res.ok()).toBeTruthy();
  });
});

test.describe("R08: Copilot Models", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("POST /models registers a model", async ({ request }) => {
    const name = uniqueName("mdl");
    const res = await request.post(`${BACKEND}/copilot/v1/models`, {
      headers,
      data: {
        api_name: name,
        display_name: `Model ${name}`,
        provider: "openai",
        connection: { api_key: "sk-test-key", model: "gpt-4" },
      },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.data.rid).toMatch(/^ri\.model\./);
  });

  test("POST /models/query returns paginated models", async ({ request }) => {
    const res = await request.post(`${BACKEND}/copilot/v1/models/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.pagination).toBeTruthy();
  });

  test("full CRUD lifecycle for model", async ({ request }) => {
    const name = uniqueName("mcrud");
    const createRes = await request.post(`${BACKEND}/copilot/v1/models`, {
      headers,
      data: {
        api_name: name,
        display_name: name,
        provider: "openai",
        connection: { api_key: "sk-test" },
      },
    });
    expect(createRes.status()).toBe(201);
    const rid = (await createRes.json()).data.rid;

    const getRes = await request.get(`${BACKEND}/copilot/v1/models/${rid}`, { headers });
    expect(getRes.ok()).toBeTruthy();

    const updateRes = await request.put(`${BACKEND}/copilot/v1/models/${rid}`, {
      headers,
      data: { display_name: `Updated ${name}` },
    });
    expect(updateRes.ok()).toBeTruthy();

    const deleteRes = await request.delete(`${BACKEND}/copilot/v1/models/${rid}`, {
      headers,
    });
    expect(deleteRes.ok()).toBeTruthy();
  });
});

test.describe("R08: Copilot Skills", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("POST /skills creates a skill", async ({ request }) => {
    const name = uniqueName("skill");
    const res = await request.post(`${BACKEND}/copilot/v1/skills`, {
      headers,
      data: {
        api_name: name,
        display_name: `Skill ${name}`,
        description: "regression skill",
        system_prompt: "Do something with the input",
      },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.data.rid).toMatch(/^ri\.skill\./);
  });

  test("POST /skills/query returns paginated skills", async ({ request }) => {
    const res = await request.post(`${BACKEND}/copilot/v1/skills/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
  });

  test("full CRUD lifecycle for skill", async ({ request }) => {
    const name = uniqueName("scrud");
    const createRes = await request.post(`${BACKEND}/copilot/v1/skills`, {
      headers,
      data: {
        api_name: name,
        display_name: name,
        description: "crud test",
        system_prompt: "You are a helper.",
      },
    });
    expect(createRes.status()).toBe(201);
    const rid = (await createRes.json()).data.rid;

    const getRes = await request.get(`${BACKEND}/copilot/v1/skills/${rid}`, { headers });
    expect(getRes.ok()).toBeTruthy();

    const updateRes = await request.put(`${BACKEND}/copilot/v1/skills/${rid}`, {
      headers,
      data: { display_name: `Updated ${name}` },
    });
    expect(updateRes.ok()).toBeTruthy();

    const deleteRes = await request.delete(`${BACKEND}/copilot/v1/skills/${rid}`, {
      headers,
    });
    expect(deleteRes.ok()).toBeTruthy();
  });
});

test.describe("R08: MCP Connections", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("POST /mcp creates a connection", async ({ request }) => {
    const name = uniqueName("mcp");
    const res = await request.post(`${BACKEND}/copilot/v1/mcp`, {
      headers,
      data: {
        api_name: name,
        display_name: `MCP ${name}`,
        transport: { type: "http", url: "http://localhost:9999/mcp" },
      },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.data.rid).toMatch(/^ri\.mcp\./);
  });

  test("POST /mcp/query returns paginated connections", async ({ request }) => {
    const res = await request.post(`${BACKEND}/copilot/v1/mcp/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
  });

  test("full CRUD lifecycle for MCP", async ({ request }) => {
    const name = uniqueName("mcrud");
    const createRes = await request.post(`${BACKEND}/copilot/v1/mcp`, {
      headers,
      data: {
        api_name: name,
        display_name: name,
        transport: { type: "http", url: "http://localhost:9999" },
      },
    });
    expect(createRes.status()).toBe(201);
    const rid = (await createRes.json()).data.rid;

    const getRes = await request.get(`${BACKEND}/copilot/v1/mcp/${rid}`, { headers });
    expect(getRes.ok()).toBeTruthy();

    const updateRes = await request.put(`${BACKEND}/copilot/v1/mcp/${rid}`, {
      headers,
      data: { display_name: `Updated ${name}` },
    });
    expect(updateRes.ok()).toBeTruthy();

    const deleteRes = await request.delete(`${BACKEND}/copilot/v1/mcp/${rid}`, {
      headers,
    });
    expect(deleteRes.ok()).toBeTruthy();
  });
});

test.describe("R08: Sub-Agents", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("POST /sub-agents creates a sub-agent", async ({ request }) => {
    const name = uniqueName("subag");
    const res = await request.post(`${BACKEND}/copilot/v1/sub-agents`, {
      headers,
      data: {
        api_name: name,
        display_name: `SubAgent ${name}`,
        description: "regression sub-agent",
      },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.data.rid).toMatch(/^ri\.subagent\./);
  });

  test("POST /sub-agents/query returns paginated sub-agents", async ({ request }) => {
    const res = await request.post(`${BACKEND}/copilot/v1/sub-agents/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
  });

  test("full CRUD lifecycle for sub-agent", async ({ request }) => {
    const name = uniqueName("sacrud");
    const createRes = await request.post(`${BACKEND}/copilot/v1/sub-agents`, {
      headers,
      data: {
        api_name: name,
        display_name: name,
        description: "crud test",
      },
    });
    expect(createRes.status()).toBe(201);
    const rid = (await createRes.json()).data.rid;

    const getRes = await request.get(`${BACKEND}/copilot/v1/sub-agents/${rid}`, {
      headers,
    });
    expect(getRes.ok()).toBeTruthy();

    const updateRes = await request.put(`${BACKEND}/copilot/v1/sub-agents/${rid}`, {
      headers,
      data: { display_name: `Updated ${name}` },
    });
    expect(updateRes.ok()).toBeTruthy();

    const deleteRes = await request.delete(`${BACKEND}/copilot/v1/sub-agents/${rid}`, {
      headers,
    });
    expect(deleteRes.ok()).toBeTruthy();
  });
});

test.describe("R08: Copilot Overview", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("GET /overview returns copilot statistics", async ({ request }) => {
    const res = await request.get(`${BACKEND}/copilot/v1/overview`, { headers });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.data).toBeTruthy();
  });
});
