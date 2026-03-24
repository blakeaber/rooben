"use client";

import { useState } from "react";
import { MarkdownRenderer } from "./MarkdownRenderer";

interface ArtifactViewerProps {
  artifacts: Record<string, string>;
}

function getFileType(name: string): "markdown" | "code" | "data" | "text" {
  const ext = name.split(".").pop()?.toLowerCase() || "";
  if (["md", "markdown"].includes(ext)) return "markdown";
  if (["py", "js", "ts", "tsx", "jsx", "json", "yaml", "yml", "toml", "sh", "bash", "css", "html", "sql", "go", "rs", "java", "c", "cpp", "h", "rb", "php"].includes(ext)) return "code";
  if (["csv", "tsv"].includes(ext)) return "data";
  return "text";
}

function getLanguage(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() || "";
  const map: Record<string, string> = {
    py: "python", js: "javascript", ts: "typescript", tsx: "tsx", jsx: "jsx",
    json: "json", yaml: "yaml", yml: "yaml", toml: "toml", sh: "bash",
    css: "css", html: "html", sql: "sql", go: "go", rs: "rust",
    java: "java", c: "c", cpp: "cpp", rb: "ruby", php: "php",
  };
  return map[ext] || "plaintext";
}

function CsvTable({ content }: { content: string }) {
  const lines = content.trim().split("\n").slice(0, 50);
  if (lines.length === 0) return null;
  const headers = lines[0].split(",").map((h) => h.trim());
  const rows = lines.slice(1).map((line) => line.split(",").map((c) => c.trim()));

  return (
    <div style={{ overflow: "auto", maxHeight: 300 }}>
      <table style={{ borderCollapse: "collapse", fontSize: 11, fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)', width: "100%" }}>
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={i} style={{ backgroundColor: "var(--color-surface-3)", border: "1px solid var(--color-border)", padding: "4px 8px", fontWeight: 600, color: "var(--color-text-primary)", textAlign: "left" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {row.map((cell, ci) => (
                <td key={ci} style={{ border: "1px solid var(--color-border)", padding: "4px 8px", color: "var(--color-text-primary)" }}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {lines.length >= 50 && (
        <div style={{ color: "var(--color-text-muted)", fontSize: 10, padding: "4px 8px", fontStyle: "italic" }}>Showing first 50 rows</div>
      )}
    </div>
  );
}

export function ArtifactViewer({ artifacts }: ArtifactViewerProps) {
  const names = Object.keys(artifacts);
  const [activeTab, setActiveTab] = useState(names[0] || "");

  if (names.length === 0) return null;

  const content = artifacts[activeTab] || "";
  const fileType = getFileType(activeTab);
  const lang = getLanguage(activeTab);

  return (
    <div style={{ border: "1px solid var(--color-border)", borderRadius: 6, overflow: "hidden" }}>
      {/* Tab bar */}
      {names.length > 1 && (
        <div
          style={{
            display: "flex",
            gap: 0,
            borderBottom: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface-2)",
            overflow: "auto",
          }}
        >
          {names.map((name) => (
            <button
              key={name}
              onClick={() => setActiveTab(name)}
              style={{
                padding: "6px 12px",
                border: "none",
                borderBottom: activeTab === name ? "2px solid #0d9488" : "2px solid transparent",
                backgroundColor: activeTab === name ? "var(--color-base)" : "transparent",
                color: activeTab === name ? "#0d9488" : "var(--color-text-secondary)",
                fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                fontSize: 11,
                fontWeight: activeTab === name ? 600 : 400,
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {name}
            </button>
          ))}
        </div>
      )}

      {/* Single tab header when only one artifact */}
      {names.length === 1 && (
        <div
          style={{
            padding: "6px 12px",
            borderBottom: "1px solid var(--color-border)",
            backgroundColor: "var(--color-surface-2)",
            color: "#0d9488",
            fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
            fontSize: 11,
            fontWeight: 600,
          }}
        >
          {activeTab}
        </div>
      )}

      {/* Content area */}
      <div style={{ backgroundColor: "var(--color-base)" }}>
        {fileType === "markdown" && (
          <MarkdownRenderer content={content} maxHeight={300} />
        )}
        {fileType === "code" && (
          <pre
            style={{
              maxHeight: 300,
              overflow: "auto",
              padding: "10px 12px",
              margin: 0,
              backgroundColor: "var(--color-surface-2)",
              fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
              fontSize: 11,
              lineHeight: 1.6,
              color: "var(--color-text-primary)",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            <code className={`language-${lang}`}>{content}</code>
          </pre>
        )}
        {fileType === "data" && <CsvTable content={content} />}
        {fileType === "text" && (
          <pre
            style={{
              maxHeight: 300,
              overflow: "auto",
              padding: "10px 12px",
              margin: 0,
              backgroundColor: "var(--color-surface-2)",
              fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
              fontSize: 11,
              lineHeight: 1.6,
              color: "var(--color-text-secondary)",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            {content}
          </pre>
        )}
      </div>
    </div>
  );
}
