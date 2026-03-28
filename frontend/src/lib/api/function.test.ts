import { describe, it, expect, vi, beforeEach } from "vitest";
import { functionApi } from "./function";
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

describe("functionApi", () => {
  it("executeAction posts rid with params", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { execution_id: "exec-1" } });

    await functionApi.executeAction("ri.action.1", { input: "value" });

    expect(apiClient.post).toHaveBeenCalledWith("/function/v1/actions/ri.action.1/execute", { params: { input: "value" } });
  });

  it("executeAction passes skip_confirmation option", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { execution_id: "exec-2" } });

    await functionApi.executeAction("ri.action.1", { x: 1 }, { skip_confirmation: true });

    expect(apiClient.post).toHaveBeenCalledWith("/function/v1/actions/ri.action.1/execute", {
      params: { x: 1 },
      skip_confirmation: true,
    });
  });

  it("queryWorkflows posts with default pagination", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: [], pagination: { total: 0 } });

    await functionApi.queryWorkflows();

    expect(apiClient.post).toHaveBeenCalledWith("/function/v1/workflows/query", {
      pagination: { page: 1, page_size: 20 },
    });
  });

  it("queryWorkflows posts with custom params", async () => {
    const params = { pagination: { page: 2, page_size: 10 }, status: "active" };
    vi.mocked(apiClient.post).mockResolvedValue({ data: [] });

    await functionApi.queryWorkflows(params);

    expect(apiClient.post).toHaveBeenCalledWith("/function/v1/workflows/query", params);
  });

  it("createWorkflow posts data", async () => {
    const data = { name: "My Workflow", steps: [] };
    vi.mocked(apiClient.post).mockResolvedValue({ data: { rid: "ri.wf.1", ...data } });

    const result = await functionApi.createWorkflow(data);

    expect(apiClient.post).toHaveBeenCalledWith("/function/v1/workflows", data);
    expect(result.data.rid).toBe("ri.wf.1");
  });

  it("executeWorkflow posts rid with inputs", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { execution_id: "wf-exec-1" } });

    await functionApi.executeWorkflow("ri.wf.1", { trigger: "manual" });

    expect(apiClient.post).toHaveBeenCalledWith("/function/v1/workflows/ri.wf.1/execute", { inputs: { trigger: "manual" } });
  });

  it("getExecution fetches by executionId", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { execution_id: "exec-1", status: "completed" } });

    await functionApi.getExecution("exec-1");

    expect(apiClient.get).toHaveBeenCalledWith("/function/v1/executions/exec-1");
  });

  it("deleteWorkflow sends delete by rid", async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({ data: null });

    await functionApi.deleteWorkflow("ri.wf.1");

    expect(apiClient.delete).toHaveBeenCalledWith("/function/v1/workflows/ri.wf.1");
  });
});
