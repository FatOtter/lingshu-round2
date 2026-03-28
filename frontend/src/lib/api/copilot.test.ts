import { describe, it, expect, vi, beforeEach } from "vitest";
import { copilotApi } from "./copilot";
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

describe("copilotApi", () => {
  it("createSession posts mode and context", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { session_id: "sess-1" } });

    const result = await copilotApi.createSession("shell", { module: "ontology" });

    expect(apiClient.post).toHaveBeenCalledWith("/copilot/v1/sessions", { mode: "shell", context: { module: "ontology" } });
    expect(result.data.session_id).toBe("sess-1");
  });

  it("createSession works with agent mode and no context", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { session_id: "sess-2" } });

    await copilotApi.createSession("agent");

    expect(apiClient.post).toHaveBeenCalledWith("/copilot/v1/sessions", { mode: "agent", context: undefined });
  });

  it("querySessions posts with params", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: [], pagination: { total: 0, page: 1, page_size: 20, has_next: false } });

    await copilotApi.querySessions({ pagination: { page: 1, page_size: 20 } });

    expect(apiClient.post).toHaveBeenCalledWith("/copilot/v1/sessions/query", { pagination: { page: 1, page_size: 20 } });
  });

  it("queryModels posts with params", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: [{ rid: "m1" }], pagination: { total: 1, page: 1, page_size: 5, has_next: false } });

    const result = await copilotApi.queryModels({ pagination: { page: 1, page_size: 5 } });

    expect(apiClient.post).toHaveBeenCalledWith("/copilot/v1/models/query", { pagination: { page: 1, page_size: 5 } });
    expect(result.pagination.total).toBe(1);
  });

  it("querySkills posts with params", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: [], pagination: { total: 0, page: 1, page_size: 10, has_next: false } });

    await copilotApi.querySkills({ pagination: { page: 1, page_size: 10 } });

    expect(apiClient.post).toHaveBeenCalledWith("/copilot/v1/skills/query", { pagination: { page: 1, page_size: 10 } });
  });

  it("queryMcp posts with params", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: [], pagination: { total: 0, page: 1, page_size: 10, has_next: false } });

    await copilotApi.queryMcp({ pagination: { page: 1, page_size: 10 } });

    expect(apiClient.post).toHaveBeenCalledWith("/copilot/v1/mcp/query", { pagination: { page: 1, page_size: 10 } });
  });

  it("querySubAgents posts with params", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: [], pagination: { total: 0, page: 1, page_size: 10, has_next: false } });

    await copilotApi.querySubAgents({ pagination: { page: 1, page_size: 10 } });

    expect(apiClient.post).toHaveBeenCalledWith("/copilot/v1/sub-agents/query", { pagination: { page: 1, page_size: 10 } });
  });

  it("resume posts approved flag", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: null });

    await copilotApi.resume("sess-1", true);

    expect(apiClient.post).toHaveBeenCalledWith("/copilot/v1/sessions/sess-1/resume", { approved: true });
  });

  it("deleteSession sends delete by sessionId", async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({ data: null });

    await copilotApi.deleteSession("sess-1");

    expect(apiClient.delete).toHaveBeenCalledWith("/copilot/v1/sessions/sess-1");
  });

  it("updateContext puts context by sessionId", async () => {
    vi.mocked(apiClient.put).mockResolvedValue({ data: {} });

    await copilotApi.updateContext("sess-1", { module: "data" });

    expect(apiClient.put).toHaveBeenCalledWith("/copilot/v1/sessions/sess-1/context", { context: { module: "data" } });
  });
});
