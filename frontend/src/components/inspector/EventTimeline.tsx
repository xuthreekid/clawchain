"use client";

import { useMemo, useState } from "react";
import { useApp } from "@/lib/store";
import { Clock, Zap, AlertCircle, CheckCircle } from "lucide-react";

const EVENT_ICONS: Record<string, typeof Clock> = {
  turn_start: Zap,
  turn_end: CheckCircle,
  turn_error: AlertCircle,
  auto_compact_start: Clock,
  auto_compact_done: CheckCircle,
  recursion_limit_reached: AlertCircle,
  session_memory_saved: CheckCircle,
  session_memory_failed: AlertCircle,
};

function getEventLabels(t: any): Record<string, string> {
  return {
    turn_start: t.evtTurnStart,
    turn_end: t.evtTurnEnd,
    turn_error: t.evtTurnError,
    tool_start: t.evtToolStart,
    tool_end: t.evtToolEnd,
    auto_compact_start: t.evtAutoCompactStart,
    auto_compact_done: t.evtAutoCompactDone,
    recursion_limit_reached: t.evtRecursionLimit,
    session_memory_saved: t.evtMemorySaved,
    session_memory_failed: t.evtMemoryFailed,
  };
}

export default function EventTimeline() {
  const { lifecycleEvents, t } = useApp();
  const [filter, setFilter] = useState<"all" | "memory" | "error">("all");
  const EVENT_LABELS = getEventLabels(t);

  const filteredEvents = useMemo(() => {
    if (filter === "all") return lifecycleEvents;
    if (filter === "memory") {
      return lifecycleEvents.filter((evt) =>
        evt.event === "session_memory_saved" || evt.event === "session_memory_failed"
      );
    }
    return lifecycleEvents.filter((evt) =>
      evt.event.includes("error") ||
      evt.event.includes("failed") ||
      evt.event.includes("recursion")
    );
  }, [lifecycleEvents, filter]);

  if (lifecycleEvents.length === 0) {
    return (
      <div className="text-center py-10 text-sm" style={{ color: "var(--text-tertiary)" }}>
        {t.evtNoEvents}
      </div>
    );
  }

  return (
    <div className="space-y-2 relative">
      <div className="flex items-center gap-1.5 pb-1">
        <button
          type="button"
          onClick={() => setFilter("all")}
          className="px-2 py-1 rounded-md text-[10px] transition-colors"
          style={{
            background: filter === "all" ? "var(--accent-muted)" : "transparent",
            color: filter === "all" ? "var(--accent)" : "var(--text-secondary)",
            border: "1px solid var(--border)",
          }}
        >
          {t.evtFilterAll}
        </button>
        <button
          type="button"
          onClick={() => setFilter("memory")}
          className="px-2 py-1 rounded-md text-[10px] transition-colors"
          style={{
            background: filter === "memory" ? "var(--accent-muted)" : "transparent",
            color: filter === "memory" ? "var(--accent)" : "var(--text-secondary)",
            border: "1px solid var(--border)",
          }}
        >
          {t.evtFilterMemory}
        </button>
        <button
          type="button"
          onClick={() => setFilter("error")}
          className="px-2 py-1 rounded-md text-[10px] transition-colors"
          style={{
            background: filter === "error" ? "var(--error-bg)" : "transparent",
            color: filter === "error" ? "var(--error)" : "var(--text-secondary)",
            border: "1px solid var(--border)",
          }}
        >
          {t.evtFilterError}
        </button>
      </div>

      {filteredEvents.length === 0 && (
        <div className="text-center py-6 text-xs" style={{ color: "var(--text-tertiary)" }}>
          {t.evtNoFilteredEvents}
        </div>
      )}

      {/* Timeline line */}
      <div
        className="absolute left-[15px] top-2 bottom-2 w-px"
        style={{ background: "var(--border)" }}
      />

      {filteredEvents.map((evt, i) => {
        const Icon = EVENT_ICONS[evt.event] || Clock;
        const label = EVENT_LABELS[evt.event] || evt.event;
        const time = new Date(evt.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

        const isError = evt.event.includes("error") || evt.event.includes("recursion");
        const isSuccess = evt.event.includes("end") || evt.event.includes("done");

        const dotColor = isError ? "var(--error)" : isSuccess ? "var(--success)" : "var(--accent)";
        const bgColor = isError ? "var(--error-bg)" : isSuccess ? "var(--success-bg)" : "var(--hover)";
        const textColor = isError ? "var(--error)" : isSuccess ? "var(--success)" : "var(--text)";

        return (
          <div key={i} className="flex items-start gap-2.5 pl-1 relative">
            <div
              className="w-[10px] h-[10px] rounded-full mt-1.5 flex-shrink-0 z-10 relative"
              style={{ background: dotColor, boxShadow: `0 0 0 3px var(--bg)` }}
            />
            <div
              className="flex-1 min-w-0 rounded-lg px-3 py-2 text-xs"
              style={{ background: bgColor }}
            >
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-1.5">
                  <Icon className="w-3 h-3 flex-shrink-0" style={{ color: dotColor }} />
                  <span className="font-medium" style={{ color: textColor }}>{label}</span>
                </div>
                <span style={{ color: "var(--text-tertiary)" }}>{time}</span>
              </div>
              {evt.run_id && (
                <div className="truncate mt-0.5" style={{ color: "var(--text-tertiary)" }}>
                  run: {evt.run_id.slice(0, 12)}...
                </div>
              )}
              {evt.data?.usage && (
                <div className="mt-1" style={{ color: "var(--text-secondary)" }}>
                  {evt.data.usage.total_tokens?.toLocaleString()} tokens · {evt.data.usage.duration_ms}ms
                </div>
              )}
              {evt.data?.error && (
                <div className="mt-1 truncate" style={{ color: "var(--error)" }}>
                  {evt.data.error}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
