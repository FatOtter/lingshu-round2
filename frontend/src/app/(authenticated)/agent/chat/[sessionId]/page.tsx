"use client";

import { useEffect, useState, useRef, type KeyboardEvent } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { copilotApi } from "@/lib/api/copilot";
import { useCopilot } from "@/hooks/use-copilot";
import { A2UIRenderer } from "@/components/a2ui/renderer";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PageLoading } from "@/components/ui/loading";
import { cn } from "@/lib/utils";
import { Send, Square, Loader2 } from "lucide-react";
import type { A2UIComponent } from "@/types/a2ui";

export default function AgentSessionChatPage() {
  const params = useParams<{ sessionId: string }>();
  const sessionId = params.sessionId;
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: session, isLoading: sessionLoading } = useQuery({
    queryKey: ["copilot", "session", sessionId],
    queryFn: () => copilotApi.getSession(sessionId),
    enabled: !!sessionId,
  });

  const {
    messages,
    isStreaming,
    sendMessage,
    stopStreaming,
    handleApprove,
    handleReject,
  } = useCopilot({ sessionId });

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    setInput("");
    sendMessage(trimmed);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (sessionLoading) {
    return <PageLoading />;
  }

  return (
    <div className="flex flex-1 flex-col">
      {session?.data && (
        <div className="border-b px-4 py-2">
          <span className="text-sm font-medium">
            {session.data.title ?? "Untitled Session"}
          </span>
        </div>
      )}

      <ScrollArea className="flex-1 p-4">
        <div className="mx-auto flex max-w-2xl flex-col gap-3">
          {messages.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-20 text-center text-muted-foreground">
              <span className="text-sm">Continue the conversation.</span>
            </div>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={cn(
                "rounded-lg px-3 py-2 text-sm",
                msg.role === "user"
                  ? "ml-8 bg-primary text-primary-foreground"
                  : "mr-8 bg-muted",
              )}
            >
              {msg.content && <p className="whitespace-pre-wrap">{msg.content}</p>}
              {msg.events
                ?.filter((e) => e.type === "component")
                .map((e, j) => (
                  <A2UIRenderer
                    key={j}
                    component={e.data.component as A2UIComponent}
                    onApprove={handleApprove}
                    onReject={handleReject}
                  />
                ))}
            </div>
          ))}
          {isStreaming && (
            <div className="mr-8 flex items-center gap-1.5 px-3 text-xs text-muted-foreground">
              <Loader2 className="size-3 animate-spin" />
              <span>Thinking...</span>
            </div>
          )}
          <div ref={scrollRef} />
        </div>
      </ScrollArea>

      <div className="border-t p-4">
        <div className="mx-auto flex max-w-2xl gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            className="min-h-[40px] flex-1 resize-none"
            rows={1}
          />
          {isStreaming ? (
            <Button variant="outline" size="icon" onClick={stopStreaming}>
              <Square className="size-4" />
            </Button>
          ) : (
            <Button size="icon" onClick={handleSend} disabled={!input.trim()}>
              <Send className="size-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
