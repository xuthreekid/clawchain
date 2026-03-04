"use client";

import { useApp } from "@/lib/store";
import * as api from "@/lib/api";
import { AlertTriangle, ShieldAlert, FileEdit, Check, X } from "lucide-react";
import type { Messages } from "@/lib/i18n/locales";

type RiskLevel = "safe" | "caution" | "danger";

const TOOL_RISK: Record<string, RiskLevel> = {
  exec: "danger",
  process_kill: "danger",
  delete: "danger",
  write: "caution",
  edit: "caution",
  apply_patch: "caution",
  python_repl: "caution",
};

function getRisk(tool: string): RiskLevel {
  return TOOL_RISK[tool] ?? "caution";
}

function getRiskConfig(t: Messages) {
  return {
    safe: {
      icon: Check,
      label: t.riskSafe,
      color: "var(--success, #22c55e)",
      border: "var(--success, #22c55e)",
      bg: "rgba(34,197,94,0.08)",
    },
    caution: {
      icon: FileEdit,
      label: t.riskCaution,
      color: "var(--warning, #f59e0b)",
      border: "var(--warning, #f59e0b)",
      bg: "rgba(245,158,11,0.08)",
    },
    danger: {
      icon: ShieldAlert,
      label: t.riskDanger,
      color: "var(--error, #ef4444)",
      border: "var(--error, #ef4444)",
      bg: "rgba(239,68,68,0.08)",
    },
  } as Record<RiskLevel, { icon: typeof AlertTriangle; label: string; color: string; border: string; bg: string }>;
}

function toolLabel(tool: string, t: Messages): string {
  const map: Record<string, string> = {
    exec: t.toolExec,
    process_kill: t.toolProcessKill,
    write: t.toolWrite,
    edit: t.toolEdit,
    delete: t.toolDelete,
    apply_patch: t.toolApplyPatch,
    python_repl: t.toolPythonRepl,
  };
  return map[tool] ?? tool;
}

export default function ApprovalModal() {
  const { pendingApproval, setPendingApproval, showNotice, t } = useApp();

  if (!pendingApproval) return null;

  const risk = getRisk(pendingApproval.tool);
  const RISK_CONFIG = getRiskConfig(t);
  const cfg = RISK_CONFIG[risk];
  const Icon = cfg.icon;

  const handle = async (decision: "approved" | "denied") => {
    try {
      await api.resolveApproval(pendingApproval.approval_id, decision);
      setPendingApproval(null);
      if (decision === "denied") {
        showNotice({ kind: "info", text: t.denied });
      }
    } catch (e: any) {
      showNotice({ kind: "error", text: e?.message || "Request failed" });
      setPendingApproval(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[300] flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.45)" }}
    >
      <div
        className="glass-card max-w-lg w-[90%] p-5 shadow-xl"
        style={{ border: `1.5px solid ${cfg.border}`, background: cfg.bg }}
      >
        <div className="flex items-center gap-2 mb-3">
          <div
            className="flex items-center justify-center w-7 h-7 rounded-full"
            style={{ background: cfg.color + "22" }}
          >
            <Icon className="w-4 h-4" style={{ color: cfg.color }} />
          </div>
          <span className="text-sm font-semibold" style={{ color: cfg.color }}>
            {cfg.label}
          </span>
          <span
            className="ml-auto text-[10px] px-2 py-0.5 rounded-full font-medium uppercase tracking-wide"
            style={{
              color: cfg.color,
              background: cfg.color + "18",
              border: `1px solid ${cfg.color}40`,
            }}
          >
            {risk}
          </span>
        </div>

        <p className="text-xs mb-2" style={{ color: "var(--text-secondary)" }}>
          {t.approvalDesc} <strong>{toolLabel(pendingApproval.tool, t)}</strong>
        </p>

        <pre
          className="p-3 rounded-lg text-xs overflow-x-auto mb-4 whitespace-pre-wrap break-all"
          style={{
            background: "var(--bg-inset)",
            border: "1px solid var(--border)",
            color: "var(--text)",
            maxHeight: 160,
          }}
        >
          {pendingApproval.input_preview || "—"}
        </pre>

        {risk === "danger" && (
          <p
            className="text-[11px] mb-3 px-2 py-1.5 rounded"
            style={{
              color: "var(--error, #ef4444)",
              background: "rgba(239,68,68,0.06)",
              border: "1px solid rgba(239,68,68,0.15)",
            }}
          >
            {t.approvalDangerWarn}
          </p>
        )}

        <div className="flex gap-2 justify-end">
          <button
            onClick={() => handle("denied")}
            className="btn-ghost flex items-center gap-1.5 px-3 py-1.5 text-xs"
            style={{ color: "var(--text-secondary)" }}
          >
            <X className="w-3.5 h-3.5" />
            {t.deny}
          </button>
          <button
            onClick={() => handle("approved")}
            className="btn-primary flex items-center gap-1.5 px-3 py-1.5 text-xs"
            style={
              risk === "danger"
                ? { background: "var(--error, #ef4444)", borderColor: "var(--error, #ef4444)" }
                : {}
            }
          >
            <Check className="w-3.5 h-3.5" />
            {risk === "danger" ? t.confirmExec : t.approve}
          </button>
        </div>
      </div>
    </div>
  );
}
