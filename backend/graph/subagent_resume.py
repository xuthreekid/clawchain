"""子 Agent 恢复

启动时对从 runs.json 恢复的 run 执行：
1. 孤儿检测：child 会话不存在则 reconcile
2. 已结束：执行 announce 交付
3. 未结束（单进程重启后 task 已丢失）：视为孤儿
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from graph.subagent_registry import registry, SubagentRunRecord

logger = logging.getLogger(__name__)

MAX_ANNOUNCE_RETRY = 3
ANNOUNCE_EXPIRY_SEC = 5 * 60  # 5 分钟


def _resolve_orphan_reason(entry: SubagentRunRecord) -> Literal["missing-session-entry", "missing-session-id", "missing-session-file"] | None:
    """判断子 Agent run 是否变成孤儿"""
    child_key = (entry.child_session_key or "").strip()
    if not child_key:
        return "missing-session-entry"
    try:
        from graph.session_manager import session_manager
        parts = child_key.split(":")
        if len(parts) < 4:
            return "missing-session-entry"
        agent_id = parts[1]
        session_id = parts[3]
        store = session_manager._load_session_store(agent_id)
        session_key = session_manager.session_key_from_session_id(agent_id, session_id)
        if session_key not in store:
            return "missing-session-entry"
        ent = store.get(session_key, {})
        sid = ent.get("sessionId")
        if not sid or not str(sid).strip():
            return "missing-session-id"
        session_file = session_manager._session_path(str(sid).strip(), agent_id)
        if not session_file.exists():
            return "missing-session-file"
        return None
    except Exception:
        return None


def _reconcile_orphaned(run_id: str, entry: SubagentRunRecord, reason: str) -> bool:
    """将孤儿 run 标记为已结束并清理"""
    import time
    entry.ended_at = time.time()
    entry.outcome = f"orphaned ({reason})"
    registry._runs.pop(run_id, None)
    registry._persist_to_disk()
    logger.warning(f"Subagent orphan pruned run={run_id} child={entry.child_session_key} reason={reason}")
    return True


async def _deliver_announce_for_run(run_id: str, entry: SubagentRunRecord) -> bool:
    """向 requester 交付 announce"""
    from graph.session_manager import session_manager
    from graph.agent import event_bus

    parsed = session_manager.session_id_from_session_key(entry.requester_session_key)
    if not parsed:
        return False
    req_agent, req_session = parsed
    main_sid = session_manager.resolve_main_session_id(req_agent)

    task_label = (entry.label or entry.task[:50] or "task").strip()
    result = (entry.result_summary or "(no output)")[:500]
    outcome = entry.outcome or "completed"
    start = entry.started_at or entry.ended_at or 0
    end = entry.ended_at or 0
    runtime_s = int(end - start) if start else 0

    msg_lines = [
        f"[System Message] [sessionId: {run_id}] A subagent task \"{task_label}\" just {outcome}.",
        "",
        "Result:",
        result,
        "",
        f"Stats: runtime {runtime_s}s",
    ]
    announce_msg = "\n".join(msg_lines)

    if req_session == main_sid:
        try:
            from graph.agent import agent_manager
            async for _ in agent_manager.astream(
                message=announce_msg,
                session_id=main_sid,
                agent_id=req_agent,
                prompt_mode="minimal",
                persist_input_role="system",
            ):
                pass
            registry.mark_announce_delivered(run_id)
            event_bus.emit(req_agent, {"type": "subagent_done", "run_id": run_id, "result": result[:300]})
            return True
        except Exception:
            session_manager.save_message(main_sid, req_agent, "system", announce_msg)
            registry.mark_announce_dropped(run_id)
            event_bus.emit(req_agent, {"type": "subagent_done", "run_id": run_id, "result": result[:300]})
            return True

    try:
        from graph.agent import agent_manager
        async for event in agent_manager.astream(
            message=announce_msg,
            session_id=req_session,
            agent_id=req_agent,
            prompt_mode="minimal",
            persist_input_role="system",
        ):
            pass
        registry.mark_announce_delivered(run_id)
        return True
    except Exception as e:
        logger.warning(f"Resume announce failed for run={run_id}: {e}")
        registry.mark_announce_dropped(run_id)
        return False


async def resume_subagent_runs() -> None:
    """启动时调用：对恢复的 run 执行 reconcile + announce"""
    for run_id in list(registry._runs.keys()):
        entry = registry._runs.get(run_id)
        if not entry:
            continue

        reason = _resolve_orphan_reason(entry)
        if reason:
            _reconcile_orphaned(run_id, entry, reason)
            continue

        if entry.announce_retry_count >= MAX_ANNOUNCE_RETRY:
            registry._runs.pop(run_id, None)
            registry._persist_to_disk()
            continue

        if entry.ended_at and (__import__("time").time() - entry.ended_at) > ANNOUNCE_EXPIRY_SEC:
            registry._runs.pop(run_id, None)
            registry._persist_to_disk()
            continue

        if entry.ended_at:
            try:
                delivered = await _deliver_announce_for_run(run_id, entry)
            except Exception as e:
                logger.warning(f"Resume announce error run={run_id}: {e}")
                delivered = False
            if delivered:
                registry._runs.pop(run_id, None)
                registry._persist_to_disk()
            elif not registry.mark_announce_retry(run_id):
                registry.mark_announce_dropped(run_id)
                registry._runs.pop(run_id, None)
                registry._persist_to_disk()
            continue

        entry.ended_at = __import__("time").time()
        entry.outcome = "restart-interrupted"
        try:
            delivered = await _deliver_announce_for_run(run_id, entry)
        except Exception:
            delivered = False
        if delivered:
            registry._runs.pop(run_id, None)
            registry._persist_to_disk()
        elif not registry.mark_announce_retry(run_id):
            registry.mark_announce_dropped(run_id)
            registry._runs.pop(run_id, None)
            registry._persist_to_disk()
