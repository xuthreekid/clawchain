"use client";

import { useState } from "react";
import { ChevronRight, Wrench, Loader2 } from "lucide-react";

interface ToolCall {
  tool?: string;
  name?: string;
  input?: any;
  output?: string;
  result?: string;
}

interface Props {
  toolCalls: ToolCall[];
}

export default function ThoughtChain({ toolCalls }: Props) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const toggle = (idx: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  if (toolCalls.length === 0) return null;

  return (
    <div className="mb-2 space-y-1">
      {toolCalls.map((tc, idx) => {
        const isOpen = expanded.has(idx);
        const name = tc.tool || tc.name || "";
        const inputVal = tc.input;
        const inputPreview = typeof inputVal === "string"
          ? inputVal.slice(0, 60)
          : JSON.stringify(inputVal ?? {}).slice(0, 60);
        const hasOutput = !!(tc.output ?? tc.result);
        const isRunning = !hasOutput;

        return (
          <div key={idx} className="glass-card overflow-hidden text-xs" style={{ borderRadius: "var(--radius-md)" }} data-testid="tool-call" data-tool-name={name} data-has-output={String(hasOutput)}>
            <button
              onClick={() => toggle(idx)}
              className="w-full flex items-center gap-1.5 px-3 py-2 transition-colors text-left"
              style={{ borderRadius: "var(--radius-md)" }}
              onMouseEnter={e => (e.currentTarget.style.background = "var(--hover)")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              <ChevronRight
                className={`w-3 h-3 flex-shrink-0 transition-transform duration-200 ${isOpen ? "rotate-90" : ""}`}
                style={{ color: "var(--text-secondary)" }}
              />
              {isRunning ? (
                <Loader2 className="w-3 h-3 flex-shrink-0 animate-spin" style={{ color: "var(--accent)" }} />
              ) : (
                <Wrench className="w-3 h-3 flex-shrink-0" style={{ color: "var(--accent)" }} />
              )}
              <span className="font-medium" style={{ color: "var(--text)" }}>{name}</span>
              {!isOpen && (
                <span className="truncate ml-1 min-w-0" style={{ color: "var(--text-tertiary)" }}>
                  {inputPreview}
                </span>
              )}
            </button>

            <div className={`grid transition-all duration-200 ease-out ${isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
              <div className="overflow-hidden">
                <div className="px-3 pb-2.5 pt-0.5 space-y-2" style={{ borderTop: "1px solid var(--border)" }}>
                  <div>
                    <span className="text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--text-tertiary)" }}>
                      Input
                    </span>
                    <pre className="mt-1 rounded-lg p-2.5 overflow-x-auto whitespace-pre-wrap text-[11px] leading-relaxed glass-inset">
                      {typeof inputVal === "string" ? inputVal : JSON.stringify(inputVal ?? {}, null, 2)}
                    </pre>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--text-tertiary)" }}>
                      Output
                    </span>
                    <pre className="mt-1 rounded-lg p-2.5 overflow-x-auto whitespace-pre-wrap text-[11px] leading-relaxed max-h-40 overflow-y-auto glass-inset">
                      {(tc.output ?? tc.result) || (
                        <span className="italic flex items-center gap-1" style={{ color: "var(--text-tertiary)" }}>
                          <Loader2 className="w-3 h-3 animate-spin inline" /> Executing...
                        </span>
                      )}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
