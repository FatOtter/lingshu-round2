import { describe, it, expect, vi, beforeEach } from "vitest";
import { connectSSE, type SSEEvent } from "./sse";

describe("connectSSE", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("parses SSE events from stream", async () => {
    const events: SSEEvent[] = [];
    const sseData = [
      'event: a2ui\ndata: {"type":"text_delta","content":"hello"}\n\n',
      'event: a2ui\ndata: {"type":"done"}\n\n',
    ].join("");

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(sseData));
        controller.close();
      },
    });

    const mockResponse = {
      ok: true,
      body: stream,
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockResponse as Response);

    const done = new Promise<void>((resolve) => {
      connectSSE("session-1", "test", {
        onEvent: (event) => events.push(event),
        onDone: resolve,
      });
    });

    await done;

    expect(events).toHaveLength(2);
    expect(events[0].type).toBe("text_delta");
    expect(events[0].data).toHaveProperty("content", "hello");
    expect(events[1].type).toBe("done");
  });

  it("calls onError on fetch failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 500,
    } as Response);

    const error = await new Promise<Error>((resolve) => {
      connectSSE("session-1", "test", {
        onEvent: () => {},
        onError: resolve,
      });
    });

    expect(error.message).toContain("500");
  });

  it("can close connection", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {}), // Never resolves
    );

    const conn = connectSSE("session-1", "test", { onEvent: () => {} });
    // Should not throw
    conn.close();
  });
});
