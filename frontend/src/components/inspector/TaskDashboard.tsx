"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Clock, Play, XCircle, RefreshCw, Filter,
  CheckCircle2, AlertCircle, Loader2, Timer, Bell, Zap,
} from "lucide-react";
import { useApp } from "@/lib/store";
import type { Messages } from "@/lib/i18n/locales";

const API_BASE = typeof window !== "undefined"
  ? `http://${window.location.hostname}:8002/api`
  : "http://localhost:8002/api";

interface TaskItem {
  id: string;
  kind: string;
  agent_id: string;
  name: string;
  status: string;
  created_at_ms: number;
  started_at_ms: number | null;
  ended_at_ms: number | null;
  duration_ms: number | null;
  retry_count: number;
  max_retries: number;
  error: string | null;
  preview: string | null;
  source_job_id: string | null;
}

function getStatusConfig(t: Messages) {
  return {
    success: { icon: CheckCircle2, color: "var(--success, #22c55e)", label: t.success },
    failed: { icon: AlertCircle, color: "var(--error, #ef4444)", label: t.failed },
    running: { icon: Loader2, color: "var(--accent, #3b82f6)", label: t.running },
    pending: { icon: Clock, color: "var(--text-secondary)", label: t.pending },
    cancelled: { icon: XCircle, color: "var(--text-tertiary)", label: t.cancelled },
    retrying: { icon: RefreshCw, color: "var(--warning, #f59e0b)", label: t.retrying },
  } as Record<string, { icon: typeof CheckCircle2; color: string; label: string }>;
}

function getKindConfig(t: Messages) {
  return {
    heartbeat: { icon: Timer, label: t.heartbeat },
    cron: { icon: Clock, label: t.cron },
    reminder: { icon: Bell, label: t.reminder },
    system: { icon: Zap, label: t.system },
  } as Record<string, { icon: typeof Clock; label: string }>;
}

