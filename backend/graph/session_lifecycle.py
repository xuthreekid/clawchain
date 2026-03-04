"""会话生命周期事件总线 — 支持 on_create / on_message / on_compact / on_close / on_memory_flush"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class LifecycleEvent(str, Enum):
    SESSION_CREATE = "session_create"
    SESSION_CLOSE = "session_close"
    MESSAGE_COMPLETE = "message_complete"
    COMPACTION = "compaction"
    MEMORY_FLUSH = "memory_flush"
    SESSION_RESET = "session_reset"
    UNDO = "undo"


@dataclass
class LifecyclePayload:
    event: LifecycleEvent
    agent_id: str
    session_id: str
    timestamp: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)


Handler = Callable[[LifecyclePayload], Any]
AsyncHandler = Callable[[LifecyclePayload], Coroutine[Any, Any, Any]]


class SessionLifecycleBus:
    """全局生命周期事件总线，支持同步和异步 handler"""

    def __init__(self) -> None:
        self._handlers: dict[LifecycleEvent, list[Handler | AsyncHandler]] = defaultdict(list)
        self._global_handlers: list[Handler | AsyncHandler] = []

    def on(self, event: LifecycleEvent, handler: Handler | AsyncHandler) -> None:
        self._handlers[event].append(handler)

    def on_any(self, handler: Handler | AsyncHandler) -> None:
        self._global_handlers.append(handler)

    def off(self, event: LifecycleEvent, handler: Handler | AsyncHandler) -> None:
        handlers = self._handlers.get(event, [])
        if handler in handlers:
            handlers.remove(handler)

    def emit(self, payload: LifecyclePayload) -> None:
        """同步触发（不等待异步 handler）"""
        for h in self._handlers.get(payload.event, []):
            try:
                result = h(payload)
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        pass
            except Exception as e:
                logger.warning(f"Lifecycle handler error ({payload.event}): {e}")
        for h in self._global_handlers:
            try:
                result = h(payload)
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        pass
            except Exception as e:
                logger.warning(f"Global lifecycle handler error ({payload.event}): {e}")

    async def emit_async(self, payload: LifecyclePayload) -> None:
        """异步触发"""
        for h in self._handlers.get(payload.event, []):
            try:
                result = h(payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning(f"Lifecycle handler error ({payload.event}): {e}")
        for h in self._global_handlers:
            try:
                result = h(payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning(f"Global lifecycle handler error ({payload.event}): {e}")


lifecycle_bus = SessionLifecycleBus()
