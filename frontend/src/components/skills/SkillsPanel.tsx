"use client";

import { useEffect, useState, useCallback } from "react";
import { useApp } from "@/lib/store";
import * as api from "@/lib/api";
import {
  Sparkles, ToggleLeft, ToggleRight, AlertCircle, CheckCircle2,
  XCircle, RefreshCw, ExternalLink, Search,
} from "lucide-react";

interface SkillDetail {
  name: string;
  description: string;
  version: string;
  location: string;
  enabled: boolean;
  status: string;
  missing_deps: string[];
  validation_errors: string[];
  always: boolean;
  emoji: string;
  body_preview: string;
}

function useStatusBadge() {
  const { t } = useApp();
  return {
    available: { label: t.statusAvailable, color: "var(--success, #22c55e)" },
    missing_deps: { label: t.statusMissingDeps, color: "var(--warning, #f59e0b)" },
    invalid: { label: t.statusInvalid, color: "var(--error, #ef4444)" },
  } as Record<string, { label: string; color: string }>;
}

export default function SkillsPanel() {
  const { currentAgentId, showNotice, skillsRefreshTrigger, t } = useApp();
  const [skills, setSkills] = useState<SkillDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [toggling, setToggling] = useState<string | null>(null);

  const loadSkills = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.fetchSkills(currentAgentId);
      setSkills(data);
    } catch (e: any) {
      showNotice({ kind: "error", text: `加载技能失败: ${e?.message || "未知错误"}` });
      setSkills([]);
    } finally {
      setLoading(false);
    }
  }, [currentAgentId, showNotice]);

  useEffect(() => { loadSkills(); }, [loadSkills, skillsRefreshTrigger]);

  const handleToggle = async (skill: SkillDetail) => {
    setToggling(skill.name);
    try {
      await api.updateSkillEnabled(currentAgentId, skill.name, !skill.enabled);
      await loadSkills();
    } catch (e: any) {
      showNotice({ kind: "error", text: `切换失败: ${e?.message || "未知错误"}` });
    } finally {
      setToggling(null);
    }
  };

  const filtered = skills.filter((s) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q);
  });

  const enabledCount = skills.filter((s) => s.enabled).length;
  const STATUS_BADGE = useStatusBadge();

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2" style={{ borderBottom: "1px solid var(--border)" }}>
        <Sparkles className="w-3.5 h-3.5" style={{ color: "var(--accent)" }} />
        <span className="text-[11px] font-semibold flex-1" style={{ color: "var(--text)" }}>
          {t.skillsManagement}
        </span>
        <span className="text-[10px]" style={{ color: "var(--text-secondary)" }}>
          {enabledCount}/{skills.length} {t.skillsEnabled}
        </span>
        <button onClick={loadSkills} className="btn-ghost p-1" type="button">
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} style={{ color: "var(--text-secondary)" }} />
        </button>
      </div>

      {/* Search */}
      <div className="px-3 py-1.5" style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg"
          style={{ background: "transparent", border: "1px solid var(--border)" }}>
          <Search className="w-3 h-3 flex-shrink-0" style={{ color: "var(--text-tertiary)" }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t.searchSkills}
            className="flex-1 bg-transparent text-[11px] outline-none placeholder:text-[var(--text-tertiary)]"
            style={{ color: "var(--text)" }}
          />
          {searchQuery && (
            <button onClick={() => setSearchQuery("")} className="flex-shrink-0" type="button">
              <XCircle className="w-3 h-3" style={{ color: "var(--text-tertiary)" }} />
            </button>
          )}
        </div>
      </div>

      {/* Skills List */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
        {filtered.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center py-12 gap-2">
            <Sparkles className="w-8 h-8" style={{ color: "var(--text-tertiary)" }} />
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
              {searchQuery ? t.noMatchSkills : t.noSkills}
            </p>
          </div>
        )}

        {filtered.map((skill) => {
          const badge = STATUS_BADGE[skill.status] || STATUS_BADGE.available;
          const isToggling = toggling === skill.name;

          return (
            <div
              key={skill.name}
              className="rounded-lg p-3 transition-colors"
              style={{
                background: "var(--bg-elevated)",
                border: `1px solid ${skill.enabled ? "var(--accent)" + "30" : "var(--border)"}`,
                opacity: skill.enabled ? 1 : 0.7,
              }}
            >
              <div className="flex items-start gap-2">
                {/* Emoji */}
                <span className="text-base mt-0.5">{skill.emoji || "🧩"}</span>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-medium" style={{ color: "var(--text)" }}>
                      {skill.name}
                    </span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded-full"
                      style={{ color: badge.color, background: badge.color + "18", border: `1px solid ${badge.color}30` }}>
                      {badge.label}
                    </span>
                    {skill.version && (
                      <span className="text-[9px]" style={{ color: "var(--text-tertiary)" }}>
                        v{skill.version}
                      </span>
                    )}
                  </div>
                  <p className="text-[10px] mt-0.5" style={{ color: "var(--text-secondary)" }}>
                    {skill.description}
                  </p>

                  {skill.missing_deps.length > 0 && (
                    <div className="flex items-center gap-1 mt-1">
                      <AlertCircle className="w-3 h-3 flex-shrink-0" style={{ color: "var(--warning)" }} />
                      <span className="text-[9px]" style={{ color: "var(--warning)" }}>
                        {t.missingLabel}: {skill.missing_deps.join(", ")}
                      </span>
                    </div>
                  )}

                  {skill.validation_errors.length > 0 && (
                    <div className="flex items-center gap-1 mt-1">
                      <XCircle className="w-3 h-3 flex-shrink-0" style={{ color: "var(--error)" }} />
                      <span className="text-[9px]" style={{ color: "var(--error)" }}>
                        {skill.validation_errors.join("; ")}
                      </span>
                    </div>
                  )}
                </div>

                {/* Toggle */}
                <button
                  onClick={() => handleToggle(skill)}
                  disabled={isToggling || skill.always}
                  className="transition-colors flex-shrink-0 mt-0.5"
                  type="button"
                  title={skill.always ? t.alwaysEnabled : skill.enabled ? t.clickToDisable : t.clickToEnable}
                >
                  {skill.enabled ? (
                    <ToggleRight className={`w-5 h-5 ${isToggling ? "animate-pulse" : ""}`}
                      style={{ color: "var(--accent)" }} />
                  ) : (
                    <ToggleLeft className={`w-5 h-5 ${isToggling ? "animate-pulse" : ""}`}
                      style={{ color: "var(--text-tertiary)" }} />
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
