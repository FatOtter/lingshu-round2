"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useParams } from "next/navigation";
import { connectSSE, type SSEConnection } from "@/lib/sse";
import type { A2UIEvent, Message } from "@/types/copilot";
import { copilotApi } from "@/lib/api/copilot";

interface UseCopilotOptions {
  sessionId: string | null;
}

function extractCurrentModule(pathname: string): string {
  const segments = pathname.split("/").filter(Boolean);
  return segments[0] ?? "";
}

function extractEntityRid(params: Record<string, string | string[]>): string | undefined {
  const rid = params.rid;
  if (typeof rid === "string") return rid;
  if (Array.isArray(rid)) return rid[0];
  return undefined;
}

export function useCopilot({ sessionId }: UseCopilotOptions) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const connectionRef = useRef<SSEConnection | null>(null);
  const pathname = usePathname();
  const params = useParams();

  // Sync shell context when navigation changes
  useEffect(() => {
    if (!sessionId) return;

    const currentModule = extractCurrentModule(pathname);
    const entityRid = extractEntityRid(params as Record<string, string | string[]>);

    const context: Record<string, unknown> = {
      module: currentModule,
      page: pathname,
    };

    if (entityRid) {
      context.entity_rid = entityRid;
    }

    copilotApi.updateContext(sessionId, context).catch((err) => {
      console.error("Failed to sync copilot context:", err);
    });
  }, [sessionId, pathname, params]);

  const sendMessage = useCallback(
    (content: string) => {
      if (!sessionId || isStreaming) return;

      const userMessage: Message = {
        role: "user",
        content,
        timestamp: new Date().toISOString(),
      };

      const assistantMessage: Message = {
        role: "assistant",
        content: "",
        timestamp: new Date().toISOString(),
        events: [],
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsStreaming(true);

      connectionRef.current = connectSSE(sessionId, content, {
        onEvent: (event) => {
          setMessages((prev) => {
            const updated = [...prev];
            const last = { ...updated[updated.length - 1] };
            const events = [...(last.events ?? [])];

            if (event.type === "text_delta") {
              const delta = (event.data.content as string) ?? "";
              last.content = last.content + delta;
            } else if (event.type === "component") {
              const a2uiEvent: A2UIEvent = {
                type: "component",
                data: event.data,
                event_id: event.event_id,
              };
              events.push(a2uiEvent);
              last.events = events;
            } else if (event.type !== "done") {
              const genericEvent: A2UIEvent = {
                type: event.type,
                data: event.data,
                event_id: event.event_id,
              };
              events.push(genericEvent);
              last.events = events;
            }

            updated[updated.length - 1] = last;
            return updated;
          });
        },
        onError: (error) => {
          console.error("SSE error:", error);
          setIsStreaming(false);
        },
        onDone: () => {
          setIsStreaming(false);
          connectionRef.current = null;
        },
      });
    },
    [sessionId, isStreaming],
  );

  const handleApprove = useCallback(async () => {
    if (!sessionId) return;
    await copilotApi.resume(sessionId, true);
  }, [sessionId]);

  const handleReject = useCallback(async () => {
    if (!sessionId) return;
    await copilotApi.resume(sessionId, false);
  }, [sessionId]);

  const stopStreaming = useCallback(() => {
    connectionRef.current?.close();
    connectionRef.current = null;
    setIsStreaming(false);
  }, []);

  return {
    messages,
    isStreaming,
    sendMessage,
    stopStreaming,
    handleApprove,
    handleReject,
    sessionId,
  };
}
