import { describe, it, expect, vi, beforeEach } from "vitest";
import { dataApi } from "./data";
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

describe("dataApi", () => {
  describe("Connections", () => {
    it("queryConnections posts with params", async () => {
      const mockResponse = { data: [], pagination: { total: 0, page: 1, page_size: 10, has_next: false } };
      vi.mocked(apiClient.post).mockResolvedValue(mockResponse);

      const result = await dataApi.queryConnections({ pagination: { page: 1, page_size: 10 } });

      expect(apiClient.post).toHaveBeenCalledWith("/data/v1/connections/query", { pagination: { page: 1, page_size: 10 } });
      expect(result).toEqual(mockResponse);
    });

    it("getConnection fetches by rid", async () => {
      vi.mocked(apiClient.get).mockResolvedValue({ data: { rid: "ri.conn.1" } });

      await dataApi.getConnection("ri.conn.1");

      expect(apiClient.get).toHaveBeenCalledWith("/data/v1/connections/ri.conn.1");
    });

    it("createConnection posts data", async () => {
      const data = { name: "postgres-main", type: "postgresql" };
      vi.mocked(apiClient.post).mockResolvedValue({ data: { rid: "ri.conn.2", ...data } });

      const result = await dataApi.createConnection(data);

      expect(apiClient.post).toHaveBeenCalledWith("/data/v1/connections", data);
      expect((result.data as unknown as Record<string, unknown>).name).toBe("postgres-main");
    });

    it("deleteConnection sends delete by rid", async () => {
      vi.mocked(apiClient.delete).mockResolvedValue({ data: null });

      await dataApi.deleteConnection("ri.conn.1");

      expect(apiClient.delete).toHaveBeenCalledWith("/data/v1/connections/ri.conn.1");
    });

    it("testConnection posts to test endpoint", async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: { success: true, message: "OK" } });

      await dataApi.testConnection("ri.conn.1");

      expect(apiClient.post).toHaveBeenCalledWith("/data/v1/connections/ri.conn.1/test");
    });
  });

  describe("Branches", () => {
    it("listBranches fetches all branches", async () => {
      vi.mocked(apiClient.get).mockResolvedValue({ data: [{ name: "main", hash: "abc" }] });

      const result = await dataApi.listBranches();

      expect(apiClient.get).toHaveBeenCalledWith("/data/v1/branches");
      expect(result.data).toHaveLength(1);
    });

    it("createBranch posts with name and default fromRef", async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: { name: "feature-1", hash: "def" } });

      await dataApi.createBranch("feature-1");

      expect(apiClient.post).toHaveBeenCalledWith("/data/v1/branches", { name: "feature-1", from_ref: "main" });
    });

    it("createBranch posts with custom fromRef", async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: { name: "feature-2", hash: "ghi" } });

      await dataApi.createBranch("feature-2", "dev");

      expect(apiClient.post).toHaveBeenCalledWith("/data/v1/branches", { name: "feature-2", from_ref: "dev" });
    });

    it("deleteBranch sends delete by name", async () => {
      vi.mocked(apiClient.delete).mockResolvedValue({ data: null });

      await dataApi.deleteBranch("feature-1");

      expect(apiClient.delete).toHaveBeenCalledWith("/data/v1/branches/feature-1");
    });

    it("mergeBranch posts with source and default target", async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} });

      await dataApi.mergeBranch("feature-1");

      expect(apiClient.post).toHaveBeenCalledWith("/data/v1/branches/feature-1/merge", { target: "main" });
    });

    it("mergeBranch posts with custom target", async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} });

      await dataApi.mergeBranch("feature-1", "dev");

      expect(apiClient.post).toHaveBeenCalledWith("/data/v1/branches/feature-1/merge", { target: "dev" });
    });
  });
});
