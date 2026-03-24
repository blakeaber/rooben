"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { TimelineEvent } from "@/lib/types";

const CATEGORIES = ["planning", "execution", "verification", "completion"] as const;

const CATEGORY_STYLE: Record<
  string,
  { bg: string; border: string; text: string; label: string }
> = {
  planning: { bg: "rgba(20, 184, 166, 0.08)", border: "#0d9488", text: "#0d9488", label: "Planning" },
  execution: { bg: "rgba(22, 163, 74, 0.08)", border: "#16a34a", text: "#16a34a", label: "Execution" },
  verification: { bg: "rgba(124, 58, 237, 0.08)", border: "#7c3aed", text: "#7c3aed", label: "Verification" },
  completion: { bg: "rgba(217, 119, 6, 0.08)", border: "#d97706", text: "#d97706", label: "Completion" },
};

interface TimelineViewProps {
  workflowId: string;
}

interface LayoutEvent extends TimelineEvent {
  _row: number;
  _leftPx: number;
}

/** Assign row indices to events so overlapping pills are staggered vertically. */
function layoutEvents(
  events: TimelineEvent[],
  minTime: number,
  timeRange: number,
  laneWidth: number,
): LayoutEvent[] {
  const sorted = [...events].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
  );

  const rows: number[][] = []; // rows[rowIndex] = [leftPx, ...]

  return sorted.map((ev) => {
    const t = new Date(ev.timestamp).getTime();
    const pct = ((t - minTime) / timeRange) * 100;
    const leftPx = 12 + (pct / 100) * (laneWidth - 24);

    let row = 0;
    while (row < rows.length) {
      const overlaps = rows[row].some((pos) => Math.abs(pos - leftPx) < 80);
      if (!overlaps) break;
      row++;
    }
    if (!rows[row]) rows[row] = [];
    rows[row].push(leftPx);

    return { ...ev, _row: row, _leftPx: leftPx };
  });
}

