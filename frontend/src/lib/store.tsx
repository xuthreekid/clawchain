"use client";

import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from "react";
import * as api from "./api";
import type { TokenUsage } from "./api";
import { useChat } from "./hooks/useChat";
import { useTheme } from "./hooks/useTheme";
import { useSubagents } from "./hooks/useSubagents";
import { type Locale, type Messages, getMessages } from "./i18n/locales";

export type { ChatMessage, LifecycleEvent } from "./hooks/useChat";
export type { ThemeMode, EffectiveTheme } from "./hooks/useTheme";
export type { Locale, Messages } from "./i18n/locales";

export interface UiNotice {
  kind: "success" | "error" | "info";
  text: string;
}

interface AppState {
  // Agent
  agents: any[];
  currentAgentId: string;
  currentSessionId: string | null;
  currentModel: any | null;

  // Chat (from useChat)
  messages: ReturnType<typeof useChat>["messages"];
  isStreaming: boolean;
  lifecycleEvents: ReturnType<typeof useChat>["lifecycleEvents"];
  lastUsage: TokenUsage | null;
  sessionError: string | null;
  sendMessage: (text: string) => Promise<void>;
  stopStreaming: () => void;

  // Config
  ragMode: boolean;
  setRagMode: (enabled: boolean) => Promise<void>;

  // Inspector
  inspectorWidth: number;
  setInspectorWidth: (w: number) => void;
  inspectorPanelMode: "docked" | "overlay" | "hidden";
  setInspectorPanelMode: (mode: "docked" | "overlay" | "hidden") => void;
  inspectorTab: string;
  setInspectorTab: (tab: any) => void;
  inspectorFile: { path: string; content: string } | null;
  inspectorFileLoading: boolean;
  openFile: (path: string) => Promise<void>;
  saveInspectorFile: (content: string) => Promise<void>;

  // Subagents
  runningSubagents: { run_id: string; task: string; status: string }[];

  // UI
  showConfigModal: boolean;
  setShowConfigModal: (v: boolean) => void;
  theme: "system" | "light" | "dark";
  effectiveTheme: "light" | "dark";
  setTheme: (mode: "system" | "light" | "dark") => void;
  uiNotice: UiNotice | null;
  showNotice: (notice: UiNotice) => void;
  clearNotice: () => void;

  // Exec approval
  pendingApproval: { approval_id: string; tool: string; input_preview: string } | null;
  setPendingApproval: (v: { approval_id: string; tool: string; input_preview: string } | null) => void;

  // i18n
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: Messages;

