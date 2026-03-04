"""Heartbeat 后台任务 — 主会话运行、HEARTBEAT_OK 剥离、事件存储"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from config import DEFAULT_HEARTBEAT_PROMPT, get_heartbeat_config, resolve_agent_workspace, list_agents
from graph.heartbeat_utils import (
    strip_heartbeat_token,
    is_heartbeat_content_effectively_empty,
    is_within_active_hours,
)
from graph.session_manager import session_manager
from graph.audit_log import audit_logger

logger = logging.getLogger(__name__)

MAX_EVENTS_PER_AGENT = 50


@dataclass
class HeartbeatEvent:
    ts: int
    status: str  # ok-empty | ok-token | sent | skipped | failed
    reason: str | None = None
    preview: str | None = None
    duration_ms: int | None = None
    agent_id: str = ""


_events: dict[str, deque[HeartbeatEvent]] = {}


def _get_events(agent_id: str) -> deque[HeartbeatEvent]:
    if agent_id not in _events:
        _events[agent_id] = deque(maxlen=MAX_EVENTS_PER_AGENT)
    return _events[agent_id]


def emit_heartbeat_event(agent_id: str, evt: HeartbeatEvent) -> None:
    _get_events(agent_id).append(evt)
    try:
        from scheduler.task_store import task_store, TaskRecord, TaskKind, TaskStatus
        import uuid
        status_map = {
            "ok-empty": TaskStatus.SUCCESS,
            "ok-token": TaskStatus.SUCCESS,
            "sent": TaskStatus.SUCCESS,
            "skipped": TaskStatus.CANCELLED,
            "failed": TaskStatus.FAILED,
        }
        record = TaskRecord(
            id=str(uuid.uuid4()),
            kind=TaskKind.HEARTBEAT,
            agent_id=agent_id,
            name=f"heartbeat:{evt.status}",
            status=status_map.get(evt.status, TaskStatus.SUCCESS),
            created_at_ms=evt.ts,
            started_at_ms=evt.ts,
            ended_at_ms=evt.ts + (evt.duration_ms or 0),
            duration_ms=evt.duration_ms,
            preview=evt.preview,
            error=evt.reason if evt.status == "failed" else None,
        )
        task_store.insert(record)
    except Exception as e:
        logger.warning("Failed to persist heartbeat event to task_history: %s", e)


def _build_cron_event_prompt(event_texts: list[str]) -> str:
    """用 cron 事件内容构造 prompt"""
    text = "\n".join(t for t in event_texts if t).strip()
    if not text:
        return "A scheduled cron event was triggered, but no event content was found. Reply HEARTBEAT_OK."
    return (
        "A scheduled reminder has been triggered. The reminder content is:\n\n"
        f"{text}\n\n"
        "Please relay this reminder to the user in a helpful and friendly way."
    )


def get_heartbeat_history(agent_id: str, limit: int = 30) -> list[dict[str, Any]]:
    events = list(_get_events(agent_id))
    events = events[-limit:][::-1]
    return [
        {
            "ts": e.ts,
            "status": e.status,
            "reason": e.reason,
            "preview": e.preview,
            "duration_ms": e.duration_ms,
        }
        for e in events
    ]


class HeartbeatRunner:
    """为每个 Agent 管理周期性心跳任务（主会话、per-agent 配置）"""

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False
        self._config_version = 0

    async def start(self, agent_ids: list[str] | None = None) -> None:
        self._running = True
        ids = agent_ids or [a["id"] for a in list_agents()]
        for agent_id in ids:
            self._ensure_task(agent_id)
        logger.info(f"Heartbeat started for agents: {ids}")

    async def stop(self) -> None:
        self._running = False
        for agent_id, task in list(self._tasks.items()):
            task.cancel()
            logger.info(f"Heartbeat stopped for agent: {agent_id}")
        self._tasks.clear()

    def _ensure_task(self, agent_id: str) -> None:
        if agent_id in self._tasks:
            return
        task = asyncio.create_task(self._heartbeat_loop(agent_id))
        self._tasks[agent_id] = task

    async def add_agent(self, agent_id: str) -> None:
        """新增 Agent 时加入心跳任务（供 API 调用）"""
        hb = get_heartbeat_config(agent_id)
        if hb.get("enabled") and hb.get("interval_seconds"):
            self._ensure_task(agent_id)

    def update_config(self) -> None:
        """配置热更新：根据当前 agents.list 与 heartbeat 配置调整任务"""
        self._config_version += 1
        ids = [a["id"] for a in list_agents()]
        for agent_id in ids:
            hb = get_heartbeat_config(agent_id)
            if not hb.get("enabled") or hb.get("interval_seconds") is None:
                task = self._tasks.pop(agent_id, None)
                if task:
                    task.cancel()
            else:
                self._ensure_task(agent_id)
        for agent_id in list(self._tasks.keys()):
            if agent_id not in ids:
                task = self._tasks.pop(agent_id, None)
                if task:
                    task.cancel()

    async def _heartbeat_loop(self, agent_id: str) -> None:
        last_run_at = 0.0
        while self._running:
            hb = get_heartbeat_config(agent_id)
            interval = hb.get("interval_seconds")
            if interval is None or interval <= 0:
                break
            try:
                poll_interval = 5
                waited = 0
                total_wait = max(1, int(interval))
                while waited < total_wait:
                    if not self._running:
                        break
                    step = min(poll_interval, total_wait - waited)
                    await asyncio.sleep(step)
                    waited += step
                    now = time.time()
                    if agent_id in _wake_requested:
                        _wake_requested.discard(agent_id)
                        break
                    if now - last_run_at >= interval:
                        break
                if not self._running:
                    break
                last_run_at = time.time()
                await self._run_heartbeat(agent_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error for {agent_id}: {e}")
                emit_heartbeat_event(
                    agent_id,
                    HeartbeatEvent(
                        ts=int(time.time() * 1000),
                        status="failed",
                        reason=str(e),
                        agent_id=agent_id,
                    ),
                )
                await asyncio.sleep(60)

    async def _run_heartbeat(self, agent_id: str) -> None:
        """在主会话上执行心跳；HEARTBEAT_OK 时 rollback 不持久化"""
        started = time.time()
        hb = get_heartbeat_config(agent_id)
        if not hb.get("enabled"):
            return
        session_id = session_manager.resolve_main_session_id(agent_id)
        workspace = resolve_agent_workspace(agent_id)
        heartbeat_md = workspace / "HEARTBEAT.md"

        # 静默时段
        active = hb.get("activeHours")
        from config import resolve_agent_config
        agent_cfg = resolve_agent_config(agent_id)
        tz = agent_cfg.get("user_timezone", "Asia/Shanghai")
        if not is_within_active_hours(active, tz):
            emit_heartbeat_event(
                agent_id,
                HeartbeatEvent(
                    ts=int(time.time() * 1000),
                    status="skipped",
                    reason="quiet-hours",
                    duration_ms=int((time.time() - started) * 1000),
                    agent_id=agent_id,
                ),
            )
            return

        # 会话忙碌
        from graph.message_queue import message_queue_manager
        if message_queue_manager.is_session_busy(agent_id, session_id):
            emit_heartbeat_event(
                agent_id,
                HeartbeatEvent(
                    ts=int(time.time() * 1000),
                    status="skipped",
                    reason="requests-in-flight",
                    duration_ms=int((time.time() - started) * 1000),
                    agent_id=agent_id,
                ),
            )
            return

        # 检查 pending cron 事件：若有则用 cron prompt 替代默认
        from infra.system_events import peek_system_event_entries_for_agent, drain_system_event_entries
        main_sid = session_manager.resolve_main_session_id(agent_id)
        session_key = session_manager.session_key_from_session_id(agent_id, main_sid)
        pending = peek_system_event_entries_for_agent(agent_id)
        cron_events = [e for e in pending if (e.get("contextKey") or "").startswith("cron:")]
        cron_events_present = False
        if cron_events:
            event_texts = [e.get("text", "").strip() for e in cron_events if e.get("text")]
            event_texts = [t for t in event_texts if t]
            if event_texts:
                full_prompt = _build_cron_event_prompt(event_texts)
                cron_events_present = True
            else:
                full_prompt = None
        else:
            full_prompt = None

        # now_str 用于 audit，cron 分支可能未设置
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        if full_prompt is None:
            # HEARTBEAT.md 空文件跳过
            if heartbeat_md.exists():
                try:
                    content = heartbeat_md.read_text(encoding="utf-8")
                    if is_heartbeat_content_effectively_empty(content):
                        emit_heartbeat_event(
                            agent_id,
                            HeartbeatEvent(
                                ts=int(time.time() * 1000),
                                status="skipped",
                                reason="empty-heartbeat-file",
                                duration_ms=int((time.time() - started) * 1000),
                                agent_id=agent_id,
                            ),
                        )
                        return
                except Exception:
                    pass

            prompt = hb.get("prompt") or DEFAULT_HEARTBEAT_PROMPT
            full_prompt = f"[心跳轮询] 当前时间: {now_str}。\n{prompt}"

        audit_logger.log(agent_id, "heartbeat_trigger", {"time": now_str})

        try:
            from graph.agent import agent_manager

            response_parts: list[str] = []
            async for event in agent_manager.astream(
                message=full_prompt,
                session_id=session_id,
                agent_id=agent_id,
                prompt_mode="minimal",
            ):
                if event.get("type") == "token":
                    response_parts.append(event.get("content", ""))

            response = "".join(response_parts).strip()
            ack_max = hb.get("ackMaxChars", 300)
            should_skip, stripped = strip_heartbeat_token(response, max_ack_chars=ack_max)

            if should_skip:
                if cron_events_present:
                    # 仅在真正发出提醒后才消费 cron 事件，避免模型失败导致事件丢失。
                    emit_heartbeat_event(
                        agent_id,
                        HeartbeatEvent(
                            ts=int(time.time() * 1000),
                            status="failed",
                            reason="cron-events-not-delivered",
                            duration_ms=int((time.time() - started) * 1000),
                            agent_id=agent_id,
                        ),
                    )
                    audit_logger.log(
                        agent_id,
                        "heartbeat_error",
                        {"error": "cron-events-not-delivered"},
                    )
                    return
                session_manager.rollback_last_turn(session_id, agent_id)
                status = "ok-empty" if not response.strip() else "ok-token"
                emit_heartbeat_event(
                    agent_id,
                    HeartbeatEvent(
                        ts=int(time.time() * 1000),
                        status=status,
                        duration_ms=int((time.time() - started) * 1000),
                        agent_id=agent_id,
                    ),
                )
                audit_logger.log(agent_id, "heartbeat_ok", {})
            else:
                target = hb.get("target", "webchat")
                if cron_events_present:
                    drain_system_event_entries(session_key)
                if target == "webchat":
                    emit_heartbeat_event(
                        agent_id,
                        HeartbeatEvent(
                            ts=int(time.time() * 1000),
                            status="sent",
                            preview=stripped[:200] if stripped else None,
                            duration_ms=int((time.time() - started) * 1000),
                            agent_id=agent_id,
                        ),
                    )
                    from graph.agent import event_bus
                    event_bus.emit(
                        agent_id,
                        {
                            "type": "heartbeat_message",
                            "session_id": session_id,
                            "agent_id": agent_id,
                        },
                    )
                audit_logger.log(agent_id, "heartbeat_response", {"response": response[:500]})
        except Exception as e:
            logger.error(f"Heartbeat execution failed for {agent_id}: {e}")
            emit_heartbeat_event(
                agent_id,
                HeartbeatEvent(
                    ts=int(time.time() * 1000),
                    status="failed",
                    reason=str(e),
                    duration_ms=int((time.time() - started) * 1000),
                    agent_id=agent_id,
                ),
            )
            audit_logger.log(agent_id, "heartbeat_error", {"error": str(e)})

    @property
    def active_agents(self) -> list[str]:
        return list(self._tasks.keys())


heartbeat_runner = HeartbeatRunner()

# 供 Cron 调用的「立即唤醒」接口
_wake_requested: set[str] = set()


def request_heartbeat_now(agent_id: str, reason: str | None = None) -> None:
    """立即唤醒指定 Agent 的心跳（供 Cron 等调用）。"""
    _wake_requested.add(agent_id)
