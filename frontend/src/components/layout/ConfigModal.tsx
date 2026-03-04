"use client";

import { useEffect, useState, useCallback } from "react";
import { useApp } from "@/lib/store";
import {
  X, ToggleLeft, ToggleRight, Plus, Trash2,
  ChevronDown, ChevronRight, Save, AlertCircle,
  Eye, EyeOff, Server, Bot, Wrench, Database,
  Clock, Activity, Search, Settings2,
  Shield, Bell, Cpu, Globe, FolderArchive, Puzzle,
} from "lucide-react";
import * as api from "@/lib/api";
import dynamic from "next/dynamic";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

/* ───────────────────── Form Primitives ───────────────────── */

function Section({ title, icon, children, defaultOpen = true }: {
  title: string; icon?: React.ReactNode; children: React.ReactNode; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="glass-card overflow-hidden">
      <button
        type="button" onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2.5 transition-colors text-left"
        onMouseEnter={e => (e.currentTarget.style.background = "var(--hover)")}
        onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
      >
        {icon}
        <span className="text-[11px] font-semibold uppercase tracking-wider flex-1" style={{ color: "var(--text)" }}>{title}</span>
        {open
          ? <ChevronDown className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />
          : <ChevronRight className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />}
      </button>
      {open && <div className="p-3 space-y-2.5" style={{ borderTop: "1px solid var(--border)" }}>{children}</div>}
    </div>
  );
}

function Input({ label, value, onChange, type = "text", disabled = false, hint, placeholder }: {
  label: string; value: string; onChange: (v: string) => void;
  type?: string; disabled?: boolean; hint?: string; placeholder?: string;
}) {
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  return (
    <div>
      <label className="text-xs block mb-0.5" style={{ color: "var(--text)" }}>{label}</label>
      <input
        type={type} value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => { if (local !== value) onChange(local); }}
        disabled={disabled} placeholder={placeholder}
        className={`input text-xs ${disabled ? "opacity-55" : ""}`}
      />
      {hint && <p className="text-[10px] mt-0.5" style={{ color: "var(--text-secondary)" }}>{hint}</p>}
    </div>
  );
}

