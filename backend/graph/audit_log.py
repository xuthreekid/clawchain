"""审计日志 — JSONL 格式记录所有 Agent 操作"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from config import resolve_agent_dir


class AuditLogger:
    """将 Agent 运行事件写入 JSONL 日志文件"""

    def _log_path(self, agent_id: str) -> Path:
        log_dir = resolve_agent_dir(agent_id) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / "audit.jsonl"

    def log(self, agent_id: str, event_type: str, data: dict[str, Any] | None = None) -> None:
        entry = {
            "ts": time.time(),
            "agent_id": agent_id,
            "event": event_type,
        }
        if data:
            entry["data"] = data

        path = self._log_path(agent_id)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def log_turn_start(self, agent_id: str, run_id: str, session_id: str) -> None:
        self.log(agent_id, "turn_start", {
            "run_id": run_id,
            "session_id": session_id,
        })

    def log_turn_end(
        self,
        agent_id: str,
        run_id: str,
        session_id: str,
        tokens: dict[str, int] | None = None,
        tool_calls: int = 0,
        duration_ms: int = 0,
    ) -> None:
        self.log(agent_id, "turn_end", {
            "run_id": run_id,
            "session_id": session_id,
            "tokens": tokens or {},
            "tool_calls": tool_calls,
            "duration_ms": duration_ms,
        })

    def log_turn_error(self, agent_id: str, run_id: str, error: str) -> None:
        self.log(agent_id, "turn_error", {
            "run_id": run_id,
            "error": error[:1000],
        })

    def log_tool_call(
        self,
        agent_id: str,
        run_id: str,
        tool: str,
        tool_input: Any,
        output: str,
        duration_ms: int = 0,
    ) -> None:
        self.log(agent_id, "tool_call", {
            "run_id": run_id,
            "tool": tool,
            "input": str(tool_input)[:500],
            "output": output[:500],
            "duration_ms": duration_ms,
        })

    def log_compress(
        self, agent_id: str, session_id: str, archived: int, remaining: int
    ) -> None:
        self.log(agent_id, "compress", {
            "session_id": session_id,
            "archived": archived,
            "remaining": remaining,
        })

    def log_memory_event(
        self, agent_id: str, event_type: str, path: str = "", detail: str = ""
    ) -> None:
        self.log(agent_id, f"memory_{event_type}", {
            "path": path,
            "detail": detail[:500],
        })

    def read_recent(self, agent_id: str, limit: int = 50) -> list[dict[str, Any]]:
        path = self._log_path(agent_id)
        if not path.exists():
            return []

        try:
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            recent = lines[-limit:]
            return [json.loads(line) for line in recent]
        except Exception:
            return []


audit_logger = AuditLogger()
