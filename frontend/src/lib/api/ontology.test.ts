import { describe, it, expect, vi, beforeEach } from "vitest";
import { ontologyApi } from "./ontology";
import { apiClient } from "./client";

vi.mock("./client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ontologyApi", () => {
  describe("ObjectType CRUD", () => {
    it("queryObjectTypes posts to correct URL with params", async () => {
      const mockResponse = { data: [], pagination: { total: 0 } };
      vi.mocked(apiClient.post).mockResolvedValue(mockResponse);

      const params = { offset: 0, limit: 10, branch: "dev" };
      const result = await ontologyApi.queryObjectTypes(params);

      expect(apiClient.post).toHaveBeenCalledWith("/ontology/v1/object-types/query", {
        pagination: { page: 1, page_size: 10 },
        include_drafts: true,
      });
      expect(result).toEqual(mockResponse);
    });

    it("queryObjectTypes works without params", async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: [] });

      await ontologyApi.queryObjectTypes();

      expect(apiClient.post).toHaveBeenCalledWith("/ontology/v1/object-types/query", {
        pagination: { page: 1, page_size: 20 },
        include_drafts: true,
      });
    });

    it("getObjectType fetches by rid", async () => {
      const mockOt = { data: { rid: "ri.obj.1", api_name: "Employee" } };
      vi.mocked(apiClient.get).mockResolvedValue(mockOt);

      const result = await ontologyApi.getObjectType("ri.obj.1");

      expect(apiClient.get).toHaveBeenCalledWith("/ontology/v1/object-types/ri.obj.1");
      expect(result).toEqual(mockOt);
    });

    it("getObjectType appends branch query param when provided", async () => {
      vi.mocked(apiClient.get).mockResolvedValue({ data: {} });

      await ontologyApi.getObjectType("ri.obj.1", "dev");

      expect(apiClient.get).toHaveBeenCalledWith("/ontology/v1/object-types/ri.obj.1?branch=dev");
    });

    it("createObjectType posts data", async () => {
      const data = { api_name: "NewType", display_name: "New Type" };
      const mockResponse = { data: { rid: "ri.obj.2", ...data } };
      vi.mocked(apiClient.post).mockResolvedValue(mockResponse);

      const result = await ontologyApi.createObjectType(data);

      expect(apiClient.post).toHaveBeenCalledWith("/ontology/v1/object-types", data);
      expect(result).toEqual(mockResponse);
    });

    it("updateObjectType puts data by rid", async () => {
      const data = { display_name: "Updated" };
      vi.mocked(apiClient.put).mockResolvedValue({ data: { rid: "ri.obj.1" } });

      await ontologyApi.updateObjectType("ri.obj.1", data);

      expect(apiClient.put).toHaveBeenCalledWith("/ontology/v1/object-types/ri.obj.1", data);
    });

    it("deleteObjectType sends delete by rid", async () => {
      vi.mocked(apiClient.delete).mockResolvedValue({ data: null });

      await ontologyApi.deleteObjectType("ri.obj.1");

      expect(apiClient.delete).toHaveBeenCalledWith("/ontology/v1/object-types/ri.obj.1");
    });
  });

  describe("LinkType operations", () => {
    it("queryLinkTypes posts to correct URL", async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: [] });

      await ontologyApi.queryLinkTypes({ limit: 5 });

      expect(apiClient.post).toHaveBeenCalledWith("/ontology/v1/link-types/query", {
        pagination: { page: 1, page_size: 5 },
        include_drafts: true,
      });
    });
  });

  describe("Version management", () => {
    it("commitStaging posts description", async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: { snapshot_id: "snap-1" } });

      await ontologyApi.commitStaging("Initial commit");

      expect(apiClient.post).toHaveBeenCalledWith("/ontology/v1/staging/commit", { description: "Initial commit" });
    });

    it("getStagingSummary fetches summary", async () => {
      vi.mocked(apiClient.get).mockResolvedValue({ data: { changes: [] } });

      await ontologyApi.getStagingSummary();

      expect(apiClient.get).toHaveBeenCalledWith("/ontology/v1/staging/summary");
    });
  });

  describe("Topology", () => {
    it("getTopology fetches without branch", async () => {
      vi.mocked(apiClient.get).mockResolvedValue({ data: { nodes: [] } });

      await ontologyApi.getTopology();

      expect(apiClient.get).toHaveBeenCalledWith("/ontology/v1/topology");
    });

    it("getTopology appends branch param", async () => {
      vi.mocked(apiClient.get).mockResolvedValue({ data: { nodes: [] } });

      await ontologyApi.getTopology("dev");

      expect(apiClient.get).toHaveBeenCalledWith("/ontology/v1/topology?branch=dev");
    });
  });
});