  // Actions
  loadAgents: () => Promise<void>;
  switchAgent: (agentId: string) => Promise<void>;
  loadMainSession: () => Promise<void>;
  skillsRefreshTrigger: number;
  triggerSkillsRefresh: () => void;
}

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [agents, setAgents] = useState<any[]>([]);
  const [currentAgentId, setCurrentAgentId] = useState("main");
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [currentModel, setCurrentModel] = useState<any | null>(null);
  const [ragMode, setRagModeState] = useState(false);
  const [inspectorWidth, setInspectorWidth] = useState(380);
  const [inspectorPanelMode, setInspectorPanelMode] = useState<"docked" | "overlay" | "hidden">("docked");
  const [inspectorFile, setInspectorFile] = useState<{ path: string; content: string } | null>(null);
  const [inspectorFileLoading, setInspectorFileLoading] = useState(false);
  const [inspectorTab, setInspectorTab] = useState<string>("files");
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [uiNotice, setUiNotice] = useState<UiNotice | null>(null);
  const [skillsRefreshTrigger, setSkillsRefreshTrigger] = useState(0);
  const [pendingApproval, setPendingApproval] = useState<{ approval_id: string; tool: string; input_preview: string } | null>(null);
  const lastLifecycleNoticeKeyRef = useRef("");

  const [locale, setLocaleState] = useState<Locale>("zh-CN");
  const t = getMessages(locale);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const saved = window.localStorage.getItem("clawchain.locale");
      if (saved === "zh-CN" || saved === "en-US") setLocaleState(saved);
    } catch {}
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try { window.localStorage.setItem("clawchain.locale", l); } catch {}
  }, []);

  // 持久化 currentAgentId（Hydration 安全：初始 "main"，useEffect 恢复）
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const saved = window.localStorage.getItem("clawchain.agent");
      if (saved && typeof saved === "string" && saved.trim()) {
        setCurrentAgentId(saved.trim());
      }
    } catch {
      // ignore
    }
  }, []);

  // 持久化侧栏布局偏好（模式 + 宽度）
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const savedMode = window.localStorage.getItem("clawchain.inspector.mode");
      if (savedMode === "docked" || savedMode === "overlay" || savedMode === "hidden") {
        setInspectorPanelMode(savedMode);
      }
      const savedWidth = Number(window.localStorage.getItem("clawchain.inspector.width") || "");
      if (Number.isFinite(savedWidth) && savedWidth >= 280 && savedWidth <= 720) {
        setInspectorWidth(savedWidth);
      }
    } catch {
      // ignore localStorage errors
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem("clawchain.inspector.mode", inspectorPanelMode);
    } catch {
      // ignore localStorage errors
    }
  }, [inspectorPanelMode]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem("clawchain.inspector.width", String(inspectorWidth));
    } catch {
      // ignore localStorage errors
    }
  }, [inspectorWidth]);

  const triggerSkillsRefresh = useCallback(() => setSkillsRefreshTrigger((n) => n + 1), []);
  const formatCommandResponse = useCallback((raw: string) => {
    const s = (raw || "").trim();
    if (!s) return s;

    const helpLines = [
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
      return helpLines;
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
      // 保留后端详细数字信息，仅统一首行标题。
      const lines = s.split("\n");
      if (lines.length > 1) return `${t.cmdCompactDone}\n${lines.slice(1).join("\n")}`;
      return t.cmdCompactDone;
    }
    if (s.startsWith("压缩失败") || low.startsWith("compaction failed")) {
      return `${t.cmdCompactFailed}\n${s}`;
    }

    // /new /reset progress + result messages from backend; normalize to locale text
    if (s.includes("正在重置会话（写入长期记忆") || low.includes("resetting session and saving long-term memory")) {
      return t.cmdResetProgressWithMemory;
    }
    if (s.includes("正在重置会话（不写入长期记忆") || low.includes("resetting session (without writing long-term memory")) {
      return t.cmdResetProgressNoMemory;
    }
    if (s.includes("会话已重置（本轮对话未写入长期记忆）") || low.includes("session has been reset (this round was not written")) {
      return t.cmdResetDoneNoMemory;
    }
    if (s.includes("会话已重置")) {
      const queued = s.includes("长期记忆将在后台保存") || low.includes("saved in the background");
      return queued
        ? `${t.cmdResetDoneWithMemory}\n${t.cmdResetDoneQueued}`
        : t.cmdResetDoneWithMemory;
    }
    return s;
  }, [t]);

  const { theme, effectiveTheme, setTheme } = useTheme();

  const loadAgents = useCallback(async () => {
    const data = await api.fetchAgents();
    setAgents(data);
  }, []);

  const loadMainSession = useCallback(async () => {
    try {
      const session = await api.fetchMainSession(currentAgentId);
      setCurrentSessionId(session.session_id);
      chat.loadMessages(currentAgentId, session.session_id);
      const model = await api.fetchCurrentModel(currentAgentId);
      setCurrentModel(model);
    } catch {
      chat.setMessages([]);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentAgentId]);

  const chat = useChat(
    currentAgentId,
    currentSessionId,
    setCurrentSessionId,
    {
      onAgentCreated: loadAgents,
      onSessionCompacted: loadMainSession,
      onTurnComplete: triggerSkillsRefresh,
      formatCommandResponse,
    },
  );

  const { runningSubagents } = useSubagents(
    currentAgentId,
    currentSessionId,
    loadMainSession,
  );

  // 订阅 Agent 事件：技能热加载、危险工具执行提示、exec 确认、心跳/定时消息
  useEffect(() => {
    if (!currentAgentId) return;
    const unsub = api.subscribeAgentEvents(currentAgentId, (event) => {
      if (event.type === "lifecycle" && event.event === "skills_updated") {
        triggerSkillsRefresh();
      }
      if (event.type === "heartbeat_message") {
        loadMainSession();
      }
      if (event.type === "lifecycle" && event.event === "approval_required") {
        const ev = event as any;
        const aid = ev.approval_id || "";
        const tool = ev.tool || "exec";
        const preview = ev.input_preview || "";
        if (aid) setPendingApproval({ approval_id: aid, tool, input_preview: preview });
      }
    });
    return unsub;
  }, [currentAgentId, triggerSkillsRefresh, loadMainSession]);

  const switchAgent = useCallback(async (agentId: string) => {
    setCurrentAgentId(agentId);
    try { window.localStorage.setItem("clawchain.agent", agentId); } catch {}
    setCurrentSessionId(null);
    setInspectorFile(null);
    setInspectorFileLoading(false);
    chat.clearChat();

    try {
      const session = await api.fetchMainSession(agentId);
      setCurrentSessionId(session.session_id);
      chat.loadMessages(agentId, session.session_id);
      const model = await api.fetchCurrentModel(agentId);
      setCurrentModel(model);
    } catch {
      chat.setMessages([]);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setRagMode = useCallback(async (enabled: boolean) => {
    await api.updateRagMode(enabled);
    setRagModeState(enabled);
  }, []);

  const openFile = useCallback(async (path: string) => {
    setInspectorFileLoading(true);
    setInspectorTab("files");
    try {
      const data = await api.readFile(currentAgentId, path);
      setInspectorFile(data);
    } catch {
      setInspectorFile({ path, content: "（无法读取文件）" });
    } finally {
      setInspectorFileLoading(false);
    }
  }, [currentAgentId]);

  const saveInspectorFile = useCallback(async (content: string) => {
    if (!inspectorFile) return;
    await api.saveFile(currentAgentId, inspectorFile.path, content);
    setInspectorFile({ ...inspectorFile, content });
  }, [currentAgentId, inspectorFile]);

  const showNotice = useCallback((notice: UiNotice) => setUiNotice(notice), []);
  const clearNotice = useCallback(() => setUiNotice(null), []);

  useEffect(() => {
    if (!chat.lifecycleEvents.length) return;
    const last = chat.lifecycleEvents[chat.lifecycleEvents.length - 1];
    if (!last) return;
    const data = (last.data || {}) as any;
    const key = `${last.event}|${data.session_id || ""}|${data.path || ""}|${data.reason || ""}|${last.timestamp}`;
    if (lastLifecycleNoticeKeyRef.current === key) return;
    lastLifecycleNoticeKeyRef.current = key;

    if (last.event === "session_memory_saved") {
      const path = data.path ? `（${data.path}）` : "";
      showNotice({ kind: "success", text: `长期记忆已后台保存${path}` });
      return;
    }
    if (last.event === "session_memory_failed") {
      const reason = data.reason ? `：${String(data.reason)}` : "";
      showNotice({ kind: "error", text: `长期记忆后台保存失败${reason}` });
    }
  }, [chat.lifecycleEvents, showNotice]);

  const value: AppState = {
    agents,
    currentAgentId,
    currentSessionId,
    currentModel,

    messages: chat.messages,
    isStreaming: chat.isStreaming,
    lifecycleEvents: chat.lifecycleEvents,
    lastUsage: chat.lastUsage,
    sessionError: chat.sessionError,
    sendMessage: chat.sendMessage,
    stopStreaming: chat.stopStreaming,

    ragMode,
    setRagMode,

    inspectorWidth,
    setInspectorWidth,
    inspectorPanelMode,
    setInspectorPanelMode,
    inspectorTab,
    setInspectorTab,
    inspectorFile,
    inspectorFileLoading,
    openFile,
    saveInspectorFile,

    runningSubagents,

    showConfigModal,
    setShowConfigModal,
    theme,
    effectiveTheme,
    setTheme,
    uiNotice,
    showNotice,
    clearNotice,

    pendingApproval,
    setPendingApproval,

    locale,
    setLocale,
    t,

    loadAgents,
    switchAgent,
    loadMainSession,
    skillsRefreshTrigger,
    triggerSkillsRefresh,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used inside AppProvider");
  return ctx;
}
