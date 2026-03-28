"use client";

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { X, Send, Square, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useShellStore } from "@/stores/shell-store";
import { useCopilot } from "@/hooks/use-copilot";
import { copilotApi } from "@/lib/api/copilot";
import { A2UIRenderer } from "@/components/a2ui/renderer";
import { cn } from "@/lib/utils";
import type { A2UIComponent } from "@/types/a2ui";

export function Shell() {
  const { isOpen, width, sessionId, close, setWidth, setSessionId } = useShellStore();
  const [input, setInput] = useState("");
  const [sessionLoading, setSessionLoading] = useState(false);
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const sessionInitRef = useRef(false);

  // Create or restore shell session when opened
  useEffect(() => {
    if (!isOpen) return;
    if (sessionId) return; // Already have a session
    if (sessionInitRef.current) return; // Already initializing

    sessionInitRef.current = true;
    setSessionLoading(true);

    copilotApi
      .createSession("shell")
      .then((res) => {
        setSessionId(res.data.session_id);
      })
      .catch((err) => {
        console.error("Failed to create shell session:", err);
      })
      .finally(() => {
        setSessionLoading(false);
        sessionInitRef.current = false;
      });
  }, [isOpen, sessionId, setSessionId]);

  const {
    messages,
    isStreaming,
    sendMessage,
    stopStreaming,
    handleApprove,
    handleReject,
  } = useCopilot({ sessionId });

  // Auto-scroll on new messages
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(() => {
    const content = input.trim();
    if (!content || isStreaming || !sessionId) return;

    setInput("");
    sendMessage(content);
  }, [input, isStreaming, sessionId, sendMessage]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleDragStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      dragRef.current = { startX: e.clientX, startWidth: width };

      const onMove = (moveEvent: MouseEvent) => {
        if (!dragRef.current) return;
        const delta = dragRef.current.startX - moveEvent.clientX;
        setWidth(dragRef.current.startWidth + delta);
      };

      const onUp = () => {
        dragRef.current = null;
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },
    [width, setWidth],
  );

  if (!isOpen) return null;

  return (
    <div className="relative flex flex-col border-l bg-card" style={{ width }}>
      {/* Drag handle */}
      <div
        className="absolute inset-y-0 left-0 w-1 cursor-col-resize hover:bg-primary/20"
        onMouseDown={handleDragStart}
      />

      {/* Header */}
      <div className="flex items-center justify-between border-b px-3 py-2">
        <span className="text-sm font-medium">Copilot</span>
        <Button variant="ghost" size="icon-xs" onClick={close}>
          <X className="size-4" />
        </Button>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 p-3">
        <div className="flex flex-col gap-3">
          {sessionLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="size-5 animate-spin text-muted-foreground" />
            </div>
          )}
          {!sessionLoading && messages.length === 0 && (
            <p className="text-center text-sm text-muted-foreground py-8">
              Ask me anything about your current context.
            </p>
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
              {msg.content && (
                <p className="whitespace-pre-wrap">{msg.content}</p>
              )}
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

      {/* Input */}
      <div className="border-t p-3">
        <div className="flex gap-2">
          <Textarea
            placeholder="Ask Copilot..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="min-h-[40px] max-h-[120px] resize-none text-sm"
            rows={1}
            disabled={sessionLoading || !sessionId}
          />
          {isStreaming ? (
            <Button size="icon" variant="outline" onClick={stopStreaming}>
              <Square className="size-4" />
            </Button>
          ) : (
            <Button
              size="icon"
              onClick={handleSend}
              disabled={!input.trim() || !sessionId || sessionLoading}
            >
              <Send className="size-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
