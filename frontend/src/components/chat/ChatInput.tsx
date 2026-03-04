"use client";

import { useState, useRef, useCallback, useMemo } from "react";
import { useApp } from "@/lib/store";
import { StopCircle, ArrowUp } from "lucide-react";

export default function ChatInput() {
  const { sendMessage, isStreaming, stopStreaming, t } = useApp();
  const [text, setText] = useState("");
  const [showCommands, setShowCommands] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const commands = useMemo(() => ([
    { cmd: "/new", desc: t.cmdNewDesc },
    { cmd: "/reset", desc: t.cmdResetDesc },
    { cmd: "/compact", desc: t.cmdCompactDesc },
    { cmd: "/help", desc: t.cmdHelpDesc },
    { cmd: "/status", desc: t.cmdStatusDesc },
    { cmd: "/context", desc: t.cmdContextDesc },
    { cmd: "/usage", desc: t.cmdUsageDesc },
    { cmd: "/think", desc: t.cmdThinkDesc },
    { cmd: "/verbose", desc: t.cmdVerboseDesc },
    { cmd: "/reasoning", desc: t.cmdReasoningDesc },
    { cmd: "/model", desc: t.cmdModelDesc },
    { cmd: "/subagents", desc: t.cmdSubagentsDesc },
    { cmd: "/whoami", desc: t.cmdWhoamiDesc },
    { cmd: "/stop", desc: t.cmdStopDesc },
  ]), [t]);

  const filteredCommands = useMemo(() => {
    if (!text.startsWith("/")) return [];
    const query = text.toLowerCase();
    return commands.filter(c => c.cmd.startsWith(query));
  }, [text, commands]);

  const handleSubmit = useCallback(() => {
    if (!text.trim() || isStreaming) return;
    sendMessage(text.trim());
    setText("");
    setShowCommands(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [text, isStreaming, sendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
    if (e.key === "Escape") {
      setShowCommands(false);
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setText(val);
    setShowCommands(val.startsWith("/") && val.length > 0);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  };

  const selectCommand = (cmd: string) => {
    setText(cmd);
    setShowCommands(false);
    textareaRef.current?.focus();
  };

  return (
    <div className="p-3 relative" style={{ background: "var(--bg)" }}>
      {/* Command palette */}
      {showCommands && filteredCommands.length > 0 && (
        <div className="absolute bottom-full left-3 right-3 mb-1.5 rounded-xl max-h-52 overflow-y-auto z-10 animate-scale-in dropdown-menu">
          <div className="px-3 py-1.5 text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--text-tertiary)" }}>
            {t.commandPaletteTitle}
          </div>
          {filteredCommands.map((c) => (
            <button
              key={c.cmd}
              onClick={() => selectCommand(c.cmd)}
              className="dropdown-item"
            >
              <code className="font-mono text-[11px] px-1.5 py-0.5 rounded"
                style={{ background: "var(--accent-muted)", color: "var(--accent)" }}>
                {c.cmd}
              </code>
              <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{c.desc}</span>
            </button>
          ))}
        </div>
      )}

      <div className="max-w-3xl mx-auto">
        <div className="relative glass-card" style={{ padding: 0 }}>
          <textarea
            ref={textareaRef}
            data-testid="chat-input"
            value={text}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            onFocus={() => { if (text.startsWith("/")) setShowCommands(true); }}
            onBlur={() => setTimeout(() => setShowCommands(false), 200)}
            placeholder={t.inputPlaceholder}
            rows={1}
            className="w-full resize-none pl-4 pr-14 py-3.5 text-sm focus:outline-none bg-transparent rounded-xl"
            style={{ color: "var(--text)", border: "none" }}
          />
          <div className="absolute right-2 bottom-2">
            {isStreaming ? (
              <button
                onClick={stopStreaming}
                className="p-2 rounded-lg text-white transition-all"
                style={{ background: "var(--error)", boxShadow: "var(--shadow-xs)" }}
              >
                <StopCircle className="w-4 h-4" />
              </button>
            ) : (
              <button
                data-testid="chat-send-btn"
                onClick={handleSubmit}
                disabled={!text.trim()}
                className="p-2 rounded-lg text-white transition-all disabled:opacity-20 disabled:cursor-not-allowed"
                style={{
                  background: text.trim() ? "var(--accent)" : "var(--text-tertiary)",
                  boxShadow: text.trim() ? "var(--shadow-xs), var(--shadow-glow)" : "none",
                }}
              >
                <ArrowUp className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        <div className="flex justify-center mt-1.5">
          <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>
            {t.sendHint}
          </span>
        </div>
      </div>
    </div>
  );
}
