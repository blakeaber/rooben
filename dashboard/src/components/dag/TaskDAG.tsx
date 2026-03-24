"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { apiFetch } from "@/lib/api";
import type { DAGNode, DAGEdge, Task } from "@/lib/types";
import { TaskNode } from "./TaskNode";
import { TaskDetailPanel } from "./TaskDetailPanel";

// Register custom node type outside component to keep reference stable
const nodeTypes = { taskNode: TaskNode };

// Default edge style — light gray connecting lines
const defaultEdgeOptions = {
  style: {
    stroke: "var(--color-border-muted)",
    strokeWidth: 1.5,
  },
  labelStyle: {
    fill: "var(--color-text-secondary)",
    fontSize: 10,
  },
};

interface TaskDAGProps {
  workflowId: string;
  tasks: Task[];
}

export function TaskDAG({ workflowId, tasks }: TaskDAGProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    setLoadError(null);
    apiFetch<{ nodes: DAGNode[]; edges: DAGEdge[] }>(
      `/api/workflows/${workflowId}/dag`
    )
      .then((data) => {
        const styledEdges = (data.edges as unknown as Edge[]).map((e) => {
          const isAnimated = (e as DAGEdge & { animated?: boolean }).animated;
          return {
            ...e,
            animated: isAnimated,
            style: {
              stroke: isAnimated ? "#14b8a6" : "var(--color-border-muted)",
              strokeWidth: isAnimated ? 2 : 1.5,
              strokeDasharray: isAnimated ? "6 4" : "none",
              transition: "stroke 0.4s ease, stroke-width 0.3s ease",
            },
          };
        });
        setNodes(data.nodes as unknown as Node[]);
        setEdges(styledEdges);
      })
      .catch((err: unknown) => {
        setLoadError(
          err instanceof Error ? err.message : "Failed to load DAG"
        );
      });
  }, [workflowId, setNodes, setEdges]);

  useEffect(() => {
    if (tasks.length === 0) return;
    setNodes((prev) =>
      prev.map((node) => {
        const task = tasks.find((t) => t.id === node.id);
        if (task && node.data.status !== task.status) {
          return { ...node, data: { ...node.data, status: task.status } };
        }
        return node;
      })
    );
  }, [tasks, setNodes]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const task = tasks.find((t) => t.id === node.id) ?? null;
      setSelectedTask(task);
    },
    [tasks]
  );

  const onPaneClick = useCallback(() => {
    setSelectedTask(null);
  }, []);

  return (
    <div
      className="relative rounded-lg overflow-hidden"
      style={{
        height: 520,
        backgroundColor: "var(--color-surface-1)",
        border: "1px solid var(--color-border)",
      }}
    >
      {loadError && (
        <div
          className="absolute inset-0 z-10 flex items-center justify-center text-sm"
          style={{ color: "#dc2626", fontFamily: 'var(--font-jetbrains, "JetBrains Mono", monospace)' }}
        >
          DAG LOAD ERROR: {loadError}
        </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        fitView
        fitViewOptions={{ padding: 0.2, includeHiddenNodes: false }}
        preventScrolling
        minZoom={0.25}
        maxZoom={2}
        zoomOnScroll={false}
        zoomOnDoubleClick={false}
        panOnScroll
        panOnScrollMode={"free" as any}
        zoomActivationKeyCode="Meta"
        proOptions={{ hideAttribution: true }}
        style={{ backgroundColor: "var(--color-surface-1)" }}
      >
        {/* Dot-grid background */}
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1}
          color="var(--color-border-muted)"
          style={{ backgroundColor: "var(--color-surface-1)" }}
        />

        {/* Controls */}
        <Controls
          style={{
            backgroundColor: "var(--color-base)",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
          }}
          showInteractive={false}
        />
      </ReactFlow>

      {/* Slide-out detail panel rendered inside the DAG frame */}
      <TaskDetailPanel
        task={selectedTask}
        onClose={() => setSelectedTask(null)}
      />
    </div>
  );
}
