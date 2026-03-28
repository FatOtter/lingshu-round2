import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient, ApiClientError } from "./client";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

beforeEach(() => {
  mockFetch.mockReset();
});

describe("apiClient", () => {
  it("GET request returns parsed JSON on success", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ data: { status: "ok" }, metadata: { request_id: "r1" } }),
    });

    const result = await apiClient.get("/health");
    expect(result).toEqual({ data: { status: "ok" }, metadata: { request_id: "r1" } });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/health",
      expect.objectContaining({ method: "GET", credentials: "include" }),
    );
  });

  it("POST request sends JSON body", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ data: { id: 1 } }),
    });

    await apiClient.post("/items", { name: "test" });
    const [, options] = mockFetch.mock.calls[0];
    expect(options.method).toBe("POST");
    expect(options.body).toBe(JSON.stringify({ name: "test" }));
  });

  it("throws ApiClientError on non-ok response", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 404,
      json: () =>
        Promise.resolve({
          error: { code: "COMMON_NOT_FOUND", message: "Not found" },
          metadata: { request_id: "r2" },
        }),
    });

    await expect(apiClient.get("/missing")).rejects.toThrow(ApiClientError);
    try {
      await apiClient.get("/missing");
    } catch (e) {
      const err = e as ApiClientError;
      expect(err.status).toBe(404);
      expect(err.code).toBe("COMMON_NOT_FOUND");
    }
  });

  it("handles non-JSON error response", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error("not json")),
    });

    await expect(apiClient.get("/fail")).rejects.toThrow(ApiClientError);
  });

  it("PUT request works", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ data: { updated: true } }),
    });

    const result = await apiClient.put("/items/1", { name: "updated" });
    expect(result).toEqual({ data: { updated: true } });
  });

  it("DELETE request works", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ data: null }),
    });

    const result = await apiClient.delete("/items/1");
    expect(result).toEqual({ data: null });
  });
});