function formatTime(ms: number, locale: string): string {
  const d = new Date(ms);
  return d.toLocaleString(locale, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

function formatDate(ms: number, locale: string): string {
  const d = new Date(ms);
  return d.toLocaleDateString(locale, { month: "2-digit", day: "2-digit" });
}

function formatDuration(ms: number | null): string {
  if (!ms) return "-";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms / 60000)}m`;
}

export default function TaskDashboard({ agentId }: { agentId: string }) {
  const { t, locale } = useApp();
  const STATUS_CONFIG = getStatusConfig(t);
  const KIND_CONFIG = getKindConfig(t);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [kindFilter, setKindFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const loadTasks = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("agent_id", agentId);
      params.set("limit", "50");
      if (kindFilter !== "all") params.set("kind", kindFilter);
      if (statusFilter !== "all") params.set("status", statusFilter);
      const resp = await fetch(`${API_BASE}/tasks/history?${params}`);
      const data = await resp.json();
      setTasks(data.items || []);
      setTotal(data.total || 0);
    } catch {
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, [agentId, kindFilter, statusFilter]);

  useEffect(() => { loadTasks(); }, [loadTasks]);

  useEffect(() => {
    const timer = setInterval(loadTasks, 30000);
    return () => clearInterval(timer);
  }, [loadTasks]);

  const handleCancel = async (taskId: string) => {
    try {
      await fetch(`${API_BASE}/tasks/${taskId}/cancel`, { method: "POST" });
      loadTasks();
    } catch { /* ignore */ }
  };

  let lastDate = "";

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2" style={{ borderBottom: "1px solid var(--border)" }}>
        <Clock className="w-3.5 h-3.5" style={{ color: "var(--accent)" }} />
        <span className="text-[11px] font-semibold flex-1" style={{ color: "var(--text)" }}>
          {t.taskHistory}
        </span>
        <span className="text-[10px]" style={{ color: "var(--text-secondary)" }}>{total} {t.taskItems}</span>
        <button onClick={loadTasks} className="btn-ghost p-1" type="button">
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} style={{ color: "var(--text-secondary)" }} />
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-1.5 px-3 py-1.5" style={{ borderBottom: "1px solid var(--border)" }}>
        <select
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value)}
          className="text-[10px] rounded px-1.5 py-0.5"
          style={{ background: "var(--bg-inset)", border: "1px solid var(--border)", color: "var(--text)" }}
        >
          <option value="all">{t.allTypes}</option>
          <option value="heartbeat">{t.heartbeat}</option>
          <option value="cron">{t.cron}</option>
          <option value="reminder">{t.reminder}</option>
          <option value="system">{t.system}</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-[10px] rounded px-1.5 py-0.5"
          style={{ background: "var(--bg-inset)", border: "1px solid var(--border)", color: "var(--text)" }}
        >
          <option value="all">{t.allStatus}</option>
          <option value="success">{t.success}</option>
          <option value="failed">{t.failed}</option>
          <option value="running">{t.running}</option>
          <option value="retrying">{t.retrying}</option>
          <option value="cancelled">{t.cancelled}</option>
        </select>
      </div>

      {/* Timeline */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-0.5">
        {tasks.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center py-12 gap-2">
            <Clock className="w-8 h-8" style={{ color: "var(--text-tertiary)" }} />
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{t.noTasks}</p>
          </div>
        )}
        {tasks.map((task) => {
          const statusCfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
          const kindCfg = KIND_CONFIG[task.kind] || KIND_CONFIG.system;
          const StatusIcon = statusCfg.icon;
          const KindIcon = kindCfg.icon;

          const date = formatDate(task.created_at_ms, locale);
          const showDate = date !== lastDate;
          lastDate = date;

          return (
            <div key={task.id}>
              {showDate && (
                <div className="text-[9px] font-semibold uppercase tracking-wider py-1.5 mt-1"
                  style={{ color: "var(--text-tertiary)" }}>
                  {date}
                </div>
              )}
              <div className="flex items-start gap-2 py-1.5 px-2 rounded-lg transition-colors group"
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--hover)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                {/* Timeline dot */}
                <div className="flex flex-col items-center mt-0.5">
                  <div className="w-2 h-2 rounded-full" style={{ background: statusCfg.color }} />
                  <div className="w-px flex-1 min-h-[16px]" style={{ background: "var(--border)" }} />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <KindIcon className="w-3 h-3 flex-shrink-0" style={{ color: "var(--text-secondary)" }} />
                    <span className="text-[11px] font-medium truncate" style={{ color: "var(--text)" }}>
                      {task.name || `${kindCfg.label}`}
                    </span>
                    <span className="ml-auto text-[9px] flex-shrink-0" style={{ color: "var(--text-tertiary)" }}>
                      {formatTime(task.created_at_ms, locale)}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <StatusIcon className={`w-3 h-3 flex-shrink-0 ${task.status === "running" ? "animate-spin" : ""}`}
                      style={{ color: statusCfg.color }} />
                    <span className="text-[10px]" style={{ color: statusCfg.color }}>{statusCfg.label}</span>
                    {task.duration_ms != null && (
                      <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>
                        {formatDuration(task.duration_ms)}
                      </span>
                    )}
                    {task.retry_count > 0 && (
                      <span className="text-[9px] px-1 py-0.5 rounded"
                        style={{ background: "var(--warning-bg)", color: "var(--warning)" }}>
                        {t.retry} {task.retry_count}/{task.max_retries}
                      </span>
                    )}
                    {(task.status === "running" || task.status === "pending") && (
                      <button onClick={() => handleCancel(task.id)}
                        className="btn-ghost p-0.5 ml-auto opacity-0 group-hover:opacity-100 transition-opacity"
                        type="button">
                        <XCircle className="w-3 h-3" style={{ color: "var(--error)" }} />
                      </button>
                    )}
                  </div>
                  {task.error && (
                    <p className="text-[10px] mt-0.5 truncate" style={{ color: "var(--error)" }}>
                      {task.error}
                    </p>
                  )}
                  {task.preview && (
                    <p className="text-[10px] mt-0.5 truncate" style={{ color: "var(--text-secondary)" }}>
                      {task.preview}
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
