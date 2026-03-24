"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownRendererProps {
  content: string;
  maxHeight?: number;
}

export function MarkdownRenderer({ content, maxHeight }: MarkdownRendererProps) {
  return (
    <div
      className="overflow-auto"
      style={{
        maxHeight: maxHeight ?? 400,
        padding: "12px 14px",
        backgroundColor: "var(--color-surface-2)",
        border: "1px solid #e5e7eb",
        borderRadius: 6,
      }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text-primary)", margin: "12px 0 6px", fontFamily: 'var(--font-ui, "DM Sans", sans-serif)' }}>{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text-primary)", margin: "10px 0 4px", fontFamily: 'var(--font-ui, "DM Sans", sans-serif)' }}>{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-primary)", margin: "8px 0 4px", fontFamily: 'var(--font-ui, "DM Sans", sans-serif)' }}>{children}</h3>
          ),
          p: ({ children }) => (
            <p style={{ fontSize: 12, lineHeight: 1.6, color: "var(--color-text-primary)", margin: "4px 0", fontFamily: 'var(--font-ui, "DM Sans", sans-serif)' }}>{children}</p>
          ),
          ul: ({ children }) => (
            <ul style={{ margin: "4px 0", paddingLeft: 20, fontSize: 12, color: "var(--color-text-primary)", fontFamily: 'var(--font-ui, "DM Sans", sans-serif)' }}>{children}</ul>
          ),
          ol: ({ children }) => (
            <ol style={{ margin: "4px 0", paddingLeft: 20, fontSize: 12, color: "var(--color-text-primary)", fontFamily: 'var(--font-ui, "DM Sans", sans-serif)' }}>{children}</ol>
          ),
          li: ({ children }) => (
            <li style={{ lineHeight: 1.6, marginBottom: 2 }}>{children}</li>
          ),
          code: ({ className, children, ...props }) => {
            const isInline = !className;
            if (isInline) {
              return (
                <code
                  style={{
                    backgroundColor: "var(--color-border)",
                    padding: "1px 4px",
                    borderRadius: 3,
                    fontSize: 11,
                    fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                    color: "var(--color-text-primary)",
                  }}
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return (
              <code
                className={className}
                style={{
                  display: "block",
                  fontSize: 11,
                  fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                  lineHeight: 1.6,
                }}
                {...props}
              >
                {children}
              </code>
            );
          },
          pre: ({ children }) => (
            <pre
              style={{
                backgroundColor: "var(--color-surface-3)",
                border: "1px solid #e5e7eb",
                borderRadius: 4,
                padding: "8px 10px",
                margin: "6px 0",
                overflow: "auto",
                maxHeight: 200,
              }}
            >
              {children}
            </pre>
          ),
          table: ({ children }) => (
            <div style={{ overflow: "auto", margin: "6px 0" }}>
              <table
                style={{
                  borderCollapse: "collapse",
                  fontSize: 11,
                  fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                  width: "100%",
                }}
              >
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th
              style={{
                backgroundColor: "var(--color-surface-3)",
                border: "1px solid #e5e7eb",
                padding: "4px 8px",
                fontWeight: 600,
                color: "var(--color-text-primary)",
                textAlign: "left",
              }}
            >
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td
              style={{
                border: "1px solid #e5e7eb",
                padding: "4px 8px",
                color: "var(--color-text-primary)",
              }}
            >
              {children}
            </td>
          ),
          blockquote: ({ children }) => (
            <blockquote
              style={{
                borderLeft: "3px solid #0d9488",
                margin: "6px 0",
                padding: "4px 12px",
                color: "var(--color-text-secondary)",
                fontSize: 12,
                fontStyle: "italic",
              }}
            >
              {children}
            </blockquote>
          ),
          strong: ({ children }) => (
            <strong style={{ fontWeight: 600, color: "var(--color-text-primary)" }}>{children}</strong>
          ),
        }}
      />
    </div>
  );
}
