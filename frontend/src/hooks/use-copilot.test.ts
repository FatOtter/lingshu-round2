import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCopilot } from "./use-copilot";

const mockConnectSSE = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/ontology/object-types",
  useParams: () => ({}),
}));

vi.mock("@/lib/sse", () => ({
  connectSSE: (...args: unknown[]) => mockConnectSSE(...args),
}));

vi.mock("@/lib/api/copilot", () => ({
  copilotApi: {
    updateContext: vi.fn().mockResolvedValue({}),
    resume: vi.fn().mockResolvedValue({ data: null }),
  },
}));

import { copilotApi } from "@/lib/api/copilot";

beforeEach(() => {
  vi.clearAllMocks();
  mockConnectSSE.mockReturnValue({ close: vi.fn() });
});

describe("useCopilot", () => {
  it("returns initial state with empty messages", () => {
    const { result } = renderHook(() => useCopilot({ sessionId: null }));

    expect(result.current.messages).toEqual([]);
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.sessionId).toBeNull();
  });

  it("does not send message when sessionId is null", () => {
    const { result } = renderHook(() => useCopilot({ sessionId: null }));

    act(() => {
      result.current.sendMessage("hello");
    });

    expect(mockConnectSSE).not.toHaveBeenCalled();
    expect(result.current.messages).toEqual([]);
  });

  it("sendMessage adds user and assistant messages", () => {
    const { result } = renderHook(() => useCopilot({ sessionId: "sess-1" }));

    act(() => {
      result.current.sendMessage("hello");
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0].role).toBe("user");
    expect(result.current.messages[0].content).toBe("hello");
    expect(result.current.messages[1].role).toBe("assistant");
    expect(result.current.isStreaming).toBe(true);
    expect(mockConnectSSE).toHaveBeenCalledWith("sess-1", "hello", expect.any(Object));
  });

  it("handleApprove calls resume with approved=true", async () => {
    const { result } = renderHook(() => useCopilot({ sessionId: "sess-1" }));

    await act(async () => {
      await result.current.handleApprove();
    });

    expect(copilotApi.resume).toHaveBeenCalledWith("sess-1", true);
  });

  it("handleReject calls resume with approved=false", async () => {
    const { result } = renderHook(() => useCopilot({ sessionId: "sess-1" }));

    await act(async () => {
      await result.current.handleReject();
    });

    expect(copilotApi.resume).toHaveBeenCalledWith("sess-1", false);
  });

  it("stopStreaming closes connection and sets isStreaming to false", () => {
    const mockClose = vi.fn();
    mockConnectSSE.mockReturnValue({ close: mockClose });

    const { result } = renderHook(() => useCopilot({ sessionId: "sess-1" }));

    act(() => {
      result.current.sendMessage("test");
    });

    act(() => {
      result.current.stopStreaming();
    });

    expect(mockClose).toHaveBeenCalled();
    expect(result.current.isStreaming).toBe(false);
  });
});