export function TimelineView({ workflowId }: TimelineViewProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const fetchTimeline = useCallback(() => {
    apiFetch<{ events: TimelineEvent[] }>(`/api/workflows/${workflowId}/timeline`)
      .then((data) => setEvents(data.events))
      .catch(() => {});
  }, [workflowId]);

  useEffect(() => {
    fetchTimeline();
  }, [fetchTimeline]);

  // Accumulate live planning events (ephemeral, not in DB)
  const [liveEvents, setLiveEvents] = useState<TimelineEvent[]>([]);

  const onWsEvent = useCallback(
    (event: { type: string; workflow_id?: string; [key: string]: unknown }) => {
      if (event.workflow_id !== workflowId) return;

      if (event.type?.startsWith("planning.")) {
        // Accumulate as local-only timeline events
        const live: TimelineEvent = {
          type: event.type,
          title: event.type.replace("planning.", "Plan: "),
          category: "planning",
          timestamp: new Date().toISOString(),
          detail: event.iteration ? `Iteration ${event.iteration}` : undefined,
        };
        setLiveEvents((prev) => [...prev, live]);
        return;
      }

      // DB-persisted event arrived — discard live planning events
      if (event.type === "workflow.planned") {
        setLiveEvents([]);
      }
      fetchTimeline();
    },
    [workflowId, fetchTimeline],
  );
  useWebSocket(onWsEvent);

  // Auto-scroll timeline horizontally to the end on new live events (not on initial load)
  const initialLoadRef = useRef(true);
  useEffect(() => {
    if (initialLoadRef.current) {
      initialLoadRef.current = false;
      return;
    }
    if (events.length > 0) {
      scrollRef.current?.scrollTo({ left: scrollRef.current.scrollWidth, behavior: "smooth" });
    }
  }, [events]);

  // Merge DB events with live planning events
  const allEvents = liveEvents.length > 0 ? [...liveEvents, ...events] : events;

  if (allEvents.length === 0) return null;

  // Compute time range for proportional positioning
  const timestamps = allEvents.map((e) => new Date(e.timestamp).getTime());
  const minTime = Math.min(...timestamps);
  const maxTime = Math.max(...timestamps);
  const timeRange = maxTime - minTime || 1;

  // Group events by category
  const byCategory: Record<string, TimelineEvent[]> = {};
  for (const cat of CATEGORIES) byCategory[cat] = [];
  for (const ev of allEvents) {
    if (byCategory[ev.category]) {
      byCategory[ev.category].push(ev);
    }
  }

  const LABEL_WIDTH = 90;
  const LANE_WIDTH = Math.max(800, allEvents.length * 100);

  // Pre-compute layouts and swimlane heights per category
  const BASE_LANE_HEIGHT = 48;
  const ROW_HEIGHT = 36; // 32px pill + 4px gap

  const layoutByCategory: Record<string, LayoutEvent[]> = {};
  const laneHeightByCategory: Record<string, number> = {};

  for (const cat of CATEGORIES) {
    const laid = layoutEvents(byCategory[cat], minTime, timeRange, LANE_WIDTH);
    layoutByCategory[cat] = laid;
    const maxRow = laid.reduce((mx, ev) => Math.max(mx, ev._row), 0);
    laneHeightByCategory[cat] = BASE_LANE_HEIGHT + maxRow * ROW_HEIGHT;
  }

  return (
    <div
      className="rounded-md"
      style={{
        backgroundColor: "var(--color-base)",
        border: "1px solid var(--color-border)",
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
        overflowX: "auto",
      }}
    >
      <div style={{ display: "flex" }}>
        {/* Left labels */}
        <div
          style={{
            width: LABEL_WIDTH,
            flexShrink: 0,
            borderRight: "1px solid var(--color-border)",
          }}
        >
          {CATEGORIES.map((cat) => {
            const style = CATEGORY_STYLE[cat];
            return (
              <div
                key={cat}
                style={{
                  height: laneHeightByCategory[cat],
                  display: "flex",
                  alignItems: "center",
                  paddingLeft: 10,
                  backgroundColor: style.bg,
                  borderBottom: "1px solid var(--color-border)",
                }}
              >
                <span
                  style={{
                    color: style.text,
                    fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
                    fontSize: 11,
                    fontWeight: 600,
                    letterSpacing: "0.02em",
                  }}
                >
                  {style.label}
                </span>
              </div>
            );
          })}
        </div>

        {/* Scrollable swimlanes */}
        <div
          ref={scrollRef}
          style={{
            flex: 1,
            overflowX: "auto",
            overflowY: "hidden",
          }}
        >
          <div style={{ minWidth: LANE_WIDTH, width: "100%", position: "relative" }}>
            {CATEGORIES.map((cat, categoryIndex) => {
              const style = CATEGORY_STYLE[cat];
              const catEvents = layoutByCategory[cat];
              const isTopLane = categoryIndex === 0;
              return (
                <div
                  key={cat}
                  style={{
                    height: laneHeightByCategory[cat],
                    position: "relative",
                    backgroundColor: style.bg,
                    borderBottom: "1px solid var(--color-border)",
                  }}
                >
                  {catEvents.map((ev, i) => (
                    <EventPill
                      key={`${ev.type}-${i}`}
                      event={ev}
                      left={ev._leftPx}
                      top={8 + ev._row * ROW_HEIGHT}
                      style={style}
                      isTopLane={isTopLane}
                    />
                  ))}
                </div>
              );
            })}
          </div>
          <div ref={endRef} style={{ width: 1, height: 1, display: "inline-block" }} />
        </div>
      </div>

      {/* Time axis */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          padding: "4px 10px 4px",
          marginLeft: LABEL_WIDTH,
          borderTop: "1px solid var(--color-border)",
          backgroundColor: "var(--color-surface-1)",
        }}
      >
        <span style={timeAxisStyle}>
          {new Date(minTime).toLocaleTimeString()}
        </span>
        {timeRange > 1 && (
          <span style={timeAxisStyle}>
            {new Date(minTime + timeRange / 2).toLocaleTimeString()}
          </span>
        )}
        <span style={timeAxisStyle}>
          {new Date(maxTime).toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
}

const timeAxisStyle: React.CSSProperties = {
  color: "var(--color-text-muted)",
  fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
  fontSize: 9,
  fontWeight: 500,
};

function EventPill({
  event,
  left,
  top,
  style,
  isTopLane,
}: {
  event: TimelineEvent;
  left: number;
  top: number;
  style: { border: string; text: string; bg: string };
  isTopLane: boolean;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position: "absolute",
        left,
        top,
        height: 32,
        display: "flex",
        alignItems: "center",
        gap: 4,
        padding: "0 8px",
        borderRadius: 6,
        border: `1px solid ${style.border}40`,
        backgroundColor: "var(--color-base)",
        whiteSpace: "nowrap",
        cursor: "default",
        zIndex: hovered ? 10 : 1,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          backgroundColor: style.border,
          flexShrink: 0,
        }}
      />
      <span
        style={{
          color: style.text,
          fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
          fontSize: 10,
          fontWeight: 500,
          maxWidth: 120,
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {event.title}
      </span>

      {/* Hover tooltip */}
      {hovered && (
        <div
          style={{
            position: "absolute",
            top: isTopLane ? 36 : -44,
            left: 0,
            backgroundColor: "#1a1a2e",
            color: "#ffffff",
            fontFamily: 'var(--font-ui, "DM Sans", sans-serif)',
            fontSize: 10,
            lineHeight: 1.4,
            padding: "6px 8px",
            borderRadius: 6,
            whiteSpace: "nowrap",
            zIndex: 20,
            boxShadow: "0 2px 8px rgba(0,0,0,0.25)",
            pointerEvents: "none",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 2 }}>{event.title}</div>
          {event.detail && <div style={{ color: "#d1d5db" }}>{event.detail}</div>}
          <div style={{ color: "#9ca3af" }}>
            {new Date(event.timestamp).toLocaleString()}
            {event.task_id && ` \u2022 ${event.task_id}`}
          </div>
        </div>
      )}
    </div>
  );
}
