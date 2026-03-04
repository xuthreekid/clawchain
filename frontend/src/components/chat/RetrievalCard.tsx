"use client";

import { useState } from "react";
import { ChevronRight, Search } from "lucide-react";
import { useApp } from "@/lib/store";

interface Props {
  results: any[];
}

export default function RetrievalCard({ results }: Props) {
  const { t } = useApp();
  const [expanded, setExpanded] = useState(false);

  if (results.length === 0) return null;

  return (
    <div className="mb-2 glass-card overflow-hidden text-xs">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 transition-colors text-left"
        onMouseEnter={e => (e.currentTarget.style.background = "var(--hover)")}
        onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
      >
        <ChevronRight
          className={`w-3 h-3 transition-transform duration-200 ${expanded ? "rotate-90" : ""}`}
          style={{ color: "var(--accent)" }}
        />
        <Search className="w-3 h-3" style={{ color: "var(--accent)" }} />
        <span className="font-medium" style={{ color: "var(--accent)" }}>
          {t.memoryRetrieval.replace("{count}", String(results.length))}
        </span>
      </button>

      {expanded && (
        <div className="px-3 pb-2.5 space-y-2" style={{ borderTop: "1px solid var(--border)" }}>
          {results.map((r, i) => (
            <div key={i} className="glass-inset rounded-lg p-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium" style={{ color: "var(--accent)" }}>
                  {r.source}
                </span>
                <span
                  className="px-1.5 py-0.5 rounded-full text-[10px] font-medium"
                  style={{
                    background: r.score > 0.7 ? "var(--success-bg)" : "var(--hover)",
                    color: r.score > 0.7 ? "var(--success)" : "var(--text-secondary)",
                  }}
                >
                  {(r.score * 100).toFixed(0)}%
                </span>
              </div>
              <p className="whitespace-pre-wrap leading-relaxed" style={{ color: "var(--text)" }}>
                {r.text}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
