"""子 Agent 会话自动归档"""

from __future__ import annotations

import logging
import threading
import time

from config import resolve_agent_sessions_dir

logger = logging.getLogger(__name__)

_stop_event = threading.Event()
_thread: threading.Thread | None = None
_CHECK_INTERVAL_SEC = 60  # sweeper 间隔


def _archive_subagent_session(agent_id: str, session_id: str) -> bool:
    """将子 Agent 会话归档到 archive/*.deleted.{ts}.json"""
    sessions_dir = resolve_agent_sessions_dir(agent_id)
    path = sessions_dir / f"{session_id}.json"
    if not path.exists():
        return False
    archive_dir = sessions_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    dest = archive_dir / f"{session_id}.deleted.{ts}.json"
    try:
        path.rename(dest)
        logger.info(f"Archived subagent session: {agent_id}/{session_id} -> {dest.name}")
        return True
    except OSError as e:
        logger.warning(f"Failed to archive {session_id}: {e}")
        return False


def _run_archive_sweep() -> int:
    """按 archive_at_ms 清理 registry 并归档会话"""
    from graph.subagent_registry import registry, SubagentRunRecord

    def on_expire(r: SubagentRunRecord) -> None:
        parts = r.child_session_key.split(":")
        if len(parts) < 4:
            return
        agent_id = parts[1]
        session_id = parts[-1]
        if not session_id.startswith("subagent-"):
            return
        _archive_subagent_session(agent_id, session_id)

    return registry.sweep_expired(on_expire=on_expire)


def _archive_loop() -> None:
    while not _stop_event.wait(_CHECK_INTERVAL_SEC):
        try:
            n = _run_archive_sweep()
            if n > 0:
                logger.info(f"Subagent archive sweep: archived {n} sessions")
        except Exception as e:
            logger.warning(f"Subagent archive sweep error: {e}")


def start_subagent_archive() -> None:
    """启动子 Agent 归档后台线程"""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_archive_loop, daemon=True)
    _thread.start()
    logger.info("Subagent archive sweeper started")


def stop_subagent_archive() -> None:
    """停止子 Agent 归档后台线程"""
    global _thread
    _stop_event.set()
    if _thread:
        _thread.join(timeout=5)
        _thread = None
    logger.info("Subagent archive sweeper stopped")
