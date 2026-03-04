"use client";

import { useEffect, useState, useCallback } from "react";
import { useApp } from "@/lib/store";
import * as api from "@/lib/api";
import { Heart, RefreshCw, Trash2, CheckCircle, AlertCircle, XCircle, MinusCircle, Clock, ChevronDown, ChevronRight, Play, Plus, ToggleLeft, ToggleRight } from "lucide-react";

const SCHEDULE_PRESETS = [
  { label: "每天 8:00", kind: "cron" as const, expr: "0 8 * * *" },
  { label: "每天 9:00", kind: "cron" as const, expr: "0 9 * * *" },
  { label: "每天 9:30", kind: "cron" as const, expr: "30 9 * * *" },
  { label: "每天 12:00", kind: "cron" as const, expr: "0 12 * * *" },
  { label: "每天 18:00", kind: "cron" as const, expr: "0 18 * * *" },
  { label: "每 30 分钟", kind: "every" as const, everyMs: 30 * 60 * 1000 },
  { label: "每 1 小时", kind: "every" as const, everyMs: 60 * 60 * 1000 },
  { label: "每 2 小时", kind: "every" as const, everyMs: 2 * 60 * 60 * 1000 },
  { label: "每 1 天", kind: "every" as const, everyMs: 24 * 60 * 60 * 1000 },
];

function formatJobSchedule(job: any): string {
  const s = job?.schedule;
  if (!s) return "—";
  if (s.kind === "at" && s.at) {
    try {
      const d = new Date(s.at);
      return `临时 ${d.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}`;
    } catch { return s.at; }
  }
  if (s.kind === "every" && s.everyMs) {
    const m = s.everyMs / 60000;
    const h = s.everyMs / 3600000;
    const d = s.everyMs / 86400000;
    if (d >= 1 && d % 1 === 0) return `每 ${d} 天`;
    if (h >= 1 && h % 1 === 0) return `每 ${h} 小时`;
    return `每 ${m} 分钟`;
  }
  if (s.kind === "cron" && s.expr) {
    const p = SCHEDULE_PRESETS.find((x) => x.kind === "cron" && x.expr === s.expr);
    return p?.label ?? s.expr;
  }
  return "—";
}

const STATUS_LABELS: Record<string, { label: string; icon: any; color: string }> = {
  "ok-empty": { label: "正常（无事项）", icon: CheckCircle, color: "var(--success)" },
  "ok-token": { label: "正常（已确认）", icon: CheckCircle, color: "var(--success)" },
  sent: { label: "有提醒", icon: AlertCircle, color: "var(--warning)" },
  skipped: { label: "已跳过", icon: MinusCircle, color: "var(--text-tertiary)" },
  failed: { label: "失败", icon: XCircle, color: "var(--error)" },
};

const REASON_LABELS: Record<string, string> = {
  "quiet-hours": "静默时段",
  "requests-in-flight": "会话忙碌",
  "empty-heartbeat-file": "HEARTBEAT.md 为空",
};

