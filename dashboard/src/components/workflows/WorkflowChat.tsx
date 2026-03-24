"use client";

import { useState, useRef, useEffect } from "react";
import { apiFetch } from "@/lib/api";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface WorkflowChatProps {
  workflowId: string;
}

export function WorkflowChat({ workflowId }: WorkflowChatProps) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInput("");
    setLoading(true);

    try {
      const res = await apiFetch<{ reply: string }>(
        `/api/workflows/${workflowId}/chat`,
        {
          method: "POST",
          body: JSON.stringify({
            message: text,
            history: messages,
          }),
        },
      );
      setMessages([...updatedMessages, { role: "assistant", content: res.reply }]);
    } catch (err) {
      setMessages([
        ...updatedMessages,
        {
          role: "assistant",
          content: `Error: ${err instanceof Error ? err.message : "Failed to get response"}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div>
      {/* Toggle button */}
      <button
        onClick={() => setOpen(!open)}
        style={{
          padding: "6px 14px",
          borderRadius: 6,
          border: "1px solid var(--color-border)",
          backgroundColor: open ? "#f0fdfa" : "var(--color-base)",
          color: open ? "#0d9488" : "var(--color-text-secondary)",
          borderColor: open ? "#99f6e4" : "var(--color-border)",
          fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
          fontSize: 12,
          fontWeight: 500,
          cursor: "pointer",
          boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        }}
      >
        {open ? "Close Chat" : "Ask about this workflow"}
      </button>

      {/* Chat panel */}
      {open && (
        <div
          className="mt-3 rounded-md overflow-hidden"
          style={{
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-base)",
            maxWidth: 640,
          }}
        >
          {/* Messages area */}
          <div
            style={{
              height: 320,
              overflowY: "auto",
              padding: 16,
              backgroundColor: "var(--color-surface-1)",
            }}
          >
            {messages.length === 0 && (
              <div
                style={{
                  color: "var(--color-text-muted)",
                  fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                  fontSize: 13,
                  textAlign: "center",
                  paddingTop: 80,
                }}
              >
                Ask questions about this workflow&apos;s tasks, outputs, or results.
              </div>
            )}
            {messages.map((msg, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                  marginBottom: 10,
                }}
              >
                <div
                  style={{
                    maxWidth: "80%",
                    padding: "8px 12px",
                    borderRadius: 8,
                    backgroundColor: msg.role === "user" ? "var(--color-base)" : "var(--color-surface-2)",
                    border: `1px solid var(--color-border)`,
                    color: "var(--color-text-primary)",
                    fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                    fontSize: 13,
                    lineHeight: 1.5,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {loading && (
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-start",
                  marginBottom: 10,
                }}
              >
                <div
                  style={{
                    padding: "8px 12px",
                    borderRadius: 8,
                    backgroundColor: "var(--color-surface-2)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text-muted)",
                    fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                    fontSize: 13,
                  }}
                >
                  Thinking...
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input area */}
          <div
            style={{
              display: "flex",
              gap: 8,
              padding: 12,
              borderTop: "1px solid var(--color-border)",
              backgroundColor: "var(--color-base)",
            }}
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question..."
              disabled={loading}
              style={{
                flex: 1,
                padding: "8px 12px",
                borderRadius: 6,
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-surface-2)",
                fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                fontSize: 13,
                color: "var(--color-text-primary)",
                outline: "none",
              }}
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              style={{
                padding: "8px 16px",
                borderRadius: 6,
                border: "none",
                backgroundColor:
                  loading || !input.trim() ? "var(--color-border)" : "#0d9488",
                color:
                  loading || !input.trim() ? "var(--color-text-muted)" : "#ffffff",
                fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                fontSize: 13,
                fontWeight: 500,
                cursor:
                  loading || !input.trim() ? "not-allowed" : "pointer",
              }}
            >
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
