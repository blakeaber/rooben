"use client";

import { useState } from "react";
import { apiFetch, apiFetchBlob } from "@/lib/api";

interface WorkspaceFile {
  path: string;
  size_bytes: number;
  modified_at?: string;
  source?: string;
}

interface ExportBarProps {
  workflowId: string;
  workflowStatus?: string;
}

export function ExportBar({ workflowId, workflowStatus }: ExportBarProps) {
  // Guard: only show export actions for completed workflows
  if (workflowStatus && workflowStatus !== "completed") {
    return (
      <div
        style={{
          padding: "8px 14px",
          color: "var(--color-text-muted)",
          fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
          fontSize: 12,
        }}
      >
        Export available after workflow completes
      </div>
    );
  }

  const [showFiles, setShowFiles] = useState(false);
  const [files, setFiles] = useState<WorkspaceFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [filesError, setFilesError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const handleToggleFiles = async () => {
    if (showFiles) {
      setShowFiles(false);
      return;
    }
    setFilesLoading(true);
    setFilesError(null);
    try {
      const res = await apiFetch<WorkspaceFile[]>(
        `/api/workflows/${workflowId}/files`,
      );
      setFiles(res);
      setShowFiles(true);
    } catch {
      setFilesError("No workspace files available");
    } finally {
      setFilesLoading(false);
    }
  };

  const handleDownloadZip = async () => {
    setDownloading(true);
    try {
      const blob = await apiFetchBlob(
        `/api/workflows/${workflowId}/files/zip`,
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `workspace-${workflowId.slice(0, 12)}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      setFilesError("ZIP download failed");
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadFile = async (filePath: string) => {
    try {
      const blob = await apiFetchBlob(
        `/api/workflows/${workflowId}/files/${filePath}`,
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filePath.split("/").pop() || filePath;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      setFilesError(`Failed to download ${filePath}`);
    }
  };

  function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  const buttonStyle: React.CSSProperties = {
    padding: "6px 14px",
    borderRadius: 6,
    border: "1px solid var(--color-border)",
    backgroundColor: "var(--color-base)",
    color: "var(--color-text-secondary)",
    fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
    fontSize: 12,
    fontWeight: 500,
    cursor: "pointer",
    boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
    textDecoration: "none",
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
  };

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        {/* Files dropdown toggle */}
        <button
          onClick={handleToggleFiles}
          disabled={filesLoading}
          style={{
            ...buttonStyle,
            cursor: filesLoading ? "wait" : "pointer",
            backgroundColor: showFiles ? "#f0fdfa" : "var(--color-base)",
            color: showFiles ? "#0d9488" : "var(--color-text-secondary)",
            borderColor: showFiles ? "#99f6e4" : "var(--color-border)",
          }}
        >
          {filesLoading ? "Loading..." : "Files"}
        </button>

        {/* ZIP download */}
        <button
          onClick={handleDownloadZip}
          disabled={downloading}
          style={{
            ...buttonStyle,
            cursor: downloading ? "wait" : "pointer",
          }}
        >
          {downloading ? "Downloading..." : "ZIP"}
        </button>
      </div>

      {/* Files error */}
      {filesError && (
        <div
          className="mt-2"
          style={{
            color: "var(--color-text-muted)",
            fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
            fontSize: 12,
          }}
        >
          {filesError}
        </div>
      )}

      {/* File list dropdown */}
      {showFiles && files.length > 0 && (
        <div
          className="mt-3 rounded-md overflow-hidden"
          style={{
            border: "1px solid var(--color-border)",
            backgroundColor: "var(--color-base)",
          }}
        >
          {files.map((f, i) => (
            <button
              key={f.path}
              onClick={() => handleDownloadFile(f.path)}
              className="flex items-center justify-between w-full px-3 py-2 hover:bg-gray-50 transition-colors text-left"
              style={{
                border: "none",
                background: "none",
                borderTop: i > 0 ? "1px solid var(--color-surface-3)" : undefined,
                cursor: "pointer",
              }}
            >
              <span
                className="truncate"
                style={{
                  color: "var(--color-text-primary)",
                  fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                  fontSize: 12,
                }}
                title={f.path}
              >
                {f.source === "artifact" ? `[db] ${f.path}` : f.path}
              </span>
              <span
                style={{
                  color: "var(--color-text-muted)",
                  fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
                  fontSize: 11,
                  flexShrink: 0,
                  marginLeft: 12,
                }}
              >
                {formatBytes(f.size_bytes)}
              </span>
            </button>
          ))}
        </div>
      )}

      {showFiles && files.length === 0 && !filesError && (
        <div
          className="mt-2"
          style={{
            color: "var(--color-text-muted)",
            fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
            fontSize: 12,
          }}
        >
          No files in workspace
        </div>
      )}
    </div>
  );
}
