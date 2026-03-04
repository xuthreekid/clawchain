"use client";

import { useRef, useEffect } from "react";
import { useApp } from "@/lib/store";
import ChatMessage from "./ChatMessage";
import ChatInput from "./ChatInput";
import RetrievalCard from "./RetrievalCard";
import { Bot, Activity } from "lucide-react";

export default function ChatPanel() {
  const {
    messages, currentSessionId, sessionError,
    currentAgentId, agents, runningSubagents, setInspectorTab, t,
  } = useApp();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const currentAgent = agents.find((a: any) => a.id === currentAgentId);

  if (!currentSessionId || messages.length === 0) {
    return (
      <div className="h-full flex flex-col" style={{ background: "var(--bg)" }} data-testid="chat-panel">
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center px-6 max-w-md animate-fade-in-up">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[var(--accent)] to-blue-500 flex items-center justify-center mx-auto mb-5"
              style={{ boxShadow: "var(--shadow-glow), var(--shadow-lg)" }}>
              <Bot className="w-8 h-8 text-white" />
            </div>
            <h2 className="text-xl font-semibold text-[var(--text)] mb-2">
              {currentAgent?.name || "ClawChain"}
            </h2>
            <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-6">
              {currentAgent?.description || t.agentDescription}
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {["记住这个", "查看今天的记忆", "帮我写代码", "搜索网页"].map((hint) => (
                <span key={hint} className="chip">{hint}</span>
              ))}
            </div>
            {sessionError && (
              <p className="mt-5 text-xs px-4 py-2.5 rounded-lg inline-block"
                style={{ background: "var(--error-bg)", color: "var(--error)" }}>
                {sessionError}
              </p>
            )}
          </div>
        </div>
        <ChatInput />
      </div>
    );
  }

  const lastAssistantIdx = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return i;
    }
    return -1;
  })();

  return (
    <div className="h-full flex flex-col" style={{ background: "var(--bg)" }} data-testid="chat-panel">
      {/* Subagent running banner */}
      {runningSubagents.length > 0 && (
        <div className="px-4 py-2 flex items-center gap-2 text-xs font-medium"
          style={{ background: "var(--warning-bg)", color: "var(--warning)", borderBottom: "1px solid var(--border)" }}>
          <Activity className="w-3.5 h-3.5" />
          <span>{runningSubagents.length} 个子 Agent 运行中</span>
          <button
            type="button"
            onClick={() => setInspectorTab("subagents")}
            className="ml-1 underline underline-offset-2 hover:no-underline transition-all"
          >
            查看详情
          </button>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-4">
          {messages.map((msg, i) => {
            const prev = i > 0 ? messages[i - 1] : null;
            const isContinuation = prev?.role === "assistant" && msg.role === "assistant";

            return (
              <div key={msg.id} className="animate-fade-in">
                {msg.retrievals && msg.retrievals.length > 0 && (
                  <div className="mb-2">
                    <RetrievalCard results={msg.retrievals} />
                  </div>
                )}
                <ChatMessage
                  message={msg}
                  hideAvatar={isContinuation}
                  isLast={i === lastAssistantIdx}
                />
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>
      </div>

      <ChatInput />
    </div>
  );
}
