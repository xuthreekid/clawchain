"""Approval Store — 危险工具执行前用户确认"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Literal

Decision = Literal["approved", "denied", "timeout"]


@dataclass
class PendingApproval:
    approval_id: str
    agent_id: str
    tool: str
    input_preview: str
    event: asyncio.Event = field(default_factory=asyncio.Event)
    result: Decision | None = None


class ApprovalStore:
    """内存态 approval 存储，支持 create/wait/resolve"""

    def __init__(self) -> None:
        self._pending: dict[str, PendingApproval] = {}
        self._lock = asyncio.Lock()

    def create(self, agent_id: str, tool: str, input_preview: str) -> str:
        """创建待确认请求，返回 approval_id"""
        approval_id = str(uuid.uuid4())
        pending = PendingApproval(
            approval_id=approval_id,
            agent_id=agent_id,
            tool=tool,
            input_preview=input_preview[:500] if input_preview else "",
        )
        self._pending[approval_id] = pending
        return approval_id

    async def wait(
        self, approval_id: str, timeout_seconds: float = 60
    ) -> Decision:
        """等待用户确认，超时视为 denied"""
        pending = self._pending.get(approval_id)
        if not pending:
            return "denied"

        try:
            await asyncio.wait_for(pending.event.wait(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            pending.result = "timeout"
        finally:
            async with self._lock:
                self._pending.pop(approval_id, None)

        return pending.result or "timeout"

    def resolve(self, approval_id: str, decision: Literal["approved", "denied"]) -> bool:
        """用户确认/拒绝，唤醒等待的协程"""
        pending = self._pending.get(approval_id)
        if not pending:
            return False
        pending.result = decision
        pending.event.set()
        return True


approval_store = ApprovalStore()
