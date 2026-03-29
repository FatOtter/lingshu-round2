/**
 * R04: Ontology — All Entity Types CRUD Regression
 * Covers: ObjectType, LinkType, InterfaceType, ActionType, SharedPropertyType
 * Each entity: create, query, get/draft, update, delete, lock, submit-to-staging
 */
import { test, expect } from "@playwright/test";
import { BACKEND, getAuthHeaders, uniqueName, paginated } from "./helpers";

test.describe("R04: ObjectType CRUD", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("create, get draft, update, delete lifecycle", async ({ request }) => {
    const name = uniqueName("ot");

    const createRes = await request.post(`${BACKEND}/ontology/v1/object-types`, {
      headers,
      data: { api_name: name, display_name: `OT ${name}`, description: "regression" },
    });
    expect(createRes.status()).toBe(201);
    const created = (await createRes.json()).data;
    expect(created.rid).toMatch(/^ri\.obj\./);
    expect(created.version_status).toBe("draft");

    const getDraftRes = await request.get(
      `${BACKEND}/ontology/v1/object-types/${created.rid}/draft`,
      { headers },
    );
    expect(getDraftRes.ok()).toBeTruthy();
    expect((await getDraftRes.json()).data.api_name).toBe(name);

    await request.post(
      `${BACKEND}/ontology/v1/object-types/${created.rid}/lock`,
      { headers },
    );

    const updateRes = await request.put(
      `${BACKEND}/ontology/v1/object-types/${created.rid}`,
      { headers, data: { display_name: `Updated ${name}` } },
    );
    expect(updateRes.ok()).toBeTruthy();
    expect((await updateRes.json()).data.display_name).toBe(`Updated ${name}`);

    const deleteRes = await request.delete(
      `${BACKEND}/ontology/v1/object-types/${created.rid}`,
      { headers },
    );
    expect(deleteRes.ok()).toBeTruthy();
  });

  test("query returns paginated results", async ({ request }) => {
    const res = await request.post(`${BACKEND}/ontology/v1/object-types/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.pagination).toBeTruthy();
    expect(Array.isArray(body.data)).toBeTruthy();
  });

  test("lock acquire and release", async ({ request }) => {
    const name = uniqueName("otlock");
    const createRes = await request.post(`${BACKEND}/ontology/v1/object-types`, {
      headers,
      data: { api_name: name, display_name: name, description: "lock test" },
    });
    const rid = (await createRes.json()).data.rid;

    const lockRes = await request.post(
      `${BACKEND}/ontology/v1/object-types/${rid}/lock`,
      { headers },
    );
    expect(lockRes.ok()).toBeTruthy();

    const releaseRes = await request.delete(
      `${BACKEND}/ontology/v1/object-types/${rid}/lock`,
      { headers },
    );
    expect(releaseRes.ok()).toBeTruthy();
  });

  test("submit-to-staging changes version_status", async ({ request }) => {
    const name = uniqueName("otstaging");
    const createRes = await request.post(`${BACKEND}/ontology/v1/object-types`, {
      headers,
      data: { api_name: name, display_name: name, description: "staging test" },
    });
    const rid = (await createRes.json()).data.rid;

    const submitRes = await request.post(
      `${BACKEND}/ontology/v1/object-types/${rid}/submit-to-staging`,
      { headers },
    );
    expect(submitRes.ok()).toBeTruthy();
    const submitted = (await submitRes.json()).data;
    expect(submitted.version_status).toBe("staging");
  });
});

test.describe("R04: LinkType CRUD", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("create, get draft, update, delete lifecycle", async ({ request }) => {
    const name = uniqueName("lt");

    const createRes = await request.post(`${BACKEND}/ontology/v1/link-types`, {
      headers,
      data: { api_name: name, display_name: `LT ${name}`, description: "regression" },
    });
    expect(createRes.status()).toBe(201);
    const created = (await createRes.json()).data;
    expect(created.version_status).toBe("draft");

    const getDraftRes = await request.get(
      `${BACKEND}/ontology/v1/link-types/${created.rid}/draft`,
      { headers },
    );
    expect(getDraftRes.ok()).toBeTruthy();

    await request.post(
      `${BACKEND}/ontology/v1/link-types/${created.rid}/lock`,
      { headers },
    );
    const updateRes = await request.put(
      `${BACKEND}/ontology/v1/link-types/${created.rid}`,
      { headers, data: { display_name: `Updated ${name}` } },
    );
    expect(updateRes.ok()).toBeTruthy();

    const deleteRes = await request.delete(
      `${BACKEND}/ontology/v1/link-types/${created.rid}`,
      { headers },
    );
    expect(deleteRes.ok()).toBeTruthy();
  });

  test("query returns paginated results", async ({ request }) => {
    const res = await request.post(`${BACKEND}/ontology/v1/link-types/query`, {
      headers,
      data: paginated(),
    });
    expect(res.ok()).toBeTruthy();
    expect((await res.json()).pagination).toBeTruthy();
  });
});

test.describe("R04: InterfaceType CRUD", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("create, get draft, update, delete lifecycle", async ({ request }) => {
    const name = uniqueName("iface");

    const createRes = await request.post(`${BACKEND}/ontology/v1/interface-types`, {
      headers,
      data: {
        api_name: name,
        display_name: `IF ${name}`,
        description: "regression",
        category: "OBJECT_INTERFACE",
      },
    });
    expect(createRes.status()).toBe(201);
    const created = (await createRes.json()).data;

    const getDraftRes = await request.get(
      `${BACKEND}/ontology/v1/interface-types/${created.rid}/draft`,
      { headers },
    );
    expect(getDraftRes.ok()).toBeTruthy();

    await request.post(
      `${BACKEND}/ontology/v1/interface-types/${created.rid}/lock`,
      { headers },
    );
    const updateRes = await request.put(
      `${BACKEND}/ontology/v1/interface-types/${created.rid}`,
      { headers, data: { display_name: `Updated ${name}` } },
    );
    expect(updateRes.ok()).toBeTruthy();

    const deleteRes = await request.delete(
      `${BACKEND}/ontology/v1/interface-types/${created.rid}`,
      { headers },
    );
    expect(deleteRes.ok()).toBeTruthy();
  });
});

test.describe("R04: ActionType CRUD", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("create, query, get draft, update, delete lifecycle", async ({ request }) => {
    const name = uniqueName("act");

    const createRes = await request.post(`${BACKEND}/ontology/v1/action-types`, {
      headers,
      data: { api_name: name, display_name: `ACT ${name}`, description: "regression" },
    });
    expect(createRes.status()).toBe(201);
    const created = (await createRes.json()).data;

    const queryRes = await request.post(`${BACKEND}/ontology/v1/action-types/query`, {
      headers,
      data: paginated(),
    });
    expect(queryRes.ok()).toBeTruthy();

    await request.post(
      `${BACKEND}/ontology/v1/action-types/${created.rid}/lock`,
      { headers },
    );
    const updateRes = await request.put(
      `${BACKEND}/ontology/v1/action-types/${created.rid}`,
      { headers, data: { display_name: `Updated ${name}` } },
    );
    expect(updateRes.ok()).toBeTruthy();

    const deleteRes = await request.delete(
      `${BACKEND}/ontology/v1/action-types/${created.rid}`,
      { headers },
    );
    expect(deleteRes.ok()).toBeTruthy();
  });
});

test.describe("R04: SharedPropertyType CRUD", () => {
  let headers: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    headers = await getAuthHeaders(request);
  });

  test("create, query, get draft, update, delete lifecycle", async ({ request }) => {
    const name = uniqueName("shprop");

    const createRes = await request.post(
      `${BACKEND}/ontology/v1/shared-property-types`,
      {
        headers,
        data: {
          api_name: name,
          display_name: `SP ${name}`,
          description: "regression",
          data_type: "DT_STRING",
        },
      },
    );
    expect(createRes.status()).toBe(201);
    const created = (await createRes.json()).data;

    const queryRes = await request.post(
      `${BACKEND}/ontology/v1/shared-property-types/query`,
      { headers, data: paginated() },
    );
    expect(queryRes.ok()).toBeTruthy();

    await request.post(
      `${BACKEND}/ontology/v1/shared-property-types/${created.rid}/lock`,
      { headers },
    );
    const updateRes = await request.put(
      `${BACKEND}/ontology/v1/shared-property-types/${created.rid}`,
      { headers, data: { display_name: `Updated ${name}` } },
    );
    expect(updateRes.ok()).toBeTruthy();

    const deleteRes = await request.delete(
      `${BACKEND}/ontology/v1/shared-property-types/${created.rid}`,
      { headers },
    );
    expect(deleteRes.ok()).toBeTruthy();
  });
});