function SecretInput({ label, value, secretPath, hint, placeholder, onSaved }: {
  label: string; value: string; secretPath: string;
  hint?: string; placeholder?: string; onSaved?: () => void;
}) {
  const { showNotice } = useApp();
  const [editing, setEditing] = useState(false);
  const [local, setLocal] = useState("");
  const [show, setShow] = useState(false);
  const [saving, setSaving] = useState(false);
  const isMasked = value.includes("***");
  const hasValue = !!value && value !== "***";
  const displayValue = isMasked ? value : (value ? "••••••••" : "");

  const handleSave = async () => {
    if (!local.trim()) return;
    setSaving(true);
    try {
      await api.updateSecrets(secretPath, local.trim());
      setLocal("");
      setEditing(false);
      setShow(false);
      onSaved?.();
    } catch (e: any) {
      showNotice({ kind: "error", text: `保存失败: ${e.message}` });
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setLocal("");
    setEditing(false);
    setShow(false);
  };

  return (
    <div>
      <label className="text-xs block mb-0.5" style={{ color: "var(--text)" }}>{label}</label>
      <div className="flex gap-1.5">
        {editing ? (
          <div className="flex-1 flex gap-1">
            <input
              type={show ? "text" : "password"} value={local}
              onChange={(e) => setLocal(e.target.value)}
              placeholder={placeholder || "输入新的 API Key"}
              autoFocus
              className="input flex-1 text-xs" style={{ borderColor: "var(--accent)" }}
            />
            <button onClick={() => setShow(!show)} className="btn-ghost p-1.5" type="button">
              {show ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
            </button>
            <button onClick={handleSave} disabled={saving || !local.trim()} className="btn-primary" style={{ padding: "4px 8px" }} type="button">
              <Save className="w-3 h-3" />
            </button>
            <button onClick={handleCancel} className="btn-ghost" style={{ fontSize: 10 }} type="button">取消</button>
          </div>
        ) : (
          <div className="flex-1 flex items-center gap-1.5">
            <span className="flex-1 px-2.5 py-1.5 text-xs rounded-lg font-mono truncate"
              style={{ border: "1px solid var(--border)", background: "var(--bg-elevated)", color: hasValue ? "var(--text-secondary)" : "var(--text-tertiary)" }}>
              {displayValue || <span className="italic">未设置</span>}
            </span>
            <button onClick={() => setEditing(true)} className="btn-outline" style={{ fontSize: 10 }} type="button">
              {hasValue ? "修改" : "设置"}
            </button>
          </div>
        )}
      </div>
      {hint && <p className="text-[10px] mt-0.5" style={{ color: "var(--text-secondary)" }}>{hint}</p>}
    </div>
  );
}

function Select({ label, value, options, onChange, hint }: {
  label: string; value: string; options: { value: string; label: string }[];
  onChange: (v: string) => void;
  hint?: string;
}) {
  return (
    <div>
      <label className="text-xs block mb-0.5" style={{ color: "var(--text)" }}>{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="input text-xs">
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      {hint && <p className="text-[10px] mt-0.5" style={{ color: "var(--text-secondary)" }}>{hint}</p>}
    </div>
  );
}

function Toggle({ label, value, onChange }: {
  label: string; value: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs" style={{ color: "var(--text)" }}>{label}</span>
      <button onClick={() => onChange(!value)} className="transition-colors" type="button">
        {value
          ? <ToggleRight className="w-5 h-5" style={{ color: "var(--accent)" }} />
          : <ToggleLeft className="w-5 h-5" style={{ color: "var(--text-tertiary)" }} />}
      </button>
    </div>
  );
}

function Textarea({ label, value, onChange, rows = 3, hint }: {
  label: string; value: string; onChange: (v: string) => void;
  rows?: number; hint?: string;
}) {
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  return (
    <div>
      <label className="text-xs block mb-0.5" style={{ color: "var(--text)" }}>{label}</label>
      <textarea value={local} onChange={(e) => setLocal(e.target.value)}
        onBlur={() => { if (local !== value) onChange(local); }}
        rows={rows} className="input text-xs resize-y" />
      {hint && <p className="text-[10px] mt-0.5" style={{ color: "var(--text-secondary)" }}>{hint}</p>}
    </div>
  );
}

/* ───────────────────── Provider Editor ───────────────────── */

function ProviderEditor({ providerId, provider, onUpdate, onDelete, onSecretSaved }: {
  providerId: string; provider: any;
  onUpdate: (id: string, field: string, value: any) => void;
  onDelete: (id: string) => void;
  onSecretSaved: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [showModels, setShowModels] = useState(false);
  const [newModel, setNewModel] = useState({ id: "", name: "", contextWindow: "128000", maxTokens: "8192" });
  const [showAddModel, setShowAddModel] = useState(false);
  const models: any[] = provider.models || [];

  return (
    <div className="glass-inset rounded-lg overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2">
        <Server className="w-3.5 h-3.5" style={{ color: "var(--accent)" }} />
        <span className="text-xs font-medium flex-1" style={{ color: "var(--text)" }}>{providerId}</span>
        <span className="text-[10px]" style={{ color: "var(--text-secondary)" }}>{models.length} 模型</span>
        <button onClick={() => setExpanded(!expanded)} className="btn-ghost p-0.5" type="button">
          {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </button>
        <button onClick={() => { if (confirm(`确定删除 Provider "${providerId}"？`)) onDelete(providerId); }}
          className="btn-ghost p-0.5" type="button"
          style={{ color: "var(--text-secondary)" }}
          onMouseEnter={e => (e.currentTarget.style.color = "var(--error)")}
          onMouseLeave={e => (e.currentTarget.style.color = "var(--text-secondary)")}>
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {expanded && (
        <div className="px-3 pb-3 space-y-2" style={{ borderTop: "1px solid var(--border)" }}>
          <Input label="Base URL" value={provider.baseUrl || ""} onChange={(v) => onUpdate(providerId, "baseUrl", v)} placeholder="https://api.openai.com/v1" />
          <SecretInput label="API Key" value={provider.apiKey || ""} secretPath={`models.providers.${providerId}.apiKey`}
            hint="敏感信息独立保存，不会被普通配置覆盖" onSaved={onSecretSaved} />
          <Select label="API 协议" value={provider.api || "openai-completions"} options={[
            { value: "openai-completions", label: "OpenAI Completions" },
            { value: "anthropic-messages", label: "Anthropic Messages" },
            { value: "ollama", label: "Ollama" },
          ]} onChange={(v) => onUpdate(providerId, "api", v)} />

          <div className="pt-1">
            <button type="button" onClick={() => setShowModels(!showModels)}
              className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider"
              style={{ color: "var(--text-secondary)" }}>
              {showModels ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              模型列表 ({models.length})
            </button>
            {showModels && (
              <div className="mt-1.5 space-y-1.5">
                {models.map((m: any, idx: number) => (
                  <div key={m.id || idx} className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs"
                    style={{ background: "var(--hover)" }}>
                    <span className="font-mono flex-1 truncate" style={{ color: "var(--text)" }}>{m.id}</span>
                    <span className="text-[10px]" style={{ color: "var(--text-secondary)" }}>{m.name || m.id}</span>
                    {m.reasoning && <span className="text-[9px] px-1 py-0.5 rounded-full" style={{ background: "var(--accent-muted)", color: "var(--accent)" }}>推理</span>}
                    <span className="text-[10px]" style={{ color: "var(--text-secondary)" }}>{m.contextWindow ? `${Math.round((m.contextWindow || 0) / 1000)}k` : ""}</span>
                    <button type="button"
                      onClick={() => { const next = models.filter((_: any, i: number) => i !== idx); onUpdate(providerId, "models", next); }}
                      className="btn-ghost p-0.5" style={{ color: "var(--text-secondary)" }}
                      onMouseEnter={e => (e.currentTarget.style.color = "var(--error)")}
                      onMouseLeave={e => (e.currentTarget.style.color = "var(--text-secondary)")}>
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
                {showAddModel ? (
                  <div className="p-2.5 rounded-lg space-y-1.5" style={{ border: "1px dashed var(--border)" }}>
                    <div className="grid grid-cols-2 gap-1.5">
                      <Input label="Model ID" value={newModel.id} onChange={(v) => setNewModel({ ...newModel, id: v })} placeholder="gpt-4o" />
                      <Input label="显示名" value={newModel.name} onChange={(v) => setNewModel({ ...newModel, name: v })} placeholder="GPT-4o" />
                      <Input label="Context Window" value={newModel.contextWindow} onChange={(v) => setNewModel({ ...newModel, contextWindow: v })} type="number" />
                      <Input label="Max Tokens" value={newModel.maxTokens} onChange={(v) => setNewModel({ ...newModel, maxTokens: v })} type="number" />
                    </div>
                    <div className="flex gap-1.5">
                      <button type="button" onClick={() => {
                        if (!newModel.id.trim()) return;
                        const entry = { id: newModel.id.trim(), name: newModel.name.trim() || newModel.id.trim(), reasoning: false, input: ["text"], contextWindow: parseInt(newModel.contextWindow) || 128000, maxTokens: parseInt(newModel.maxTokens) || 8192 };
                        onUpdate(providerId, "models", [...models, entry]);
                        setNewModel({ id: "", name: "", contextWindow: "128000", maxTokens: "8192" });
                        setShowAddModel(false);
                      }} className="btn-primary" style={{ fontSize: 10 }}>添加</button>
                      <button type="button" onClick={() => setShowAddModel(false)} className="btn-ghost" style={{ fontSize: 10 }}>取消</button>
                    </div>
                  </div>
                ) : (
                  <button type="button" onClick={() => setShowAddModel(true)} className="btn-outline w-full justify-center" style={{ fontSize: 10 }}>
                    <Plus className="w-3 h-3" /> 添加模型
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ───────────────────── Agent Card ───────────────────── */

function AgentCard({ agent, models, config, currentAgentId, onConfigChange, onDelete, onError }: {
  agent: any; models: { id: string; name: string; provider: string }[];
  config: any; currentAgentId: string;
  onConfigChange: (newConfig: any) => void; onDelete: (id: string) => void;
  onError?: (msg: string) => void;
}) {
  const { t } = useApp();
  const [expanded, setExpanded] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const agentsList: any[] = config.agents?.list || [];
  const idx = agentsList.findIndex((a: any) => a.id === agent.id);

  const updateAgent = async (field: string, value: any) => {
    const list = JSON.parse(JSON.stringify(agentsList));
    const a = list[idx];
    if (!a) return;
    if (field.includes(".")) {
      const parts = field.split(".");
      let cur = a;
      for (let i = 0; i < parts.length - 1; i++) { cur[parts[i]] = cur[parts[i]] || {}; cur = cur[parts[i]]; }
      if (value === undefined || value === "") delete cur[parts[parts.length - 1]];
      else cur[parts[parts.length - 1]] = value;
    } else { a[field] = value; }
    try {
      const result = await api.replaceConfig({ ...config, agents: { ...config.agents, list } });
      onConfigChange(result.config);
    } catch (e: any) { onError?.(`${t.configUpdateFailed}: ${e?.message || "未知错误"}`); }
  };

  return (
    <div className="glass-inset rounded-lg p-2.5 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-xs font-medium truncate" style={{ color: "var(--text)" }}>{agent.name || agent.id}</div>
          <div className="text-[10px] truncate font-mono" style={{ color: "var(--text-secondary)" }}>{agent.id}</div>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <select value={agent.model ?? ""} onChange={(e) => updateAgent("model", e.target.value || null)}
            className="input text-[10px] max-w-[140px] truncate" style={{ padding: "3px 6px" }}>
            <option value="">{t.inheritDefault}</option>
            {models.map((m) => { const ref = `${m.provider}/${m.id}`; return <option key={ref} value={ref}>{m.name}</option>; })}
          </select>
          <button onClick={() => setExpanded(!expanded)} className="btn-ghost p-1" type="button">
            {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          </button>
          {agent.id !== "main" && (
            deleteConfirm ? (
              <div className="flex gap-1">
                <button onClick={() => { onDelete(agent.id); setDeleteConfirm(false); }}
                  className="btn-primary" style={{ padding: "2px 6px", fontSize: 10, background: "var(--error)" }} type="button">{t.confirm}</button>
                <button onClick={() => setDeleteConfirm(false)} className="btn-ghost" style={{ fontSize: 10 }} type="button">{t.cancel}</button>
              </div>
            ) : (
              <button onClick={() => setDeleteConfirm(true)} className="btn-ghost p-1" type="button"
                style={{ color: "var(--text-secondary)" }}
                onMouseEnter={e => (e.currentTarget.style.color = "var(--error)")}
                onMouseLeave={e => (e.currentTarget.style.color = "var(--text-secondary)")}>
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )
          )}
        </div>
      </div>
      {expanded && (
        <div className="pt-2 space-y-2" style={{ borderTop: "1px solid var(--border)" }}>
          <div className="text-[10px] font-semibold uppercase" style={{ color: "var(--text-secondary)" }}>{t.heartbeatOverride}</div>
          <Toggle label={t.heartbeatEnabled} value={agent.heartbeat?.enabled !== false} onChange={(v) => updateAgent("heartbeat.enabled", v)} />
          <Input label={t.heartbeatInterval} value={agent.heartbeat?.every ?? ""} onChange={(v) => updateAgent("heartbeat.every", v || undefined)} placeholder={t.inheritDefault} />
          <div className="text-[10px] font-semibold uppercase pt-1" style={{ color: "var(--text-secondary)" }}>{t.toolsPolicyOverride}</div>
          <Input label={t.toolsAllow} value={(agent.tools?.allow || []).join(", ")}
            onChange={(v) => { const arr = v.split(",").map((s: string) => s.trim()).filter(Boolean); updateAgent("tools", { ...(agent.tools || {}), allow: arr.length ? arr : undefined }); }}
            placeholder={t.inheritDefault} hint={t.commaSeparatedEmptyInherit} />
          <Input label={t.toolsDeny} value={(agent.tools?.deny || []).join(", ")}
            onChange={(v) => { const arr = v.split(",").map((s: string) => s.trim()).filter(Boolean); updateAgent("tools", { ...(agent.tools || {}), deny: arr.length ? arr : undefined }); }}
            placeholder={t.inheritDefault} hint={t.commaSeparatedPreferAllow} />
        </div>
      )}
    </div>
  );
}

/* ───────────────────── Main ConfigModal ───────────────────── */

export default function ConfigModal() {
  const { currentAgentId, currentModel, loadMainSession, loadAgents, switchAgent, showConfigModal, setShowConfigModal, effectiveTheme, showNotice, locale, setLocale, t } = useApp();
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [configPath, setConfigPath] = useState("");
  const [configMode, setConfigMode] = useState<"form" | "raw">("form");
  const [rawJson, setRawJson] = useState("");
  const [rawError, setRawError] = useState<string | null>(null);
  const [models, setModels] = useState<{ id: string; name: string; provider: string }[]>([]);
  const [showAddProvider, setShowAddProvider] = useState(false);
  const [newProvider, setNewProvider] = useState({ id: "", baseUrl: "", api: "openai-completions" });
  const [showAddAgent, setShowAddAgent] = useState(false);
  const [addAgentForm, setAddAgentForm] = useState({ id: "", name: "", description: "", model: "" });

  const loadConfig = useCallback(() => {
    api.fetchConfig().then(c => { setConfig(c); setRawJson(JSON.stringify(c, null, 2)); setLoading(false); })
      .catch((e: any) => { setLoading(false); showNotice({ kind: "error", text: `加载配置失败: ${e?.message || "未知错误"}` }); });
  }, [showNotice]);

  const loadModels = useCallback(() => {
    api.fetchModels().then((data: any) => {
      setModels((data.catalog || []).map((e: any) => ({ id: e.id, name: e.name || e.id, provider: e.provider || "" })));
    }).catch((e: any) => { setModels([]); showNotice({ kind: "error", text: `加载模型列表失败: ${e?.message || "未知错误"}` }); });
  }, [showNotice]);

  useEffect(() => { if (showConfigModal) { loadConfig(); loadModels(); } }, [showConfigModal, loadConfig, loadModels]);

  useEffect(() => {
    api.fetchConfigPath().then(r => setConfigPath(r.path))
      .catch((e: any) => { showNotice({ kind: "error", text: `读取配置路径失败: ${e?.message || "未知错误"}` }); });
  }, [showNotice]);

  const handleUpdate = async (path: string, value: any) => {
    const parts = path.split(".");
    const updates: any = {};
    let current = updates;
    for (let i = 0; i < parts.length - 1; i++) { current[parts[i]] = {}; current = current[parts[i]]; }
    current[parts[parts.length - 1]] = value;
    setSaving(true);
    try {
      const result = await api.updateConfig(updates);
      setConfig(result.config);
      setRawJson(JSON.stringify(result.config, null, 2));
    } catch (e: any) { showNotice({ kind: "error", text: `保存配置失败: ${e?.message || "未知错误"}` }); }
    setSaving(false);
  };

  const handleProviderFieldUpdate = async (providerId: string, field: string, value: any) => {
    if (!config) return;
    const providers = JSON.parse(JSON.stringify(config.models?.providers || {}));
    if (!providers[providerId]) return;
    if (field === "models") providers[providerId].models = value;
    else providers[providerId][field] = value;
    const cleanProviders = JSON.parse(JSON.stringify(providers));
    for (const pid of Object.keys(cleanProviders)) {
      const p = cleanProviders[pid];
      if (p.apiKey && p.apiKey.includes("***")) delete p.apiKey;
    }
    setSaving(true);
    try {
      const result = await api.updateConfig({ models: { providers: cleanProviders } });
      setConfig(result.config); setRawJson(JSON.stringify(result.config, null, 2)); loadModels();
    } catch (e: any) { showNotice({ kind: "error", text: `更新失败: ${e?.message || "未知错误"}` }); }
    setSaving(false);
  };

  const handleDeleteProvider = async (providerId: string) => {
    if (!config) return;
    const providers = JSON.parse(JSON.stringify(config.models?.providers || {}));
    delete providers[providerId];
    setSaving(true);
    try {
      const result = await api.updateConfig({ models: { providers } });
      setConfig(result.config); setRawJson(JSON.stringify(result.config, null, 2)); loadModels();
    } catch (e: any) { showNotice({ kind: "error", text: `删除 Provider 失败: ${e?.message || "未知错误"}` }); }
    setSaving(false);
  };

  const handleAddProvider = async () => {
    if (!newProvider.id.trim() || !config) return;
    const providers = JSON.parse(JSON.stringify(config.models?.providers || {}));
    providers[newProvider.id.trim()] = { baseUrl: newProvider.baseUrl.trim(), api: newProvider.api, models: [] };
    setSaving(true);
    try {
      const result = await api.updateConfig({ models: { providers } });
      setConfig(result.config); setRawJson(JSON.stringify(result.config, null, 2));
      setShowAddProvider(false); setNewProvider({ id: "", baseUrl: "", api: "openai-completions" }); loadModels();
    } catch (e: any) { showNotice({ kind: "error", text: `添加失败: ${e?.message || "未知错误"}` }); }
    setSaving(false);
  };

  const handleConfigChange = (newCfg: any) => { setConfig(newCfg); setRawJson(JSON.stringify(newCfg, null, 2)); loadModels(); };
  const handleSecretSaved = () => { loadConfig(); loadModels(); };

  if (!showConfigModal) return null;

  if (loading || !config) {
    return (
      <>
        <div className="fixed inset-0 z-40" style={{ background: "rgba(0,0,0,0.25)", backdropFilter: "blur(4px)" }}
          onClick={() => setShowConfigModal(false)} aria-hidden />
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="glass-card px-8 py-6 text-sm" style={{ color: "var(--text-secondary)" }}>
            {loading ? "加载配置..." : "无法加载配置"}
          </div>
        </div>
      </>
    );
  }

  const defaults = config.agents?.defaults || {};
  const providers = config.models?.providers || {};
  const providerKeys = Object.keys(providers);
  const webSearch = config.tools?.web?.search || {};
  const autoCompaction = config.auto_compaction || {};
  const sessionMaint = config.session?.maintenance || {};

  const handleRawSave = async () => {
    setRawError(null);
    try {
      const parsed = JSON.parse(rawJson);
      setSaving(true);
      const result = await api.replaceConfig(parsed);
      setConfig(result.config);
      // 重新加载原始配置，避免脱敏值覆盖编辑器中的真实密钥
      try {
        const raw = await api.fetchRawConfig();
        setRawJson(JSON.stringify(raw, null, 2));
      } catch {
        setRawJson(JSON.stringify(result.config, null, 2));
      }
      loadModels(); loadMainSession();
    } catch (e: any) { setRawError(e.message || "JSON 解析失败"); }
    finally { setSaving(false); }
  };

  const handleRawLoad = async () => {
    try {
      const raw = await api.fetchRawConfig();
      setRawJson(JSON.stringify(raw, null, 2));
    } catch (e: any) {
      setRawError(e?.message || "无法加载原始配置");
      showNotice({ kind: "error", text: `加载原始配置失败: ${e?.message || "未知错误"}` });
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 transition-opacity"
        style={{ background: "rgba(0,0,0,0.25)", backdropFilter: "blur(4px)" }}
        onClick={() => setShowConfigModal(false)} aria-hidden />

      {/* Drawer */}
      <div className="fixed right-0 top-0 bottom-0 w-[480px] max-w-[95vw] z-50 flex flex-col animate-slide-in-from-right" data-testid="config-modal"
        style={{
          background: "var(--glass-heavy)",
          backdropFilter: "blur(var(--blur-heavy)) saturate(1.8)",
          WebkitBackdropFilter: "blur(var(--blur-heavy)) saturate(1.8)",
          borderLeft: "1px solid var(--glass-border)",
          boxShadow: "var(--shadow-xl)",
        }}>

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 flex-shrink-0"
          style={{ borderBottom: "1px solid var(--border)" }}>
          <div className="flex items-center gap-2">
            <Settings2 className="w-4 h-4" style={{ color: "var(--accent)" }} />
            <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>{t.configCenter}</h2>
          </div>
          <button onClick={() => setShowConfigModal(false)} className="btn-ghost p-1.5" type="button">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Mode toggle */}
        <div className="px-4 py-2 flex items-center gap-2" style={{ borderBottom: "1px solid var(--border)" }}>
          <p className="text-[10px] flex-1 truncate font-mono" style={{ color: "var(--text-secondary)" }}>{configPath || "config.json"}</p>
          <div className="flex gap-px rounded-lg p-0.5" style={{ background: "var(--bg-inset)" }}>
            <button type="button" onClick={() => setConfigMode("form")}
              className="px-2.5 py-1 text-[11px] rounded-md transition-all"
              style={{
                background: configMode === "form" ? "var(--bg-elevated)" : "transparent",
                color: configMode === "form" ? "var(--text)" : "var(--text-secondary)",
                boxShadow: configMode === "form" ? "var(--shadow-xs)" : "none",
              }}>
              表单
            </button>
            <button type="button" onClick={() => { setConfigMode("raw"); handleRawLoad(); }}
              className="px-2.5 py-1 text-[11px] rounded-md transition-all"
              style={{
                background: configMode === "raw" ? "var(--bg-elevated)" : "transparent",
                color: configMode === "raw" ? "var(--text)" : "var(--text-secondary)",
                boxShadow: configMode === "raw" ? "var(--shadow-xs)" : "none",
              }}>
              JSON
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-h-0 overflow-y-auto">
          {saving && <div className="px-4 py-1 text-xs animate-pulse" style={{ color: "var(--accent)" }}>保存中...</div>}

          {configMode === "raw" ? (
            <div className="flex flex-col h-full">
              <div className="px-4 py-2 flex items-center gap-2">
                <AlertCircle className="w-3.5 h-3.5" style={{ color: "var(--warning)" }} />
                <p className="text-[10px] flex-1" style={{ color: "var(--text-secondary)" }}>
                  原始 JSON 编辑（含明文密钥）。agents.defaults 为全局默认，agents.list[].model 覆盖每个 Agent。
                </p>
              </div>
              {rawError && <div className="mx-4 text-xs px-2.5 py-1.5 rounded-lg" style={{ color: "var(--error)", background: "var(--error-bg)" }}>{rawError}</div>}
              <div className="flex-1 min-h-0 mx-4 mb-2 rounded-lg overflow-hidden" style={{ border: "1px solid var(--border)" }}>
                <MonacoEditor
                  height="100%" language="json"
                  theme={effectiveTheme === "dark" ? "vs-dark" : "vs"}
                  value={rawJson}
                  onChange={(v) => { setRawJson(v || ""); setRawError(null); }}
                  options={{ minimap: { enabled: false }, fontSize: 12, lineNumbers: "on", wordWrap: "on", scrollBeyondLastLine: false, automaticLayout: true }}
                />
              </div>
              <div className="px-4 pb-3 flex justify-end">
                <button onClick={handleRawSave} disabled={saving} className="btn-primary" type="button" data-testid="config-save-btn">保存</button>
              </div>
            </div>
          ) : (
            <div className="p-4 space-y-3">
              {/* Providers */}
              <Section title="Providers & 模型" icon={<Server className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />}>
                {providerKeys.length === 0 && (
                  <div className="text-xs px-2.5 py-2 rounded-lg flex items-start gap-2"
                    style={{ background: "var(--warning-bg)", color: "var(--warning)" }}>
                    <AlertCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                    <span>未配置任何 Provider。请添加至少一个 Provider 并设置 API Key 和模型，才能开始对话。</span>
                  </div>
                )}
                {providerKeys.map((pid) => (
                  <ProviderEditor key={pid} providerId={pid} provider={providers[pid]}
                    onUpdate={handleProviderFieldUpdate} onDelete={handleDeleteProvider} onSecretSaved={handleSecretSaved} />
                ))}
                {showAddProvider ? (
                  <div className="p-2.5 rounded-lg space-y-2" style={{ border: "1px dashed var(--accent)" }}>
                    <div className="text-[11px] font-medium" style={{ color: "var(--text)" }}>添加 Provider</div>
                    <Input label="Provider ID" value={newProvider.id} onChange={(v) => setNewProvider({ ...newProvider, id: v })} placeholder="如 openai, deepseek, anthropic, ollama" />
                    <Input label="Base URL" value={newProvider.baseUrl} onChange={(v) => setNewProvider({ ...newProvider, baseUrl: v })} placeholder="https://api.openai.com/v1" />
                    <Select label="API 协议" value={newProvider.api} options={[
                      { value: "openai-completions", label: "OpenAI Completions" },
                      { value: "anthropic-messages", label: "Anthropic Messages" },
                      { value: "ollama", label: "Ollama" },
                    ]} onChange={(v) => setNewProvider({ ...newProvider, api: v })} />
                    <div className="flex gap-2">
                      <button type="button" onClick={handleAddProvider} className="btn-primary">添加</button>
                      <button type="button" onClick={() => setShowAddProvider(false)} className="btn-ghost">取消</button>
                    </div>
                    <p className="text-[10px]" style={{ color: "var(--text-secondary)" }}>
                      常见 Provider：OpenAI, Anthropic, DeepSeek, OpenRouter, Ollama, 通义千问, Moonshot, 智谱等
                    </p>
                  </div>
                ) : (
                  <button type="button" onClick={() => setShowAddProvider(true)} className="btn-outline w-full justify-center">
                    <Plus className="w-3.5 h-3.5" /> 添加 Provider
                  </button>
                )}
              </Section>

              {/* Default Model */}
              <Section title="默认模型" icon={<Bot className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />}>
                <div>
                  <label className="text-xs block mb-0.5" style={{ color: "var(--text)" }}>全局默认模型</label>
                  <select value={defaults.model || ""}
                    onChange={async (e) => {
                      const ref = e.target.value;
                      try { await api.switchModel(currentAgentId, ref, "default"); await loadMainSession(); loadConfig(); }
                      catch (err: any) { showNotice({ kind: "error", text: `切换失败: ${err.message}` }); }
                    }}
                    disabled={models.length === 0} className="input text-xs">
                    <option value="">{models.length === 0 ? "请先添加 Provider 和模型" : "请选择..."}</option>
                    {models.map((m) => { const ref = `${m.provider}/${m.id}`; return <option key={ref} value={ref}>{m.name} ({m.provider})</option>; })}
                  </select>
                  <p className="text-[10px] mt-0.5" style={{ color: "var(--text-secondary)" }}>
                    影响所有未覆盖模型的 Agent。当前生效：{currentModel ? `${currentModel.name} (${currentModel.provider})` : "未设置"}
                  </p>
                </div>
                <Input label="递归限制" value={String(defaults.recursion_limit || 50)} onChange={(v) => handleUpdate("agents.defaults.recursion_limit", parseInt(v) || 50)} type="number" />
                <Input label="Context Tokens" value={String(defaults.contextTokens || 200000)} onChange={(v) => handleUpdate("agents.defaults.contextTokens", parseInt(v) || 200000)} type="number" hint="模型上下文窗口 token 数" />
                <Select label="Thinking 默认" value={defaults.thinkingDefault || "off"} options={[
                  { value: "off", label: "关闭" }, { value: "on", label: "开启" },
                ]} onChange={(v) => handleUpdate("agents.defaults.thinkingDefault", v)} />
              </Section>

              {/* Agents */}
              <Section title="Agent 列表" icon={<Bot className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />}>
                <div className="space-y-2">
                  {(config.agents?.list || []).map((agent: any) => (
                    <AgentCard key={agent.id} agent={agent} models={models} config={config} currentAgentId={currentAgentId}
                      onConfigChange={handleConfigChange}
                      onError={(msg) => showNotice({ kind: "error", text: msg })}
                      onDelete={async (id) => {
                        try {
                          await api.deleteAgent(id); loadConfig(); await loadAgents();
                          if (currentAgentId === id) await switchAgent("main");
                        } catch (e: any) { showNotice({ kind: "error", text: e.message }); }
                      }}
                    />
                  ))}
                </div>
                {showAddAgent ? (
                  <div className="p-2.5 rounded-lg space-y-2" style={{ border: "1px dashed var(--border)" }}>
                    <div className="text-[11px] font-medium" style={{ color: "var(--text)" }}>新增 Agent</div>
                    <Input label="ID" value={addAgentForm.id} onChange={(v) => setAddAgentForm({ ...addAgentForm, id: v })} placeholder="如 coder" />
                    <Input label="名称" value={addAgentForm.name} onChange={(v) => setAddAgentForm({ ...addAgentForm, name: v })} placeholder="显示名" />
                    <Input label="描述" value={addAgentForm.description} onChange={(v) => setAddAgentForm({ ...addAgentForm, description: v })} placeholder="可选" />
                    <Select label="模型" value={addAgentForm.model} options={[{ value: "", label: "继承默认" }, ...models.map((m) => ({ value: `${m.provider}/${m.id}`, label: `${m.name} (${m.provider})` }))]} onChange={(v) => setAddAgentForm({ ...addAgentForm, model: v })} />
                    <div className="flex gap-2">
                      <button type="button" onClick={async () => {
                        if (!addAgentForm.id.trim() || !addAgentForm.name.trim()) { showNotice({ kind: "error", text: "ID 和名称必填" }); return; }
                        try {
                          await api.createAgent({ id: addAgentForm.id.trim(), name: addAgentForm.name.trim(), description: addAgentForm.description.trim(), model: addAgentForm.model || undefined });
                          loadConfig(); loadAgents();
                          setShowAddAgent(false); setAddAgentForm({ id: "", name: "", description: "", model: "" });
                        } catch (e: any) { showNotice({ kind: "error", text: e.message }); }
                      }} className="btn-primary">创建</button>
                      <button type="button" onClick={() => setShowAddAgent(false)} className="btn-ghost">取消</button>
                    </div>
                  </div>
                ) : (
                  <button type="button" onClick={() => setShowAddAgent(true)} className="btn-outline w-full justify-center">
                    <Plus className="w-3.5 h-3.5" /> 新增 Agent
                  </button>
                )}
              </Section>

              {/* Tools Policy */}
              <Section title="工具策略（全局默认）" icon={<Wrench className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />} defaultOpen={false}>
                <Input label="允许 (allow)" value={(defaults.tools?.allow || []).join(", ")}
                  onChange={(v) => { const arr = v.split(",").map((s: string) => s.trim()).filter(Boolean); handleUpdate("agents.defaults.tools", { ...(defaults.tools || {}), allow: arr.length ? arr : undefined }); }}
                  placeholder="留空表示全部允许" hint="逗号分隔，如 read,write,exec" />
                <Input label="禁止 (deny)" value={(defaults.tools?.deny || []).join(", ")}
                  onChange={(v) => { const arr = v.split(",").map((s: string) => s.trim()).filter(Boolean); handleUpdate("agents.defaults.tools", { ...(defaults.tools || {}), deny: arr.length ? arr : undefined }); }}
                  placeholder="留空表示不禁止" hint="逗号分隔，优先于 allow" />
              </Section>

              {/* Heartbeat */}
              <Section title="心跳（全局默认）" icon={<Activity className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />} defaultOpen={false}>
                <Toggle label="启用心跳" value={defaults.heartbeat?.enabled !== false} onChange={(v) => handleUpdate("agents.defaults.heartbeat.enabled", v)} />
                <Input label="检查间隔" value={defaults.heartbeat?.every || "30m"} onChange={(v) => handleUpdate("agents.defaults.heartbeat.every", v)} placeholder="30m、1h" hint="0 表示关闭" />
                <Textarea label="心跳 Prompt" value={defaults.heartbeat?.prompt || ""} onChange={(v) => handleUpdate("agents.defaults.heartbeat.prompt", v)} rows={3} hint="留空使用内置默认 Prompt（读取 HEARTBEAT.md 并遵循）" />
                <Input label="Ack 最大字符" value={String(defaults.heartbeat?.ackMaxChars ?? 300)} onChange={(v) => handleUpdate("agents.defaults.heartbeat.ackMaxChars", parseInt(v) || 300)} type="number" />
                <div className="grid grid-cols-2 gap-2">
                  <Input label="活跃时段开始" value={defaults.heartbeat?.activeHours?.start || "08:00"} onChange={(v) => handleUpdate("agents.defaults.heartbeat.activeHours", { ...defaults.heartbeat?.activeHours, start: v })} placeholder="08:00" />
                  <Input label="活跃时段结束" value={defaults.heartbeat?.activeHours?.end || "24:00"} onChange={(v) => handleUpdate("agents.defaults.heartbeat.activeHours", { ...defaults.heartbeat?.activeHours, end: v })} placeholder="24:00" />
                </div>
              </Section>

              {/* Memory Search */}
              <Section title="记忆检索" icon={<Search className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />} defaultOpen={false}>
                <Toggle label="启用向量检索" value={defaults.memorySearch?.store?.vector?.enabled ?? false} onChange={(v) => handleUpdate("agents.defaults.memorySearch.store.vector.enabled", v)} />
                <Select label="Embedding 来源" value={defaults.memorySearch?.provider || "local"} options={[
                  { value: "local", label: "本地 (sentence-transformers)" },
                  { value: "openai", label: "远程 OpenAI 兼容 API" },
                ]} onChange={(v) => handleUpdate("agents.defaults.memorySearch.provider", v)} />
                {defaults.memorySearch?.provider === "openai" && (
                  <>
                    <Input label="API Base URL" value={defaults.memorySearch?.remote?.baseUrl || ""} onChange={(v) => handleUpdate("agents.defaults.memorySearch.remote.baseUrl", v)} placeholder="https://api.openai.com/v1" />
                    <SecretInput label="API Key" value={defaults.memorySearch?.remote?.apiKey || ""} secretPath="agents.defaults.memorySearch.remote.apiKey" hint="可用 ${OPENAI_API_KEY} 引用环境变量" onSaved={handleSecretSaved} />
                    <Input label="Model" value={defaults.memorySearch?.model || "text-embedding-3-small"} onChange={(v) => handleUpdate("agents.defaults.memorySearch.model", v)} />
                  </>
                )}
              </Section>

              {/* Web Search */}
              <Section title="网络搜索" icon={<Search className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />} defaultOpen={false}>
                <Select label="搜索后端" value={webSearch.provider || "duckduckgo"} options={[
                  { value: "duckduckgo", label: "DuckDuckGo" },
                  { value: "brave", label: "Brave Search" },
                  { value: "searxng", label: "SearXNG" },
                ]} onChange={(v) => handleUpdate("tools.web.search.provider", v)} />
                {webSearch.provider === "brave" && (
                  <SecretInput label="Brave API Key" value={webSearch.apiKey || ""} secretPath="tools.web.search.apiKey" onSaved={handleSecretSaved} />
                )}
                {webSearch.provider === "searxng" && (
                  <Input label="SearXNG URL" value={webSearch.baseUrl || ""} onChange={(v) => handleUpdate("tools.web.search.baseUrl", v)} placeholder="http://localhost:8888" />
                )}
              </Section>

              {/* Session */}
              <Section title="会话与压缩" icon={<Database className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />} defaultOpen={false}>
                <Select label="会话维护模式" value={sessionMaint.mode || "warn"} options={[
                  { value: "warn", label: "warn（仅预警）" }, { value: "enforce", label: "enforce（自动清理）" },
                ]} onChange={(v) => handleUpdate("session.maintenance.mode", v)} />
                <Input label="过期时长" value={sessionMaint.pruneAfter || "30d"} onChange={(v) => handleUpdate("session.maintenance.pruneAfter", v)} hint="如 30d、7d" />
                <Input label="最大会话数" value={String(sessionMaint.maxEntries ?? 500)} onChange={(v) => handleUpdate("session.maintenance.maxEntries", parseInt(v) || 500)} type="number" />
                <div className="pt-2 mt-2" style={{ borderTop: "1px solid var(--border)" }}>
                  <Toggle label="启用自动压缩" value={autoCompaction.enabled !== false} onChange={(v) => handleUpdate("auto_compaction.enabled", v)} />
                  <Input label="压缩阈值 (tokens)" value={String(autoCompaction.threshold_tokens || 80000)} onChange={(v) => handleUpdate("auto_compaction.threshold_tokens", parseInt(v) || 80000)} type="number" />
                  <Input label="预警阈值 (tokens)" value={String(autoCompaction.warning_tokens || 60000)} onChange={(v) => handleUpdate("auto_compaction.warning_tokens", parseInt(v) || 60000)} type="number" />
                </div>
              </Section>

              {/* Sandbox */}
              <Section title={t.configSandbox} icon={<Shield className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />} defaultOpen={false}>
                <Select label={t.execConfirmLabel} value={config.tools?.exec?.approval?.ask ?? "on_miss"} options={[
                  { value: "off", label: t.execConfirmOff },
                  { value: "on_miss", label: t.execConfirmOnMiss },
                  { value: "always", label: t.execConfirmAlways },
                ]} onChange={(v) => handleUpdate("tools.exec.approval", { ...(config.tools?.exec?.approval || {}), ask: v })} hint={t.execConfirmHint} />
                <Select label="沙箱模式" value={config.sandbox?.mode || "soft"} options={[
                  { value: "off", label: "关闭 — 不做额外安全检查" },
                  { value: "soft", label: "软沙箱 — 路径限制 + 命令黑名单" },
                  { value: "strict", label: "严格 — 所有写操作需确认" },
                ]} onChange={(v) => handleUpdate("sandbox.mode", v)} />
                <Select label={t.writeApprovalLabel} value={config.sandbox?.writeApproval || "on_overwrite"} options={[
                  { value: "off", label: t.writeApprovalOff },
                  { value: "on_overwrite", label: t.writeApprovalOnOverwrite },
                  { value: "always", label: t.writeApprovalAlways },
                ]} onChange={(v) => handleUpdate("sandbox.writeApproval", v)} />
                <Toggle label="执行命令前工作区快照" value={config.sandbox?.snapshotBeforeExec ?? false} onChange={(v) => handleUpdate("sandbox.snapshotBeforeExec", v)} />
                <Input label="撤销栈大小" value={String(config.sandbox?.undoStackSize ?? 50)} onChange={(v) => handleUpdate("sandbox.undoStackSize", parseInt(v) || 50)} type="number" hint="Agent 可回滚的最近操作数量" />
              </Section>

              {/* Notifications */}
              <Section title={t.configNotifications} icon={<Bell className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />} defaultOpen={false}>
                <Toggle label="启用通知" value={config.notifications?.enabled !== false} onChange={(v) => handleUpdate("notifications.enabled", v)} />
                <Toggle label="通知声音" value={config.notifications?.sound !== false} onChange={(v) => handleUpdate("notifications.sound", v)} />
                <Toggle label="角标提示" value={config.notifications?.badge !== false} onChange={(v) => handleUpdate("notifications.badge", v)} />
                <div className="grid grid-cols-2 gap-2">
                  <Input label="免打扰开始" value={config.notifications?.quietHours?.start || "23:00"} onChange={(v) => handleUpdate("notifications.quietHours", { ...config.notifications?.quietHours, start: v })} />
                  <Input label="免打扰结束" value={config.notifications?.quietHours?.end || "08:00"} onChange={(v) => handleUpdate("notifications.quietHours", { ...config.notifications?.quietHours, end: v })} />
                </div>
              </Section>

              {/* Runtime */}
              <Section title={t.configRuntime} icon={<Cpu className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />} defaultOpen={false}>
                <Input label="最大并发会话" value={String(config.runtime?.maxConcurrentSessions ?? 5)} onChange={(v) => handleUpdate("runtime.maxConcurrentSessions", parseInt(v) || 5)} type="number" />
                <Input label="内存限制 (MB)" value={String(config.runtime?.memoryLimitMB ?? 0)} onChange={(v) => handleUpdate("runtime.memoryLimitMB", parseInt(v) || 0)} type="number" hint="0 = 不限制" />
                <Input label="进程超时 (秒)" value={String(config.runtime?.processTimeoutSeconds ?? 300)} onChange={(v) => handleUpdate("runtime.processTimeoutSeconds", parseInt(v) || 300)} type="number" />
                <Input label="空闲 GC (分钟)" value={String(config.runtime?.gcIdleMinutes ?? 30)} onChange={(v) => handleUpdate("runtime.gcIdleMinutes", parseInt(v) || 30)} type="number" hint="空闲会话多久后自动释放内存" />
              </Section>

              {/* Browser */}
              <Section title={t.configBrowser} icon={<Globe className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />} defaultOpen={false}>
                <Toggle label="启用浏览器" value={config.browser?.enabled ?? false} onChange={(v) => handleUpdate("browser.enabled", v)} />
                <Toggle label="无头模式" value={config.browser?.headless !== false} onChange={(v) => handleUpdate("browser.headless", v)} />
                <Input label="视口大小" value={config.browser?.viewport || "1280x720"} onChange={(v) => handleUpdate("browser.viewport", v)} placeholder="1280x720" />
                <Input label="代理" value={config.browser?.proxy || ""} onChange={(v) => handleUpdate("browser.proxy", v || null)} placeholder="http://proxy:port" />
              </Section>

              {/* Backup */}
              <Section title={t.configBackup} icon={<FolderArchive className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />} defaultOpen={false}>
                <Toggle label="自动备份" value={config.backup?.autoBackup ?? false} onChange={(v) => handleUpdate("backup.autoBackup", v)} />
                <Input label="备份间隔 (小时)" value={String(config.backup?.intervalHours ?? 24)} onChange={(v) => handleUpdate("backup.intervalHours", parseInt(v) || 24)} type="number" />
                <Input label="最大快照数" value={String(config.backup?.maxSnapshots ?? 10)} onChange={(v) => handleUpdate("backup.maxSnapshots", parseInt(v) || 10)} type="number" />
                <Input label="备份目录" value={config.backup?.backupDir || ""} onChange={(v) => handleUpdate("backup.backupDir", v || null)} placeholder="留空使用默认目录" />
              </Section>

              {/* Skills */}
              <Section title={t.configSkills} icon={<Puzzle className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />} defaultOpen={false}>
                <Toggle label="自动发现技能" value={config.skills?.autoDiscover !== false} onChange={(v) => handleUpdate("skills.autoDiscover", v)} />
                <Toggle label="检查技能更新" value={config.skills?.updateCheck ?? false} onChange={(v) => handleUpdate("skills.updateCheck", v)} />
              </Section>

              {/* App */}
              <Section title={t.configApp} icon={<Settings2 className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />} defaultOpen={false}>
                <Select label="语言 / Language" value={locale} options={[
                  { value: "zh-CN", label: "简体中文" }, { value: "en-US", label: "English" },
                ]} onChange={(v) => { setLocale(v as any); handleUpdate("app.locale", v); }} />
                <Select label="日志级别" value={config.app?.logLevel || "info"} options={[
                  { value: "debug", label: "Debug" }, { value: "info", label: "Info" },
                  { value: "warning", label: "Warning" }, { value: "error", label: "Error" },
                ]} onChange={(v) => handleUpdate("app.logLevel", v)} />
                <Input label="网络代理" value={config.app?.proxy || ""} onChange={(v) => handleUpdate("app.proxy", v || null)} placeholder="http://proxy:port" />
              </Section>

              {/* Advanced */}
              <Section title="高级：Compaction & Context Pruning" icon={<Clock className="w-3.5 h-3.5" style={{ color: "var(--text-secondary)" }} />} defaultOpen={false}>
                <div className="text-[10px] uppercase font-semibold mb-1" style={{ color: "var(--text-secondary)" }}>Compaction 策略</div>
                <Toggle label="启用" value={defaults.compaction?.enabled !== false} onChange={(v) => handleUpdate("agents.defaults.compaction.enabled", v)} />
                <Input label="阈值比例" value={String(defaults.compaction?.threshold ?? 0.8)} onChange={(v) => handleUpdate("agents.defaults.compaction.threshold", parseFloat(v) || 0.8)} hint="0.8 = 80% context 使用时触发" />
                <Input label="保留 tokens" value={String(defaults.compaction?.reserveTokens ?? 20000)} onChange={(v) => handleUpdate("agents.defaults.compaction.reserveTokens", parseInt(v) || 20000)} type="number" />
                <Input label="保留最近 tokens" value={String(defaults.compaction?.keepRecentTokens ?? 8000)} onChange={(v) => handleUpdate("agents.defaults.compaction.keepRecentTokens", parseInt(v) || 8000)} type="number" />
                <Toggle label="Memory Flush" value={defaults.compaction?.memoryFlush !== false} onChange={(v) => handleUpdate("agents.defaults.compaction.memoryFlush", v)} />
                <div className="pt-2 mt-2" style={{ borderTop: "1px solid var(--border)" }}>
                  <div className="text-[10px] uppercase font-semibold mb-1" style={{ color: "var(--text-secondary)" }}>Context Pruning</div>
                  <Toggle label="Soft Trim" value={defaults.contextPruning?.softTrim !== false} onChange={(v) => handleUpdate("agents.defaults.contextPruning.softTrim", v)} />
                  <Input label="工具输出最大字符" value={String(defaults.contextPruning?.toolOutputMaxChars ?? 3000)} onChange={(v) => handleUpdate("agents.defaults.contextPruning.toolOutputMaxChars", parseInt(v) || 3000)} type="number" />
                  <Input label="保留最近消息数" value={String(defaults.contextPruning?.recentPreserve ?? 4)} onChange={(v) => handleUpdate("agents.defaults.contextPruning.recentPreserve", parseInt(v) || 4)} type="number" />
                </div>
              </Section>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
