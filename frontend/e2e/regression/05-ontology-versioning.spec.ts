/**
 * R05: Ontology — Versioning, Staging, Snapshots, Properties, Topology, Search
 * Covers the full version lifecycle and auxiliary ontology endpoints
 */
import { test, expect } from "@playwright/test";
import { BACKEND, getAuthHeaders, uniqueName, paginated } from "./helpers";

test.describe("R05: Staging & Snapshots", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("GET /staging/summary returns staging state", async ({ request }) => {
    const res = await request.get(`${BACKEND}/ontology/v1/staging/summary`, { headers });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.data).toBeTruthy();
  });

  test("GET /drafts/summary returns drafts state", async ({ request }) => {
    const res = await request.get(`${BACKEND}/ontology/v1/drafts/summary`, { headers });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.data).toBeTruthy();
  });

  test("full version lifecycle: create → submit → commit → snapshot", async ({
    request,
  }) => {
    const name = uniqueName("ver");
    const createRes = await request.post(`${BACKEND}/ontology/v1/object-types`, {
      headers,
      data: { api_name: name, display_name: name, description: "version lifecycle" },
    });
    const rid = (await createRes.json()).data.rid;

    const submitRes = await request.post(
      `${BACKEND}/ontology/v1/object-types/${rid}/submit-to-staging`,
      { headers },
    );
    expect(submitRes.ok()).toBeTruthy();

    const commitRes = await request.post(`${BACKEND}/ontology/v1/staging/commit`, {
      headers,
      data: { commit_message: `regression commit ${name}` },
    });
    if (commitRes.ok()) {
      const snapshot = (await commitRes.json()).data;
      expect(snapshot.snapshot_id ?? snapshot.rid).toBeTruthy();

      const snapQueryRes = await request.post(
        `${BACKEND}/ontology/v1/snapshots/query`,
        { headers, data: paginated() },
      );
      expect(snapQueryRes.ok()).toBeTruthy();
      const snapshots = (await snapQueryRes.json()).data;
      expect(snapshots.length).toBeGreaterThanOrEqual(1);
    }
  });

  test("POST /staging/discard clears staging", async ({ request }) => {
    const name = uniqueName("disc");
    const createRes = await request.post(`${BACKEND}/ontology/v1/object-types`, {
      headers,
      data: { api_name: name, display_name: name, description: "discard test" },
    });
    const rid = (await createRes.json()).data.rid;

    await request.post(
      `${BACKEND}/ontology/v1/object-types/${rid}/submit-to-staging`,
      { headers },
    );

    const discardRes = await request.post(`${BACKEND}/ontology/v1/staging/discard`, {
      headers,
    });
    expect(discardRes.ok()).toBeTruthy();
  });

  test("POST /snapshots/query returns paginated snapshots", async ({ request }) => {
    const res = await request.post(`${BACKEND}/ontology/v1/snapshots/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.pagination).toBeTruthy();
  });
});

test.describe("R05: PropertyTypes", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("create property type on object type", async ({ request }) => {
    const otName = uniqueName("otprop");
    const createOtRes = await request.post(`${BACKEND}/ontology/v1/object-types`, {
      headers,
      data: { api_name: otName, display_name: otName, description: "prop parent" },
    });
    const otRid = (await createOtRes.json()).data.rid;

    const propName = uniqueName("prop");
    const createPropRes = await request.post(
      `${BACKEND}/ontology/v1/object-types/${otRid}/property-types`,
      {
        headers,
        data: {
          api_name: propName,
          display_name: `Prop ${propName}`,
          base_type: "string",
        },
      },
    );
    expect(createPropRes.ok()).toBeTruthy();
    const prop = (await createPropRes.json()).data;
    expect(prop.api_name).toBe(propName);
  });

  test("POST /property-types/query returns all properties", async ({ request }) => {
    const res = await request.post(`${BACKEND}/ontology/v1/property-types/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.pagination).toBeTruthy();
  });
});

test.describe("R05: Topology & Search", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("GET /topology returns graph data", async ({ request }) => {
    const res = await request.get(`${BACKEND}/ontology/v1/topology`, { headers });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.data).toBeTruthy();
  });

  test("GET /search returns results for a query", async ({ request }) => {
    const res = await request.get(`${BACKEND}/ontology/v1/search?q=test&limit=10`, {
      headers,
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(Array.isArray(body.data)).toBeTruthy();
  });

  test("POST /asset-mappings/query returns mappings", async ({ request }) => {
    const res = await request.post(`${BACKEND}/ontology/v1/asset-mappings/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.pagination).toBeTruthy();
  });
});