export default function HeartbeatPanel() {
  const { currentAgentId, t, showNotice } = useApp();
  const [heartbeatConfig, setHeartbeatConfig] = useState<{ enabled: boolean; every: string } | null>(null);
  const [heartbeatToggling, setHeartbeatToggling] = useState(false);
  const [events, setEvents] = useState<any[]>([]);
  const [cronJobs, setCronJobs] = useState<any[]>([]);
  const [cronExpanded, setCronExpanded] = useState(true);
  const [cronAdding, setCronAdding] = useState(false);
  const [cronForm, setCronForm] = useState({
    name: "", text: "",
    scheduleKind: "preset" as "at" | "every" | "preset" | "advanced",
    scheduleAt: "", everyAmount: "30",
    everyUnit: "minutes" as "minutes" | "hours" | "days",
    presetValue: "0 8 * * *", advancedExpr: "0 8 * * *",
    deleteAfterRun: false,
  });
  const [loading, setLoading] = useState(true);
  const [cleared, setCleared] = useState(false);

  const load = useCallback(() => {
    if (!currentAgentId) return;
    setLoading(true);
    Promise.all([
      api.fetchHeartbeatConfig(currentAgentId),
      api.fetchHeartbeatHistory(currentAgentId, 30),
      api.fetchCronJobs().catch(() => []),
    ]).then(([hbCfg, heartbeatData, cronData]) => {
      setHeartbeatConfig(hbCfg);
      setEvents(Array.isArray(heartbeatData) ? heartbeatData : []);
      setCronJobs(Array.isArray(cronData) ? cronData : []);
    }).catch(() => {
      setHeartbeatConfig(null);
      setEvents([]);
      setCronJobs([]);
    }).finally(() => setLoading(false));
  }, [currentAgentId]);

  const handleToggleHeartbeat = useCallback(async () => {
    if (heartbeatConfig == null || heartbeatToggling) return;
    const next = !heartbeatConfig.enabled;
    setHeartbeatToggling(true);
    try {
      await api.updateHeartbeatEnabled(next);
      setHeartbeatConfig((c) => c ? { ...c, enabled: next } : null);
      showNotice?.({ kind: "success", text: next ? t.heartbeatStatusOn : t.heartbeatStatusOff });
    } catch (e: any) {
      showNotice?.({ kind: "error", text: e?.message || "更新失败" });
    } finally {
      setHeartbeatToggling(false);
    }
  }, [heartbeatConfig, heartbeatToggling, showNotice, t]);

  useEffect(() => { setCleared(false); }, [currentAgentId]);

  useEffect(() => {
    if (currentAgentId && !cleared) load();
  }, [currentAgentId, cleared, load]);

  const handleClear = () => { setEvents([]); setCleared(true); };
  const handleRefresh = () => { setCleared(false); load(); };

  const handleRunCron = async (jobId: string) => {
    try { await api.runCronJob(jobId); load(); } catch (e) { console.error(e); }
  };

  const handleDeleteCron = async (jobId: string) => {
    try { await api.deleteCronJob(jobId); load(); } catch (e) { console.error(e); }
  };

  const buildSchedule = (): { kind: string; at?: string; everyMs?: number; expr?: string } | null => {
    if (cronForm.scheduleKind === "at") {
      if (!cronForm.scheduleAt.trim()) return null;
      const d = new Date(cronForm.scheduleAt);
      if (isNaN(d.getTime())) return null;
      return { kind: "at", at: d.toISOString() };
    }
    if (cronForm.scheduleKind === "every") {
      const n = parseInt(cronForm.everyAmount, 10) || 0;
      if (n <= 0) return null;
      const mult = cronForm.everyUnit === "minutes" ? 60000 : cronForm.everyUnit === "hours" ? 3600000 : 86400000;
      return { kind: "every", everyMs: n * mult };
    }
    if (cronForm.scheduleKind === "preset") {
      const p = SCHEDULE_PRESETS.find(
        (x) => (x.kind === "cron" && x.expr === cronForm.presetValue) || (x.kind === "every" && "everyMs" in x && String((x as any).everyMs) === cronForm.presetValue)
      );
      if (p?.kind === "cron") return { kind: "cron", expr: p.expr };
      if (p?.kind === "every" && "everyMs" in p) return { kind: "every", everyMs: (p as any).everyMs };
      const n = parseInt(cronForm.presetValue, 10);
      if (!isNaN(n) && n > 0) return { kind: "every", everyMs: n };
      return { kind: "cron", expr: cronForm.presetValue || "0 8 * * *" };
    }
    return { kind: "cron", expr: cronForm.advancedExpr.trim() || "0 8 * * *" };
  };

  const handleAddCron = async () => {
    if (!cronForm.name.trim() || !cronForm.text.trim()) return;
    const schedule = buildSchedule();
    if (!schedule) return;
    try {
      const body: any = {
        name: cronForm.name.trim(), schedule,
        payload: { kind: "systemEvent", text: cronForm.text.trim() },
        agent_id: currentAgentId || "main",
      };
      if (cronForm.scheduleKind === "at" && cronForm.deleteAfterRun) body.deleteAfterRun = true;
      await api.createCronJob(body);
      setCronForm({ name: "", text: "", scheduleKind: "preset", scheduleAt: "", everyAmount: "30", everyUnit: "minutes", presetValue: "0 8 * * *", advancedExpr: "0 8 * * *", deleteAfterRun: false });
      setCronAdding(false);
      load();
    } catch (e) { console.error(e); }
  };

  const formatTime = (ts: number) => {
    const d = new Date(ts);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    return isToday
      ? d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      : d.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 flex-shrink-0"
        style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-inset)" }}>
        <div className="flex items-center gap-2">
          <Heart className="w-4 h-4" style={{ color: "var(--accent)" }} />
          <span className="text-xs font-medium" style={{ color: "var(--text)" }}>{t.heartbeatAndCron}</span>
        </div>
        <div className="flex gap-0.5">
          <button onClick={handleRefresh} className="btn-ghost p-1.5" title="刷新">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button onClick={handleClear} className="btn-ghost p-1.5" title="清空列表">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden px-3 py-3 space-y-3">
        {/* Heartbeat 状态与开关 */}
        <div className="flex items-center justify-between gap-2 p-2.5 rounded-lg" style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-medium" style={{ color: "var(--text)" }}>
              {heartbeatConfig?.enabled ? t.heartbeatStatusOn : t.heartbeatStatusOff}
            </div>
            {heartbeatConfig?.enabled && heartbeatConfig?.every && (
              <div className="text-[10px] mt-0.5" style={{ color: "var(--text-secondary)" }}>
                {t.heartbeatIntervalLabel}: {heartbeatConfig.every}
              </div>
            )}
          </div>
          <button
            onClick={handleToggleHeartbeat}
            disabled={heartbeatToggling || heartbeatConfig == null}
            className="p-1 rounded transition-opacity disabled:opacity-50"
            title={heartbeatConfig?.enabled ? t.heartbeatStatusOff : t.heartbeatStatusOn}
          >
            {heartbeatConfig?.enabled ? (
              <ToggleRight className="w-5 h-5" style={{ color: "var(--success)" }} />
            ) : (
              <ToggleLeft className="w-5 h-5" style={{ color: "var(--text-tertiary)" }} />
            )}
          </button>
        </div>

        {/* Heartbeat events */}
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wider mb-2 px-1" style={{ color: "var(--text-tertiary)" }}>{t.heartbeatLabel}</div>
          {loading ? (
            <div className="text-xs py-4 text-center" style={{ color: "var(--text-tertiary)" }}>{t.loading}</div>
          ) : events.length === 0 ? (
            <div className="text-xs py-4 text-center" style={{ color: "var(--text-tertiary)" }}>
              {cleared ? t.clearedClickRefresh : t.noHeartbeatRecords}
            </div>
          ) : (
            <div className="space-y-2">
              {events.map((evt, i) => {
                const meta = STATUS_LABELS[evt.status] || { label: evt.status, icon: MinusCircle, color: "var(--text-tertiary)" };
                const Icon = meta.icon;
                const reasonText = evt.reason ? REASON_LABELS[evt.reason] || evt.reason : null;
                return (
                  <div key={`${evt.ts}-${i}`} className="glass-card p-2.5 text-xs">
                    <div className="flex items-center gap-2 mb-1">
                      <Icon className="w-3.5 h-3.5 flex-shrink-0" style={{ color: meta.color }} />
                      <span className="font-medium" style={{ color: "var(--text)" }}>{meta.label}</span>
                      {reasonText && (
                        <span className="text-[10px]" style={{ color: "var(--text-secondary)" }}>({reasonText})</span>
                      )}
                    </div>
                    <div className="text-[10px]" style={{ color: "var(--text-secondary)" }}>
                      {formatTime(evt.ts)}
                      {evt.duration_ms != null && <span className="ml-2">耗时 {evt.duration_ms}ms</span>}
                    </div>
                    {evt.preview && (
                      <div className="mt-1.5 pt-1.5 line-clamp-3" style={{ borderTop: "1px solid var(--border)", color: "var(--text)" }}>
                        {evt.preview}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Cron jobs */}
        <div>
          <div className="flex items-center justify-between">
            <button
              onClick={() => setCronExpanded(!cronExpanded)}
              className="flex items-center gap-1.5 flex-1 text-left px-1 py-1 rounded-lg transition-colors"
              onMouseEnter={e => (e.currentTarget.style.background = "var(--hover)")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              {cronExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              <Clock className="w-3 h-3" style={{ color: "var(--text-secondary)" }} />
              <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>{t.cronTasks} ({cronJobs.length})</span>
            </button>
            <button onClick={() => setCronAdding(!cronAdding)} className="btn-ghost p-1" title="新建">
              <Plus className="w-3 h-3" />
            </button>
          </div>
          {cronAdding && (
            <div className="mt-2 p-3 glass-card space-y-3">
              <input
                type="text" placeholder={t.taskName} value={cronForm.name}
                onChange={(e) => setCronForm((f) => ({ ...f, name: e.target.value }))}
                className="input text-xs"
              />
              <textarea
                placeholder="提醒内容" value={cronForm.text}
                onChange={(e) => setCronForm((f) => ({ ...f, text: e.target.value }))}
                rows={2} className="input text-xs resize-y"
              />
              <div className="space-y-2">
                <div className="text-[10px] font-medium" style={{ color: "var(--text-secondary)" }}>执行时间</div>
                <select
                  value={cronForm.scheduleKind}
                  onChange={(e) => setCronForm((f) => ({ ...f, scheduleKind: e.target.value as any }))}
                  className="input text-xs"
                >
                  <option value="at">{t.oneTimeTask}</option>
                  <option value="preset">{t.presetCron}</option>
                  <option value="every">{t.intervalCron}</option>
                  <option value="advanced">高级（cron 表达式）</option>
                </select>
                {cronForm.scheduleKind === "at" && (
                  <div className="space-y-1.5">
                    <input type="datetime-local" value={cronForm.scheduleAt}
                      onChange={(e) => setCronForm((f) => ({ ...f, scheduleAt: e.target.value }))}
                      className="input text-xs" />
                    <label className="flex items-center gap-1.5 text-xs" style={{ color: "var(--text)" }}>
                      <input type="checkbox" checked={cronForm.deleteAfterRun}
                        onChange={(e) => setCronForm((f) => ({ ...f, deleteAfterRun: e.target.checked }))}
                        className="rounded" />
                      执行后自动删除
                    </label>
                  </div>
                )}
                {cronForm.scheduleKind === "preset" && (
                  <select value={cronForm.presetValue}
                    onChange={(e) => setCronForm((f) => ({ ...f, presetValue: e.target.value }))}
                    className="input text-xs">
                    {SCHEDULE_PRESETS.map((p) => (
                      <option key={p.label} value={p.kind === "cron" ? p.expr : String((p as { everyMs?: number }).everyMs)}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                )}
                {cronForm.scheduleKind === "every" && (
                  <div className="flex gap-1.5">
                    <input type="number" min={1} value={cronForm.everyAmount}
                      onChange={(e) => setCronForm((f) => ({ ...f, everyAmount: e.target.value }))}
                      className="input flex-1 min-w-0 text-xs" />
                    <select value={cronForm.everyUnit}
                      onChange={(e) => setCronForm((f) => ({ ...f, everyUnit: e.target.value as any }))}
                      className="input text-xs" style={{ width: "auto" }}>
                      <option value="minutes">分钟</option>
                      <option value="hours">小时</option>
                      <option value="days">天</option>
                    </select>
                  </div>
                )}
                {cronForm.scheduleKind === "advanced" && (
                  <input type="text" placeholder="0 8 * * *" value={cronForm.advancedExpr}
                    onChange={(e) => setCronForm((f) => ({ ...f, advancedExpr: e.target.value }))}
                    className="input text-xs font-mono" />
                )}
              </div>
              <div className="flex gap-2 pt-1">
                <button onClick={handleAddCron}
                  disabled={!cronForm.name.trim() || !cronForm.text.trim() || (cronForm.scheduleKind === "at" && !cronForm.scheduleAt) || (cronForm.scheduleKind === "every" && !parseInt(cronForm.everyAmount, 10))}
                  className="btn-primary">
                  创建
                </button>
                <button onClick={() => setCronAdding(false)} className="btn-ghost">取消</button>
              </div>
            </div>
          )}
          {cronExpanded && (
            <div className="mt-1.5 space-y-2">
              {cronJobs.length === 0 ? (
                <div className="text-xs py-4 text-center" style={{ color: "var(--text-tertiary)" }}>{t.noCronTasks}</div>
              ) : (
                cronJobs.map((job) => (
                  <div key={job.id} className="glass-card p-2.5 text-xs">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="font-medium truncate" style={{ color: "var(--text)" }}>{job.name}</span>
                      <div className="flex gap-0.5 flex-shrink-0">
                        <button onClick={() => handleRunCron(job.id)} className="btn-ghost p-1" title="立即触发">
                          <Play className="w-3 h-3" />
                        </button>
                        <button onClick={() => handleDeleteCron(job.id)} className="btn-ghost p-1" title="删除"
                          style={{ color: "var(--text-secondary)" }}
                          onMouseEnter={e => (e.currentTarget.style.color = "var(--error)")}
                          onMouseLeave={e => (e.currentTarget.style.color = "var(--text-secondary)")}>
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                    <div className="text-[10px]" style={{ color: "var(--text-secondary)" }}>
                      {formatJobSchedule(job)} | {job.enabled ? t.enabled : t.disabled}
                      {job.deleteAfterRun && " · 执行后删除"}
                    </div>
                    {job.payload?.text && (
                      <div className="mt-1.5 pt-1.5 line-clamp-2 text-[10px]"
                        style={{ borderTop: "1px solid var(--border)", color: "var(--text)" }}>
                        {job.payload.text}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
