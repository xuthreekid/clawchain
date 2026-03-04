"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useApp } from "@/lib/store";
import { FileText, Save, FolderOpen, Sparkles, Users, Wrench, Heart, ChevronRight, RefreshCw, PanelRightClose, ListTodo, ToggleLeft, ToggleRight } from "lucide-react";
import * as api from "@/lib/api";
import type { Messages } from "@/lib/i18n/locales";
import dynamic from "next/dynamic";
import SubagentPanel from "@/components/inspector/SubagentPanel";
import HeartbeatPanel from "@/components/inspector/HeartbeatPanel";
import EventTimeline from "@/components/inspector/EventTimeline";
import TaskDashboard from "@/components/inspector/TaskDashboard";
import SkillsPanel from "@/components/skills/SkillsPanel";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

const WORKSPACE_FILES = [
  { path: "workspace/SOUL.md", label: "SOUL.md" },
  { path: "workspace/IDENTITY.md", label: "IDENTITY.md" },
  { path: "workspace/USER.md", label: "USER.md" },
  { path: "workspace/AGENTS.md", label: "AGENTS.md" },
  { path: "workspace/TOOLS.md", label: "TOOLS.md" },
  { path: "workspace/HEARTBEAT.md", label: "HEARTBEAT.md" },
  { path: "workspace/MEMORY.md", label: "MEMORY.md" },
  { path: "SKILLS_SNAPSHOT.md", label: "SKILLS_SNAPSHOT" },
];

function getCategoryLabel(cat: string, t: Messages): string {
  const map: Record<string, string> = {
    file: t.categoryFile,
    runtime: t.categoryRuntime,
    web: t.categoryWeb,
    memory: t.categoryMemory,
    knowledge: t.categoryKnowledge,
    agent: t.categoryAgent,
    status: t.categoryStatus,
    other: t.categoryOther,
  };
  return map[cat] || cat;
}

type TabId = "files" | "tools" | "skills" | "subagents" | "heartbeat" | "tasks";

const TAB_DEFS: { id: TabId; labelKey: string; icon: any }[] = [
  { id: "files", labelKey: "tabFiles", icon: FolderOpen },
  { id: "tools", labelKey: "tabTools", icon: Wrench },
  { id: "skills", labelKey: "tabSkills", icon: Sparkles },
  { id: "subagents", labelKey: "tabSubagents", icon: Users },
  { id: "heartbeat", labelKey: "tabHeartbeat", icon: Heart },
  { id: "tasks", labelKey: "tabTasks", icon: ListTodo },
];

export default function InspectorPanel() {
  const {
    currentAgentId, inspectorFile, inspectorFileLoading, openFile, saveInspectorFile,
    inspectorTab, setInspectorTab, effectiveTheme, inspectorPanelMode, setInspectorPanelMode,
    showNotice, t,
  } = useApp();
  const [editedContent, setEditedContent] = useState("");
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    if (inspectorFile) {
      setEditedContent(inspectorFile.content);
      setHasChanges(false);
    }
  }, [inspectorFile]);

  const handleSave = async () => {
    await saveInspectorFile(editedContent);
    setHasChanges(false);
  };

  const activeTab = inspectorTab as TabId;

  return (
    <div className="h-full flex flex-col" style={{ background: "var(--glass-heavy)", backdropFilter: "blur(var(--blur-glass))" }} data-testid="inspector-panel">
      {/* Tab bar */}
      <div className="flex flex-shrink-0 items-stretch" style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="flex flex-1 min-w-0">
          {TAB_DEFS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            const label = (t as any)[tab.labelKey] || tab.labelKey;
            return (
              <button
                key={tab.id}
                onClick={() => setInspectorTab(tab.id)}
                className="flex items-center justify-center px-2.5 py-2 transition-all duration-200 relative"
                data-testid={`inspector-tab-${tab.id}`}
                title={label}
                style={{
                  color: isActive ? "var(--accent)" : "var(--text-secondary)",
                  background: isActive ? "var(--accent-muted)" : "transparent",
                  borderRadius: "6px",
                }}
                onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = "var(--hover)"; }}
                onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = "transparent"; }}
              >
                <Icon className="w-4 h-4" />
                {isActive && (
                  <div className="absolute bottom-0 left-1.5 right-1.5 h-0.5 rounded-full" style={{ background: "var(--accent)" }} />
                )}
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-0.5 px-1" style={{ borderLeft: "1px solid var(--border)" }}>
          <button
            onClick={() => setInspectorPanelMode("hidden")}
            className="btn-ghost p-1 rounded-md opacity-70 hover:opacity-100 transition-opacity"
            title="收起面板"
          >
            <PanelRightClose className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0">
        {activeTab === "files" && (
          <FilesTab
            inspectorFile={inspectorFile}
            inspectorFileLoading={inspectorFileLoading}
            openFile={openFile}
            editedContent={editedContent}
            setEditedContent={setEditedContent}
            hasChanges={hasChanges}
            setHasChanges={setHasChanges}
            handleSave={handleSave}
            effectiveTheme={effectiveTheme}
            t={t}
          />
        )}
        {activeTab === "tools" && (
          <ToolsTab
            currentAgentId={currentAgentId}
            t={t}
            onError={(msg) => showNotice({ kind: "error", text: msg })}
          />
        )}
        {activeTab === "skills" && (
          <div className="flex-1 min-h-0 h-full flex flex-col">
            <SkillsPanel />
          </div>
        )}
        {activeTab === "subagents" && (
          <div className="flex-1 min-h-0 h-full overflow-y-auto p-3">
            <SubagentPanel />
          </div>
        )}
        {activeTab === "heartbeat" && (
          <div className="flex-1 min-h-0 h-full flex flex-col overflow-y-auto">
            <HeartbeatPanel />
            <div className="px-3 pb-3">
              <div className="text-[10px] uppercase tracking-wider font-semibold mb-2 px-1" style={{ color: "var(--text-tertiary)" }}>
                {t.runtimeEvents}
              </div>
              <EventTimeline />
            </div>
          </div>
        )}
        {activeTab === "tasks" && (
          <div className="flex-1 min-h-0 h-full flex flex-col">
            <TaskDashboard agentId={currentAgentId} />
          </div>
        )}
      </div>
    </div>
  );
}

