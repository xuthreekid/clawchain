"""子 Agent 注册表"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal


@dataclass
class SubagentRunRecord:
    run_id: str
    child_session_key: str
    requester_session_key: str
    requester_agent_id: str
    target_agent_id: str
    task: str
    label: str | None = None
    model: str | None = None
    cleanup: Literal["delete", "keep"] = "keep"
    spawn_depth: int = 0
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    ended_at: float | None = None
    outcome: str | None = None
    result_summary: str | None = None
    asyncio_task: Any = field(default=None, repr=False)
    # 创建后 N 分钟从 registry 删除并归档会话
    archive_at_ms: float | None = None
    # announce 重试
    announce_retry_count: int = 0
    last_announce_retry_at: float | None = None
    # webchat 展示/调度元数据
    state: str = "running"
    terminal_reason: str | None = None
    announce_state: str = "pending"


def _resolve_archive_after_ms() -> float | None:
    """从 config 读取 archive_after_minutes，返回毫秒数"""
    try:
        from config import get_config
        cfg = get_config()
        minutes = cfg.get("agents", {}).get("defaults", {}).get("subagents", {}).get("archive_after_minutes", 60)
        if not isinstance(minutes, (int, float)) or minutes <= 0:
            return None
        return max(1, int(minutes)) * 60_000
    except Exception:
        return 60 * 60_000  # 默认 60 分钟


class SubagentRegistry:
    def __init__(self):
        self._runs: dict[str, SubagentRunRecord] = {}
        self._restore_from_disk()

    def _restore_from_disk(self) -> None:
        from graph.subagent_registry_state import restore_registry_from_disk
        restore_registry_from_disk(self._runs, merge_only=False)

    def _persist_to_disk(self) -> None:
        from graph.subagent_registry_state import save_registry_to_disk
        save_registry_to_disk(self._runs)

    def register_run(
        self,
        run_id: str,
        child_session_key: str,
        requester_session_key: str,
        requester_agent_id: str,
        target_agent_id: str,
        task: str,
        label: str | None = None,
        model: str | None = None,
        cleanup: str = "keep",
        spawn_depth: int = 0,
    ) -> SubagentRunRecord:
        now = time.time()
        archive_after_ms = _resolve_archive_after_ms()
        archive_at_ms = (now * 1000 + archive_after_ms) if archive_after_ms else None

        record = SubagentRunRecord(
            run_id=run_id,
            child_session_key=child_session_key,
            requester_session_key=requester_session_key,
            requester_agent_id=requester_agent_id,
            target_agent_id=target_agent_id,
            task=task,
            label=label,
            model=model,
            cleanup=cleanup,  # type: ignore
            spawn_depth=spawn_depth,
            archive_at_ms=archive_at_ms,
        )
        self._runs[run_id] = record
        self._persist_to_disk()
        return record

    def set_task(self, run_id: str, task: Any) -> None:
        if run_id in self._runs:
            self._runs[run_id].asyncio_task = task

    def mark_started(self, run_id: str) -> None:
        if run_id in self._runs:
            self._runs[run_id].started_at = time.time()
            self._runs[run_id].state = "running"
            self._persist_to_disk()

    def mark_completed(
        self,
        run_id: str,
        result_summary: str = "",
        outcome: str = "completed",
        terminal_reason: str | None = None,
    ) -> None:
        if run_id in self._runs:
            self._runs[run_id].ended_at = time.time()
            self._runs[run_id].outcome = outcome
            self._runs[run_id].result_summary = result_summary[:1000]
            self._runs[run_id].state = "succeeded"
            self._runs[run_id].terminal_reason = terminal_reason
            self._persist_to_disk()

    def mark_terminated(self, run_id: str, reason: str = "killed") -> None:
        if run_id in self._runs:
            self._runs[run_id].ended_at = time.time()
            self._runs[run_id].outcome = reason
            lowered = (reason or "").lower()
            if "timeout" in lowered:
                self._runs[run_id].state = "timed_out"
            elif "killed" in lowered or "cancel" in lowered:
                self._runs[run_id].state = "cancelled"
            elif "orphaned" in lowered:
                self._runs[run_id].state = "orphaned"
            elif "restart-interrupted" in lowered:
                self._runs[run_id].state = "interrupted"
            else:
                self._runs[run_id].state = "failed"
            self._runs[run_id].terminal_reason = reason
            self._persist_to_disk()

    def kill(self, run_id: str, cascade: bool = True) -> bool:
        """终止 run，cascade=True 时递归终止其子 runs"""
        record = self._runs.get(run_id)
        if record is None:
            return False
        # Only running runs are killable; completed runs must stay immutable.
        if record.ended_at is not None:
            return False
        if cascade:
            child_sk = self.session_key_from_child_session_key(record.child_session_key)
            for r in list(self._runs.values()):
                if r.requester_session_key == child_sk and r.ended_at is None:
                    self.kill(r.run_id, cascade=True)
        if record.asyncio_task:
            try:
                if hasattr(record.asyncio_task, "cancel"):
                    record.asyncio_task.cancel()
            except Exception:
                pass
        self.mark_terminated(run_id, "killed")
        return True

    def list_runs_for_requester(
        self, requester_key: str, include_recent_minutes: int = 30
    ) -> list[SubagentRunRecord]:
        cutoff = time.time() - include_recent_minutes * 60
        results = []
        for r in self._runs.values():
            if r.requester_session_key != requester_key:
                continue
            if r.ended_at is not None and r.ended_at < cutoff:
                continue
            results.append(r)
        results.sort(key=lambda r: r.created_at, reverse=True)
        return results

    def count_active_for_requester(self, requester_key: str) -> int:
        return sum(
            1 for r in self._runs.values()
            if r.requester_session_key == requester_key and r.ended_at is None
        )

    def get_run(self, run_id: str) -> SubagentRunRecord | None:
        return self._runs.get(run_id)

    def mark_announce_retry(self, run_id: str) -> bool:
        """标记 announce 重试，返回是否可继续重试（未超限且未过期）"""
        r = self._runs.get(run_id)
        if not r:
            return False
        MAX_RETRY = 3
        EXPIRE_MS = 5 * 60 * 1000
        if r.announce_retry_count >= MAX_RETRY:
            return False
        if r.ended_at and (time.time() * 1000 - r.ended_at * 1000) > EXPIRE_MS:
            return False
        r.announce_retry_count = getattr(r, "announce_retry_count", 0) + 1
        r.last_announce_retry_at = time.time()
        r.announce_state = "retrying"
        self._persist_to_disk()
        return True

    def mark_announce_delivered(self, run_id: str) -> None:
        r = self._runs.get(run_id)
        if not r:
            return
        r.announce_state = "delivered"
        self._persist_to_disk()

    def mark_announce_dropped(self, run_id: str) -> None:
        r = self._runs.get(run_id)
        if not r:
            return
        r.announce_state = "dropped"
        self._persist_to_disk()

    def get_requester_depth(self, requester_session_key: str) -> int:
        """Depth 0 = main, 1 = subagent, 2 = sub-subagent

        通过 registry 查找：requester 作为 child 被 spawn 时，其 spawn_depth - 1 即为 requester 深度。
        主会话无对应 run，返回 0。
        """
        key = (requester_session_key or "").strip()
        if not key or "agent:" not in key:
            return 0
        parts = key.split(":")
        if len(parts) < 3:
            return 0
        agent_id = parts[1]
        session_part = ":".join(parts[2:])
        if not session_part:
            return 0
        if not session_part.startswith("subagent"):
            return 0
        child_key_candidate = f"agent:{agent_id}:subagent:{session_part}"
        for r in self._runs.values():
            if r.child_session_key == child_key_candidate:
                return max(0, r.spawn_depth - 1)
        return 0

    @staticmethod
    def session_key_from_child_session_key(child_session_key: str) -> str:
        """agent:id:subagent:session_id -> agent:id:session_id"""
        parts = (child_session_key or "").split(":")
        if len(parts) >= 4:
            return f"{parts[0]}:{parts[1]}:{parts[-1]}"
        return child_session_key or ""

    def list_descendant_runs(
        self, root_session_key: str, include_recent_minutes: int = 60
    ) -> list[SubagentRunRecord]:
        """从 root 起 BFS 收集所有后代 runs"""
        cutoff = time.time() - include_recent_minutes * 60
        root = (root_session_key or "").strip()
        if not root:
            return []
        pending = [root]
        visited: set[str] = {root}
        descendants: list[SubagentRunRecord] = []
        while pending:
            requester = pending.pop(0)
            for r in self._runs.values():
                if r.requester_session_key != requester:
                    continue
                if r.ended_at is not None and r.ended_at < cutoff:
                    continue
                descendants.append(r)
                child_sk = self.session_key_from_child_session_key(r.child_session_key)
                if child_sk and child_sk not in visited:
                    visited.add(child_sk)
                    pending.append(child_sk)
        return sorted(descendants, key=lambda x: x.created_at, reverse=True)

    def resolve_requester_for_child_session(
        self, child_session_key: str
    ) -> tuple[str, str] | None:
        """给定 child_session_key，返回 (requester_session_key, requester_agent_id)"""
        key = (child_session_key or "").strip()
        if not key:
            return None
        best: SubagentRunRecord | None = None
        for r in self._runs.values():
            if r.child_session_key != key:
                continue
            if best is None or r.created_at > best.created_at:
                best = r
        if best is None:
            return None
        return (best.requester_session_key, best.requester_agent_id)

    def count_active_descendant_runs(self, root_session_key: str) -> int:
        """root 下尚未结束的后代 run 数量"""
        root = (root_session_key or "").strip()
        if not root:
            return 0
        pending = [root]
        visited: set[str] = {root}
        count = 0
        while pending:
            requester = pending.pop(0)
            for r in self._runs.values():
                if r.requester_session_key != requester:
                    continue
                if r.ended_at is None:
                    count += 1
                child_sk = self.session_key_from_child_session_key(r.child_session_key)
                if child_sk and child_sk not in visited:
                    visited.add(child_sk)
                    pending.append(child_sk)
        return count

    def cleanup_old(self, max_age_hours: int = 24) -> int:
        cutoff = time.time() - max_age_hours * 3600
        to_remove = [
            rid for rid, r in self._runs.items()
            if r.ended_at is not None and r.ended_at < cutoff
        ]
        for rid in to_remove:
            del self._runs[rid]
        if to_remove:
            self._persist_to_disk()
        return len(to_remove)

    def replace_run_after_steer(
        self,
        previous_run_id: str,
        next_run_id: str,
        task: str,
        fallback: SubagentRunRecord | None = None,
    ) -> SubagentRunRecord | None:
        """steer 后替换 run，新 run 继承原 run 的上下文"""
        prev = self._runs.get(previous_run_id) or fallback
        if not prev:
            return None
        if previous_run_id != next_run_id:
            del self._runs[previous_run_id]
        now = time.time()
        archive_after_ms = _resolve_archive_after_ms()
        archive_at_ms = (now * 1000 + archive_after_ms) if archive_after_ms else None
        record = SubagentRunRecord(
            run_id=next_run_id,
            child_session_key=prev.child_session_key,
            requester_session_key=prev.requester_session_key,
            requester_agent_id=prev.requester_agent_id,
            target_agent_id=prev.target_agent_id,
            task=task,
            label=prev.label,
            model=prev.model,
            cleanup=prev.cleanup,
            spawn_depth=prev.spawn_depth,
            created_at=now,
            started_at=now,
            archive_at_ms=archive_at_ms,
        )
        self._runs[next_run_id] = record
        self._persist_to_disk()
        return record

    def sweep_expired(
        self,
        on_expire: Callable[[SubagentRunRecord], None] | None = None,
    ) -> int:
        """删除 archive_at_ms 已到期的 run，并归档会话。

        每 60 秒由 subagent_archive 调用。on_expire 负责归档/删除会话文件。
        """
        now_ms = time.time() * 1000
        to_remove: list[tuple[str, SubagentRunRecord]] = []
        for rid, r in self._runs.items():
            if r.archive_at_ms is None or r.archive_at_ms > now_ms:
                continue
            to_remove.append((rid, r))

        for rid, r in to_remove:
            if on_expire:
                try:
                    on_expire(r)
                except Exception:
                    pass
            del self._runs[rid]
        if to_remove:
            self._persist_to_disk()
        return len(to_remove)


registry = SubagentRegistry()
