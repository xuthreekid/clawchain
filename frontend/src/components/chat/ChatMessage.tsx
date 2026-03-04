"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { User, Bot, Copy, Check, Loader2, Info } from "lucide-react";
import type { ChatMessage as ChatMsgType } from "@/lib/store";
import { useApp } from "@/lib/store";
import ThoughtChain from "./ThoughtChain";
import SubagentInlineCard from "./SubagentInlineCard";

interface Props {
  message: ChatMsgType;
  hideAvatar?: boolean;
  isLast?: boolean;
}

export default function ChatMessage({ message, hideAvatar, isLast }: Props) {
  const { t } = useApp();
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const isCommand = message.role === ("command" as any);
  const finishedAt = message.finishedAt || message.createdAt;
  const timeLabel = finishedAt != null
    ? new Date(finishedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : null;
  const durationSeconds =
    typeof message.streamDurationMs === "number"
      ? message.streamDurationMs / 1000
      : message.usage && message.usage.duration_ms > 0
        ? message.usage.duration_ms / 1000
        : null;

  const handleCopy = () => {
    if (!message.content) return;
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const localizeCommandContent = (raw: string) => {
    const s = (raw || "").trim();
    if (!s) return s;

    const helpTemplate = [
      `## ${t.helpListTitle}`,
      `- \`/new\` — ${t.cmdNewDesc}`,
      `- \`/reset\` — ${t.cmdResetDesc}`,
      `- \`/compact\` — ${t.cmdCompactDesc}`,
      `- \`/help\` — ${t.cmdHelpDesc}`,
      `- \`/status\` — ${t.cmdStatusDesc}`,
      `- \`/context\` — ${t.cmdContextDesc}`,
      `- \`/usage\` — ${t.cmdUsageDesc}`,
      `- \`/stop\` — ${t.cmdStopDesc}`,
      `- \`/think\` — ${t.cmdThinkDesc}`,
      `- \`/verbose\` — ${t.cmdVerboseDesc}`,
      `- \`/reasoning\` — ${t.cmdReasoningDesc}`,
      `- \`/model\` — ${t.cmdModelDesc}`,
      `- \`/subagents\` — ${t.cmdSubagentsDesc}`,
      `- \`/whoami\` — ${t.cmdWhoamiDesc}`,
    ].join("\n");

    if (
      s.startsWith("## 可用命令") ||
      s.startsWith("## Available Commands") ||
      (s.includes("`/new`") && s.includes("`/reset`") && s.includes("`/help`"))
    ) {
      return helpTemplate;
    }

    const low = s.toLowerCase();
    if (s.includes("正在执行压缩") || low.includes("compaction in progress")) {
      return t.cmdCompactProgress;
    }
    if (s.startsWith("压缩未执行：") || low.startsWith("compaction skipped:")) {
      const lines = s.split("\n");
      const first = lines[0] || s;
      const reasonRaw = first.split("：").slice(1).join("：").trim() || first.split(":").slice(1).join(":").trim();
      let reason = reasonRaw;
      if (reasonRaw.includes("消息过少")) reason = t.cmdCompactReasonTooFewMessages;
      else if (reasonRaw.includes("无足够消息可压缩")) reason = t.cmdCompactReasonNoEnoughCompressible;
      else if (reasonRaw.includes("会话不存在")) reason = t.cmdCompactReasonSessionMissing;
      const rest = lines.slice(1).join("\n").trim();
      return `${t.cmdCompactSkipped}\n${reason ? `- ${reason}` : ""}${rest ? `\n\n${rest}` : ""}`.trim();
    }
    if (s.startsWith("压缩完成。") || low.startsWith("compaction completed")) {
      const lines = s.split("\n");
      if (lines.length > 1) return `${t.cmdCompactDone}\n${lines.slice(1).join("\n")}`;
      return t.cmdCompactDone;
    }
    if (s.startsWith("压缩失败") || low.startsWith("compaction failed")) {
      return `${t.cmdCompactFailed}\n${s}`;
    }

    if (
      s.includes("正在重置会话（写入长期记忆") ||
      low.includes("resetting session and saving long-term memory")
    ) {
      return t.cmdResetProgressWithMemory;
    }
    if (
      s.includes("正在重置会话（不写入长期记忆") ||
      low.includes("resetting session (without writing long-term memory")
    ) {
      return t.cmdResetProgressNoMemory;
    }
    if (
      s.includes("会话已重置（本轮对话未写入长期记忆）") ||
      low.includes("session has been reset (this round was not written to long-term memory")
    ) {
      return t.cmdResetDoneNoMemory;
    }
    if (s.includes("会话已重置") || low.includes("session has been reset")) {
      const queued =
        s.includes("长期记忆将在后台保存") ||
        low.includes("saved in the background");
      return queued
        ? `${t.cmdResetDoneWithMemory}\n${t.cmdResetDoneQueued}`
        : t.cmdResetDoneWithMemory;
    }

    return s;
  };

  if (isCommand) {
    const commandText = localizeCommandContent(message.content || "");
    return (
      <div className="flex justify-center" data-testid="chat-message" data-role={message.role}>
        <div
          className="w-full max-w-2xl rounded-xl px-4 py-3 text-sm"
          style={{
            background: "var(--warning-bg)",
            border: "1px solid var(--border)",
            boxShadow: "var(--shadow-xs)",
          }}
        >
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--warning)" }}>
            {t.commandNoticeTitle}
          </div>
          <div className="whitespace-pre-wrap leading-relaxed" style={{ color: "var(--text)" }}>
            {commandText}
          </div>
        </div>
      </div>
    );
  }

  if (isSystem) {
    return (
      <div className="group flex gap-3" data-testid="chat-message" data-role={message.role}>
        {hideAvatar ? (
          <div className="w-8 flex-shrink-0" />
        ) : (
          <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5"
            style={{ background: "var(--info-bg)", color: "var(--info)" }}>
            <Info className="w-4 h-4" />
          </div>
        )}
        <div className="min-w-0 max-w-[80%]">
          <div className="inline-block rounded-2xl rounded-tl-md px-4 py-2.5 text-sm leading-relaxed"
            style={{ background: "var(--info-bg)", border: "1px solid var(--border)", color: "var(--text)" }}>
            <div className="markdown-body prose prose-sm max-w-none" style={{ color: "var(--text)" }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content || ""}</ReactMarkdown>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const hasToolCalls = (message.toolCalls || []).some(tc => (tc.tool || tc.name));
  const isEmpty = !message.content && !message.isStreaming && !hasToolCalls;
  const isTextToolCall = !isUser && message.content?.startsWith("functions.");

  const toolName = (tc: { tool?: string; name?: string }) => tc.tool || tc.name || "";
  const spawnCalls = (message.toolCalls || []).filter(tc => toolName(tc) === "sessions_spawn");
  const nonSpawnCalls = (message.toolCalls || []).filter(tc => toolName(tc) !== "sessions_spawn");

  return (
    <div className={`group flex gap-3 ${isUser ? "flex-row-reverse" : ""}`} data-testid="chat-message" data-role={message.role}>
      {/* Avatar */}
      {hideAvatar ? (
        <div className="w-8 flex-shrink-0" />
      ) : (
        <div className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5 transition-shadow duration-200 ${isUser
            ? "bg-gradient-to-br from-[var(--accent)] to-blue-500 text-white"
            : ""
          }`}
          style={
            isUser
              ? { boxShadow: "var(--shadow-xs)" }
              : { background: "var(--hover)", color: "var(--text-secondary)" }
          }
        >
          {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
        </div>
      )}

      {/* Content */}
      <div className={`min-w-0 max-w-[80%] ${isUser ? "text-right" : ""}`}>
        {/* Tool calls (non-spawn) */}
        {nonSpawnCalls.length > 0 && <ThoughtChain toolCalls={nonSpawnCalls} />}

        {/* Subagent spawns */}
        {spawnCalls.map((tc, i) => {
          let runId = "";
          try {
            const parsed = typeof tc.output === "string" ? JSON.parse(tc.output) : tc.output;
            runId = parsed?.run_id || parsed?.content?.match?.(/run_id['":\s]+(\S+)/)?.[1] || "";
          } catch {
            const m = tc.output?.match?.(/run_id['":\s]+([^\s'"]+)/);
            if (m) runId = m[1];
          }
          const taskText = typeof tc.input === "object" ? (tc.input.task || tc.input.message || "") : String(tc.input).slice(0, 100);
          return runId ? <SubagentInlineCard key={`spawn-${i}`} runId={runId} task={taskText} /> : null;
        })}

        {isEmpty && (
          <div className="text-xs italic py-1" style={{ color: "var(--text-tertiary)" }}>
            ({t.noReplyYet})
          </div>
        )}

        {isTextToolCall && !hasToolCalls && (
          <div className="flex items-center gap-1.5 text-xs py-1" style={{ color: "var(--text-secondary)" }}>
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>{t.parsingToolCalls}</span>
          </div>
        )}

        {/* Message bubble */}
        {!isEmpty && !isTextToolCall && (message.content || (message.isStreaming && !hasToolCalls) || isUser) && (
          <div className="relative">
            <div className={`inline-block rounded-2xl px-4 py-2.5 text-sm leading-relaxed transition-shadow duration-200 ${isUser ? "rounded-tr-md" : "rounded-tl-md"
              }`}
              style={isUser ? {
                background: "linear-gradient(135deg, var(--accent) 0%, #2563eb 100%)",
                color: "var(--text-on-accent)",
                boxShadow: "var(--shadow-sm)",
              } : {
                background: "var(--glass-heavy)",
                backdropFilter: "blur(var(--blur-glass))",
                WebkitBackdropFilter: "blur(var(--blur-glass))",
                border: "1px solid var(--border)",
                color: "var(--text)",
                boxShadow: "var(--shadow-xs)",
              }}
            >
              {isUser ? (
                <p className="whitespace-pre-wrap text-left">{message.content}</p>
              ) : (
                <div className="markdown-body prose prose-sm max-w-none" style={{ color: "var(--text)" }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content || ""}</ReactMarkdown>
                </div>
              )}
              {message.isStreaming && (
                <span className="inline-flex gap-1 ml-1.5 items-center align-middle">
                  <span className="w-1 h-1 rounded-full animate-pulse-dot" style={{ background: isUser ? "rgba(255,255,255,0.7)" : "var(--text-secondary)", animationDelay: "0ms" }} />
                  <span className="w-1 h-1 rounded-full animate-pulse-dot" style={{ background: isUser ? "rgba(255,255,255,0.7)" : "var(--text-secondary)", animationDelay: "200ms" }} />
                  <span className="w-1 h-1 rounded-full animate-pulse-dot" style={{ background: isUser ? "rgba(255,255,255,0.7)" : "var(--text-secondary)", animationDelay: "400ms" }} />
                </span>
              )}

              {/* Copy button — inside bubble, bottom-right */}
              {!isUser && message.content && !message.isStreaming && (
                <button
                  onClick={handleCopy}
                  className="absolute bottom-1 right-1 opacity-0 group-hover:opacity-100 transition-all duration-200 p-1 rounded-md hover:bg-black/5"
                  style={{ color: "var(--text-tertiary)" }}
                  aria-label={t.copy}
                >
                  {copied
                    ? <Check className="w-3 h-3" style={{ color: "var(--success)" }} />
                    : <Copy className="w-3 h-3" />}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Metadata */}
        {!isUser && isLast && !message.isStreaming && (
          <div className="mt-2 text-[10px] flex items-center gap-3" style={{ color: "var(--text-tertiary)" }}>
            {timeLabel && <span>{timeLabel}</span>}
            {durationSeconds != null && <span>{durationSeconds.toFixed(1)}s</span>}
            {message.usage && (message.usage.input_tokens > 0 || message.usage.output_tokens > 0) && (
              <span>
                {message.usage.input_tokens.toLocaleString()} in / {message.usage.output_tokens.toLocaleString()} out
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
