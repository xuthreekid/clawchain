"""子 Agent Registry 持久化"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from config import DATA_DIR

from graph.subagent_registry import SubagentRunRecord

logger = logging.getLogger(__name__)

REGISTRY_VERSION = 2


def _registry_path() -> Path:
    """subagent registry 持久化路径"""
    return DATA_DIR / "subagents" / "runs.json"


def _record_to_dict(r: SubagentRunRecord) -> dict[str, Any]:
    """可序列化字段，排除 asyncio_task"""
    return {
        "run_id": r.run_id,
        "child_session_key": r.child_session_key,
        "requester_session_key": r.requester_session_key,
        "requester_agent_id": r.requester_agent_id,
        "target_agent_id": r.target_agent_id,
        "task": r.task,
        "label": r.label,
        "model": r.model,
        "cleanup": r.cleanup,
        "spawn_depth": r.spawn_depth,
        "created_at": r.created_at,
        "started_at": r.started_at,
        "ended_at": r.ended_at,
        "outcome": r.outcome,
        "result_summary": r.result_summary,
        "archive_at_ms": r.archive_at_ms,
        "announce_retry_count": getattr(r, "announce_retry_count", 0),
        "last_announce_retry_at": getattr(r, "last_announce_retry_at", None),
        "state": getattr(r, "state", "running"),
        "terminal_reason": getattr(r, "terminal_reason", None),
        "announce_state": getattr(r, "announce_state", "pending"),
    }


def _dict_to_record(d: dict[str, Any]) -> SubagentRunRecord:
    """从 dict 恢复 SubagentRunRecord"""
    r = SubagentRunRecord(
        run_id=d.get("run_id", ""),
        child_session_key=d.get("child_session_key", ""),
        requester_session_key=d.get("requester_session_key", ""),
        requester_agent_id=d.get("requester_agent_id", ""),
        target_agent_id=d.get("target_agent_id", ""),
        task=d.get("task", ""),
        label=d.get("label"),
        model=d.get("model"),
        cleanup=d.get("cleanup", "keep"),
        spawn_depth=d.get("spawn_depth", 0),
        created_at=d.get("created_at", 0.0),
        started_at=d.get("started_at"),
        ended_at=d.get("ended_at"),
        outcome=d.get("outcome"),
        result_summary=d.get("result_summary"),
        archive_at_ms=d.get("archive_at_ms"),
    )
    r.announce_retry_count = d.get("announce_retry_count", 0)
    r.last_announce_retry_at = d.get("last_announce_retry_at")
    r.state = d.get("state", "running")
    r.terminal_reason = d.get("terminal_reason")
    r.announce_state = d.get("announce_state", "pending")
    return r


def save_registry_to_disk(runs: dict[str, SubagentRunRecord]) -> None:
    """持久化 registry 到磁盘"""
    try:
        path = _registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized: dict[str, dict[str, Any]] = {}
        for run_id, r in runs.items():
            serialized[run_id] = _record_to_dict(r)
        data = {"version": REGISTRY_VERSION, "runs": serialized}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to persist subagent registry: {e}")


def load_registry_from_disk() -> dict[str, SubagentRunRecord]:
    """从磁盘加载 registry"""
    path = _registry_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load subagent registry: {e}")
        return {}
    if not isinstance(raw, dict):
        return {}
    runs_raw = raw.get("runs")
    if not isinstance(runs_raw, dict):
        return {}
    out: dict[str, SubagentRunRecord] = {}
    for run_id, entry in runs_raw.items():
        if not isinstance(entry, dict) or not run_id:
            continue
        if not entry.get("run_id"):
            entry["run_id"] = run_id
        try:
            out[run_id] = _dict_to_record(entry)
        except Exception:
            continue
    return out


def restore_registry_from_disk(
    runs: dict[str, SubagentRunRecord],
    merge_only: bool = False,
) -> int:
    """恢复 registry，merge_only 时跳过已存在的 run_id"""
    restored = load_registry_from_disk()
    if not restored:
        return 0
    added = 0
    for run_id, entry in restored.items():
        if not run_id or not entry:
            continue
        if merge_only and run_id in runs:
            continue
        runs[run_id] = entry
        added += 1
    return added
