"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import * as api from "../api";

interface SubagentInfo {
  run_id: string;
  task: string;
  status: string;
}

export function useSubagents(
  currentAgentId: string,
  currentSessionId: string | null,
  onSubagentDone?: () => void,
) {
  const [runningSubagents, setRunningSubagents] = useState<SubagentInfo[]>([]);
  const refreshTimerRef = useRef<number | null>(null);

  const refreshSubagents = useCallback(async () => {
    if (!currentSessionId) return;
    try {
      const resp = await api.fetchSubagents(currentAgentId, currentSessionId);
      const data = resp.flat || [];
      const running = data
        .filter((s: any) => (s.state || s.status) === "running")
        .map((s: any) => ({
          run_id: s.run_id,
          task: s.task?.slice(0, 60) || "",
          status: s.state || s.status,
        }));
      setRunningSubagents(running);
    } catch {
      setRunningSubagents([]);
    }
  }, [currentAgentId, currentSessionId]);

  useEffect(() => {
    if (!currentSessionId) return;
    refreshSubagents();
    const id = setInterval(refreshSubagents, 2500);
    return () => clearInterval(id);
  }, [currentSessionId, refreshSubagents]);

  useEffect(() => {
    const triggerRefresh = () => {
      if (refreshTimerRef.current) window.clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = window.setTimeout(refreshSubagents, 120);
    };

    const unsubscribe = api.subscribeAgentEvents(
      currentAgentId,
      (event) => {
        const type = event.type || "";
        if (!type.startsWith("subagent_")) return;
        triggerRefresh();
        if (type === "subagent_done" || type === "subagent_error" || type === "subagent_killed") {
          onSubagentDone?.();
        }
      },
      () => { },
    );

    return () => {
      unsubscribe();
      if (refreshTimerRef.current) {
        window.clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [currentAgentId, currentSessionId, onSubagentDone, refreshSubagents]);

  return { runningSubagents };
}
