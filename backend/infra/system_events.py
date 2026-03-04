"""System Events 队列 — 供 Cron 入队、Heartbeat 读取"""

from __future__ import annotations

import time
from collections import deque
from typing import Any

MAX_EVENTS = 20


class _SessionQueue:
    def __init__(self) -> None:
        self.queue: deque[dict[str, Any]] = deque(maxlen=MAX_EVENTS)
        self.last_text: str | None = None
        self.last_context_key: str | None = None


_queues: dict[str, _SessionQueue] = {}


def _normalize_context_key(key: str | None) -> str | None:
    if not key or not str(key).strip():
        return None
    return str(key).strip().lower()


def enqueue_system_event(
    text: str,
    session_key: str,
    context_key: str | None = None,
) -> None:
    """入队系统事件，供下次心跳读取。"""
    key = (session_key or "").strip()
    if not key:
        return
    if key not in _queues:
        _queues[key] = _SessionQueue()
    q = _queues[key]
    cleaned = (text or "").strip()
    if not cleaned:
        return
    ctx = _normalize_context_key(context_key)
    q.last_context_key = ctx
    if q.last_text == cleaned:
        return
    q.last_text = cleaned
    q.queue.append({"text": cleaned, "ts": int(time.time() * 1000), "contextKey": ctx})


def peek_system_event_entries(session_key: str) -> list[dict[str, Any]]:
    """读取 pending 事件（不消费）。"""
    key = (session_key or "").strip()
    if not key or key not in _queues:
        return []
    return [dict(e) for e in _queues[key].queue]


def drain_system_event_entries(session_key: str) -> list[dict[str, Any]]:
    """取出并消费 pending 事件。"""
    key = (session_key or "").strip()
    if not key or key not in _queues:
        return []
    q = _queues[key]
    entries = list(q.queue)
    q.queue.clear()
    q.last_text = None
    q.last_context_key = None
    return entries


def peek_system_event_entries_for_agent(agent_id: str) -> list[dict[str, Any]]:
    """按 agent_id 取主会话的 pending 事件。session_key = agent:{agent_id}:main"""
    from graph.session_manager import session_manager
    main_sid = session_manager.resolve_main_session_id(agent_id)
    session_key = session_manager.session_key_from_session_id(agent_id, main_sid)
    return peek_system_event_entries(session_key)