function FilesTab({
  inspectorFile, inspectorFileLoading, openFile,
  editedContent, setEditedContent, hasChanges, setHasChanges,
  handleSave, effectiveTheme, t,
}: {
  inspectorFile: { path: string; content: string } | null;
  inspectorFileLoading: boolean;
  openFile: (path: string) => Promise<void>;
  editedContent: string;
  setEditedContent: (v: string) => void;
  hasChanges: boolean;
  setHasChanges: (v: boolean) => void;
  handleSave: () => Promise<void>;
  effectiveTheme: "light" | "dark";
  t: Messages;
}) {
  return (
    <div className="h-full flex flex-col">
      <div className="p-3 overflow-y-auto flex-shrink-0" style={{ maxHeight: "40%", borderBottom: "1px solid var(--border)" }}>
        <div className="text-[10px] font-semibold uppercase tracking-wider mb-2 px-1" style={{ color: "var(--text-tertiary)" }}>
          {t.keyFiles}
        </div>
        <div className="space-y-0.5">
          {WORKSPACE_FILES.map((f) => (
            <button
              key={f.path}
              onClick={() => openFile(f.path)}
              className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs flex items-center gap-2 transition-all duration-150"
              style={{
                background: inspectorFile?.path === f.path ? "var(--accent-muted)" : "transparent",
                color: inspectorFile?.path === f.path ? "var(--accent)" : "var(--text-secondary)",
                fontWeight: inspectorFile?.path === f.path ? 500 : 400,
              }}
              onMouseEnter={e => { if (inspectorFile?.path !== f.path) e.currentTarget.style.background = "var(--hover)"; }}
              onMouseLeave={e => { if (inspectorFile?.path !== f.path) e.currentTarget.style.background = "transparent"; }}
            >
              <FileText className="w-3 h-3 flex-shrink-0 opacity-50" />
              <span className="truncate">{f.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 min-h-0 flex flex-col">
        {inspectorFileLoading ? (
          <div className="flex-1 flex items-center justify-center text-[var(--text-secondary)] text-xs">
            {t.loading}
          </div>
        ) : inspectorFile ? (
          <>
            <div className="flex items-center justify-between px-3 py-1.5 flex-shrink-0"
              style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-inset)" }}>
              <span className="text-[11px] truncate font-mono" style={{ color: "var(--text-secondary)" }}>{inspectorFile.path}</span>
              {hasChanges && (
                <button onClick={handleSave} className="btn-primary" style={{ padding: "3px 10px", fontSize: 11 }}>
                  <Save className="w-3 h-3" />
                  {t.save}
                </button>
              )}
            </div>
            <div className="flex-1 min-h-0">
              <MonacoEditor
                height="100%"
                language="markdown"
                theme={effectiveTheme === "dark" ? "vs-dark" : "vs"}
                value={editedContent}
                onChange={(val: string | undefined) => {
                  setEditedContent(val || "");
                  setHasChanges(true);
                }}
                loading={<div className="flex items-center justify-center h-full text-[var(--text-secondary)] text-xs">加载编辑器...</div>}
                options={{
                  minimap: { enabled: false },
                  fontSize: 12,
                  lineNumbers: "on",
                  wordWrap: "on",
                  scrollBeyondLastLine: false,
                  padding: { top: 8 },
                  automaticLayout: true,
                  overviewRulerBorder: false,
                  scrollbar: { verticalScrollbarSize: 6, horizontalScrollbarSize: 6 },
                }}
              />
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-[var(--text-tertiary)] text-xs">
            {t.clickFileToEdit}
          </div>
        )}
      </div>
    </div>
  );
}

function ToolsTab({ currentAgentId, t, onError }: { currentAgentId: string; t: Messages; onError?: (msg: string) => void }) {
  const [tools, setTools] = useState<api.ToolItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [toggling, setToggling] = useState<string | null>(null);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  const refreshTools = useCallback(() => {
    api.fetchTools(currentAgentId).then(setTools).catch((e: any) => {
      setTools([]);
      onErrorRef.current?.(`加载工具列表失败: ${e?.message || "未知错误"}`);
    }).finally(() => setLoading(false));
  }, [currentAgentId]);

  useEffect(() => {
    setLoading(true);
    refreshTools();
  }, [currentAgentId, refreshTools]);

  const handleToggleTool = async (t: api.ToolItem) => {
    if (toggling === t.name) return;
    setToggling(t.name);
    try {
      await api.updateToolPolicy(currentAgentId, t.name, !t.allowed);
      setTools(prev => prev.map(x => x.name === t.name ? { ...x, allowed: !x.allowed } : x));
    } catch (e: any) {
      onError?.(`更新工具策略失败: ${e?.message || "未知错误"}`);
    } finally {
      setToggling(null);
    }
  };

  if (loading) return <div className="p-4 text-[var(--text-secondary)] text-xs text-center">{t.loading}</div>;

  const byCategory = tools.reduce<Record<string, api.ToolItem[]>>((acc, t) => {
    const cat = t.category || "other";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(t);
    return acc;
  }, {});

  const toggleCategory = (cat: string) => {
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  return (
    <div className="h-full overflow-y-auto p-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider mb-3 px-1" style={{ color: "var(--text-tertiary)" }}>
        {t.toolsTitle} ({tools.length})
      </div>
      <div className="space-y-1">
        {Object.entries(byCategory).map(([cat, list]) => {
          const isCollapsed = collapsed.has(cat);
          return (
            <div key={cat}>
              <button
                onClick={() => toggleCategory(cat)}
                className="w-full flex items-center gap-1.5 px-1 py-1 text-left rounded-lg transition-colors"
                onMouseEnter={e => (e.currentTarget.style.background = "var(--hover)")}
                onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
              >
                <ChevronRight className={`w-3 h-3 text-[var(--text-secondary)] transition-transform duration-200 ${isCollapsed ? "" : "rotate-90"}`} />
                <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--text-secondary)" }}>
                  {getCategoryLabel(cat, t)}
                </span>
                <span className="text-[10px] opacity-60 ml-auto" style={{ color: "var(--text-secondary)" }}>{list.length}</span>
              </button>
              <div className={`grid transition-all duration-200 ease-out ${isCollapsed ? "grid-rows-[0fr]" : "grid-rows-[1fr]"}`}>
                <div className="overflow-hidden">
                  <div className="space-y-0.5 pl-4 mt-0.5 mb-1.5">
                    {list.map((tool) => (
                      <div key={tool.name} className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs group transition-colors"
                        onMouseEnter={e => (e.currentTarget.style.background = "var(--hover)")}
                        onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="font-mono text-[var(--text)] text-[11px]">{tool.name}</div>
                          {tool.description && (
                            <div className="text-[10px] mt-0.5 line-clamp-1 group-hover:line-clamp-3 transition-all" style={{ color: "var(--text-secondary)" }}>{tool.description}</div>
                          )}
                        </div>
                        <button
                          onClick={() => handleToggleTool(tool)}
                          disabled={toggling === tool.name}
                          className="p-0.5 opacity-60 hover:opacity-100 transition-opacity flex-shrink-0 disabled:opacity-40"
                          title={tool.allowed ? t.clickToDisable : t.clickToEnable}
                        >
                          {tool.allowed ? (
                            <ToggleRight className="w-4 h-4" style={{ color: "var(--success)" }} />
                          ) : (
                            <ToggleLeft className="w-4 h-4" style={{ color: "var(--text-tertiary)" }} />
                          )}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}


