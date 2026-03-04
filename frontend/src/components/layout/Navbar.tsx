"use client";

import { useState, useRef, useEffect } from "react";
import { useApp } from "@/lib/store";
import * as api from "@/lib/api";
import {
  Bot, Settings, ChevronDown, Sun, Moon, Monitor,
  Activity, Zap, RefreshCw, Languages,
} from "lucide-react";
import type { Locale } from "@/lib/i18n/locales";

export default function Navbar() {
  const {
    agents, currentAgentId, switchAgent, currentModel,
    setShowConfigModal, theme, setTheme,
    isStreaming, runningSubagents, lastUsage,
    locale, setLocale, t,
  } = useApp();

  const [showAgentMenu, setShowAgentMenu] = useState(false);
  const [showThemeMenu, setShowThemeMenu] = useState(false);
  const [showLocaleMenu, setShowLocaleMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const themeRef = useRef<HTMLDivElement>(null);
  const localeRef = useRef<HTMLDivElement>(null);
  const currentAgent = agents.find((a: any) => a.id === currentAgentId);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (menuRef.current && !menuRef.current.contains(target)) setShowAgentMenu(false);
      if (themeRef.current && !themeRef.current.contains(target)) setShowThemeMenu(false);
      if (localeRef.current && !localeRef.current.contains(target)) setShowLocaleMenu(false);
    };
    if (showAgentMenu || showThemeMenu || showLocaleMenu) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showAgentMenu, showThemeMenu, showLocaleMenu]);

  const ThemeIcon = theme === "dark" ? Moon : theme === "light" ? Sun : Monitor;
  const subagentCount = runningSubagents?.length || 0;

  return (
    <nav className="relative z-50 h-12 px-3 flex items-center justify-between flex-shrink-0 glass-heavy"
      style={{ borderBottom: "1px solid var(--border)" }}>

      {/* ---- Left: Brand + Agent Switcher ---- */}
      <div className="flex items-center gap-2.5">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[var(--accent)] to-blue-500 flex items-center justify-center flex-shrink-0"
            style={{ boxShadow: "var(--shadow-glow)" }}>
            <Bot className="w-4 h-4 text-white" />
          </div>
          <span className="font-semibold text-[var(--text)] text-[13px] tracking-tight hidden sm:inline">
            ClawChain
          </span>
        </div>

        <div className="w-px h-5" style={{ background: "var(--border)" }} />

        {/* Agent Switcher */}
        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => setShowAgentMenu(!showAgentMenu)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-[13px] text-[var(--text)] font-medium transition-all rounded-lg"
            style={{ background: showAgentMenu ? "var(--hover)" : "transparent" }}
            onMouseEnter={e => (e.currentTarget.style.background = "var(--hover)")}
            onMouseLeave={e => (e.currentTarget.style.background = showAgentMenu ? "var(--hover)" : "transparent")}
          >
            <span>{currentAgent?.name || currentAgentId}</span>
            <ChevronDown className={`w-3.5 h-3.5 text-[var(--text-secondary)] transition-transform duration-200 ${showAgentMenu ? "rotate-180" : ""}`} />
          </button>
          {showAgentMenu && (
            <div className="absolute left-0 top-full mt-1.5 z-50 min-w-[200px] dropdown-menu animate-scale-in">
              {agents.map((a: any) => (
                <button
                  key={a.id}
                  onClick={() => { switchAgent(a.id); setShowAgentMenu(false); }}
                  className={`dropdown-item ${a.id === currentAgentId ? "dropdown-item--active" : ""}`}
                >
                  <div className="min-w-0">
                    <div className="font-medium truncate">{a.name || a.id}</div>
                    {a.description && <div className="text-[10px] text-[var(--text-tertiary)] mt-0.5 truncate">{a.description}</div>}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ---- Center: Status Chips ---- */}
      <div className="flex items-center gap-2">
        {currentModel?.name && (
          <button onClick={() => setShowConfigModal(true)} className="chip chip--accent" data-testid="model-chip">
            <Zap className="w-3 h-3" />
            <span>{currentModel.name}</span>
          </button>
        )}

        {isStreaming && (
          <div className="chip chip--accent">
            <RefreshCw className="w-3 h-3 animate-spin" />
            <span>{t.generating}</span>
          </div>
        )}

        {subagentCount > 0 && (
          <div className="chip" style={{ background: "var(--info-bg)", color: "var(--info)", borderColor: "transparent" }}>
            <Activity className="w-3 h-3" />
            <span>{subagentCount} {t.subagentCount}</span>
          </div>
        )}

        {!isStreaming && lastUsage && (
          <span className="text-[10px] text-[var(--text-tertiary)] hidden md:inline tabular-nums">
            {lastUsage.input_tokens ? `${(lastUsage.input_tokens / 1000).toFixed(1)}k in` : ""}
            {lastUsage.output_tokens ? ` / ${(lastUsage.output_tokens / 1000).toFixed(1)}k out` : ""}
            {lastUsage.duration_ms ? ` · ${(lastUsage.duration_ms / 1000).toFixed(1)}s` : ""}
          </span>
        )}
      </div>

      {/* ---- Right: Theme + Settings ---- */}
      <div className="flex items-center gap-0.5">
        <div className="relative" ref={themeRef}>
          <button
            type="button"
            onClick={() => setShowThemeMenu(v => !v)}
            className="btn-ghost p-2"
            aria-label="切换主题"
          >
            <ThemeIcon className="w-4 h-4" />
          </button>
          {showThemeMenu && (
            <div className="absolute right-0 top-full mt-1.5 z-50 min-w-[140px] dropdown-menu animate-scale-in">
              {([
                { key: "system" as const, label: "跟随系统", icon: Monitor },
                { key: "light" as const, label: "明亮", icon: Sun },
                { key: "dark" as const, label: "深色", icon: Moon },
              ]).map((opt) => (
                <button
                  key={opt.key}
                  className={`dropdown-item ${theme === opt.key ? "dropdown-item--active" : ""}`}
                  onClick={() => { setTheme(opt.key); setShowThemeMenu(false); }}
                >
                  <opt.icon className="w-3.5 h-3.5" />
                  <span>{opt.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="relative" ref={localeRef}>
          <button
            type="button"
            onClick={() => setShowLocaleMenu(v => !v)}
            className="btn-ghost p-2"
            aria-label="切换语言"
            title={locale === "zh-CN" ? "简体中文" : "English"}
          >
            <Languages className="w-4 h-4" />
          </button>
          {showLocaleMenu && (
            <div className="absolute right-0 top-full mt-1.5 z-50 min-w-[120px] dropdown-menu animate-scale-in">
              {([
                { key: "zh-CN" as Locale, label: "简体中文" },
                { key: "en-US" as Locale, label: "English" },
              ]).map((opt) => (
                <button
                  key={opt.key}
                  className={`dropdown-item ${locale === opt.key ? "dropdown-item--active" : ""}`}
                  onClick={() => {
                    setLocale(opt.key);
                    api.updateConfig({ app: { locale: opt.key } }).catch(() => {});
                    setShowLocaleMenu(false);
                  }}
                >
                  <span>{opt.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={() => setShowConfigModal(true)}
          className="btn-ghost p-2"
          aria-label="设置"
          data-testid="config-btn"
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </nav>
  );
}
