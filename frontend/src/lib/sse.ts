/**
 * SSE client for A2UI event streaming.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
  event_id?: number;
}

export interface SSEConnection {
  close: () => void;
}

export function connectSSE(
  sessionId: string,
  content: string,
  options: {
    onEvent: (event: SSEEvent) => void;
    onError?: (error: Error) => void;
    onDone?: () => void;
  },
): SSEConnection {
  const controller = new AbortController();

  const run = async () => {
    try {
      const response = await fetch(
        `${BASE_URL}/copilot/v1/sessions/${sessionId}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ content }),
          signal: controller.signal,
        },
      );

      if (!response.ok) {
        throw new Error(`SSE connection failed: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response body");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        let currentData = "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            currentData = line.slice(6);
          } else if (line === "" && currentData) {
            try {
              const parsed = JSON.parse(currentData) as Record<string, unknown>;
              const event: SSEEvent = {
                type: parsed.type as string,
                data: parsed,
              };
              options.onEvent(event);

              if (event.type === "done") {
                options.onDone?.();
              }
            } catch {
              // Skip unparseable lines
            }
            currentData = "";
          }
        }
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }
      options.onError?.(error instanceof Error ? error : new Error(String(error)));
    }
  };

  run();

  return {
    close: () => controller.abort(),
  };
}
