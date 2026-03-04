"""Turn 生命周期追踪"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallRecord:
    tool: str
    input: Any
    output: str = ""
    started_at: float = 0.0
    ended_at: float = 0.0
    error: str | None = None


@dataclass
class TurnRecord:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: str = ""
    session_id: str = ""
    started_at: float = field(default_factory=time.time)
    ended_at: float = 0.0
    phase: str = "pending"  # pending -> running -> completed / error
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int = 0
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    error: str | None = None
    compressed: bool = False

    @property
    def duration_ms(self) -> int:
        if self.ended_at:
            return int((self.ended_at - self.started_at) * 1000)
        return int((time.time() - self.started_at) * 1000)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "phase": self.phase,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "total_tokens": self.total_tokens,
            "tool_calls_count": len(self.tool_calls),
            "duration_ms": self.duration_ms,
            "error": self.error,
            "compressed": self.compressed,
        }


class RunTracker:
    """追踪所有进行中和已完成的 Turn"""

    def __init__(self):
        self._active: dict[str, TurnRecord] = {}
        self._history: list[TurnRecord] = []
        self._event_listeners: list[Any] = []

    def start_turn(self, agent_id: str, session_id: str) -> TurnRecord:
        record = TurnRecord(agent_id=agent_id, session_id=session_id)
        record.phase = "running"
        self._active[record.run_id] = record
        self._emit("turn_start", record)
        return record

    def record_tool_start(self, run_id: str, tool: str, tool_input: Any) -> None:
        record = self._active.get(run_id)
        if not record:
            return
        tc = ToolCallRecord(tool=tool, input=tool_input, started_at=time.time())
        record.tool_calls.append(tc)
        self._emit("tool_start", record, {"tool": tool, "input": tool_input})

    def record_tool_end(
        self, run_id: str, tool: str, output: str, error: str | None = None
    ) -> None:
        record = self._active.get(run_id)
        if not record:
            return
        for tc in reversed(record.tool_calls):
            if tc.tool == tool and not tc.ended_at:
                tc.output = output[:2000]
                tc.ended_at = time.time()
                tc.error = error
                break
        self._emit("tool_end", record, {"tool": tool, "output": output[:500]})

    def record_tokens(
        self,
        run_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read: int = 0,
        cache_write: int = 0,
    ) -> None:
        record = self._active.get(run_id)
        if not record:
            return
        record.input_tokens += input_tokens
        record.output_tokens += output_tokens
        record.cache_read_tokens += cache_read
        record.cache_write_tokens += cache_write
        record.total_tokens = (
            record.input_tokens + record.output_tokens
            + record.cache_read_tokens + record.cache_write_tokens
        )

    def complete_turn(self, run_id: str) -> TurnRecord | None:
        record = self._active.pop(run_id, None)
        if not record:
            return None
        record.ended_at = time.time()
        record.phase = "completed"
        self._history.append(record)
        self._emit("turn_end", record)
        return record

    def error_turn(self, run_id: str, error: str) -> TurnRecord | None:
        record = self._active.pop(run_id, None)
        if not record:
            return None
        record.ended_at = time.time()
        record.phase = "error"
        record.error = error
        self._history.append(record)
        self._emit("turn_error", record, {"error": error})
        return record

    def get_active(self, run_id: str) -> TurnRecord | None:
        return self._active.get(run_id)

    def get_session_history(
        self, agent_id: str, session_id: str
    ) -> list[TurnRecord]:
        return [
            r for r in self._history
            if r.agent_id == agent_id and r.session_id == session_id
        ]

    def get_cumulative_usage(
        self, agent_id: str, session_id: str | None = None
    ) -> dict[str, int]:
        records = [
            r for r in self._history
            if r.agent_id == agent_id
            and (session_id is None or r.session_id == session_id)
        ]
        return {
            "input_tokens": sum(r.input_tokens for r in records),
            "output_tokens": sum(r.output_tokens for r in records),
            "cache_read_tokens": sum(r.cache_read_tokens for r in records),
            "cache_write_tokens": sum(r.cache_write_tokens for r in records),
            "total_tokens": sum(r.total_tokens for r in records),
            "turns": len(records),
        }

    def add_listener(self, callback: Any) -> None:
        self._event_listeners.append(callback)

    def _emit(self, event_type: str, record: TurnRecord, extra: dict | None = None) -> None:
        data = {"event": event_type, "record": record.to_dict()}
        if extra:
            data.update(extra)
        for listener in self._event_listeners:
            try:
                listener(data)
            except Exception:
                pass


run_tracker = RunTracker()
