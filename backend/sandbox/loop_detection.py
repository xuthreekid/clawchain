"""工具循环检测"""

from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass, field
from typing import Any

WARNING_THRESHOLD = 10
CRITICAL_THRESHOLD = 20
GLOBAL_CIRCUIT_BREAKER = 30
HISTORY_SIZE = 30


@dataclass
class ToolCall:
    tool_name: str
    args_hash: str
    result_hash: str | None = None


@dataclass
class LoopDetector:
    """每个会话维护一个实例"""
    history: deque[ToolCall] = field(
        default_factory=lambda: deque(maxlen=HISTORY_SIZE)
    )
    total_calls: int = 0

    @staticmethod
    def _hash(obj: Any) -> str:
        raw = str(obj).encode("utf-8")
        return hashlib.md5(raw).hexdigest()[:12]

    def record(self, tool_name: str, args: Any, result: Any = None) -> str | None:
        """
        记录一次工具调用，返回警告消息（如有）。
        """
        args_hash = self._hash(args)
        result_hash = self._hash(result) if result is not None else None

        call = ToolCall(
            tool_name=tool_name,
            args_hash=args_hash,
            result_hash=result_hash,
        )
        self.history.append(call)
        self.total_calls += 1

        if self.total_calls >= GLOBAL_CIRCUIT_BREAKER:
            return (
                f"[安全警告] 工具调用已达 {self.total_calls} 次，触发全局熔断。"
                "请停止当前循环并换一种方法。"
            )

        repeat_count = sum(
            1 for c in self.history
            if c.tool_name == tool_name and c.args_hash == args_hash
        )

        if repeat_count >= CRITICAL_THRESHOLD:
            return (
                f"[严重警告] 工具 '{tool_name}' 使用相同参数已被调用 {repeat_count} 次。"
                "请立即停止重复调用。"
            )
        if repeat_count >= WARNING_THRESHOLD:
            return (
                f"[警告] 工具 '{tool_name}' 使用相同参数已被调用 {repeat_count} 次，"
                "可能陷入循环。请检查你的方法。"
            )

        if len(self.history) >= 4:
            recent = list(self.history)[-4:]
            if (
                recent[0].tool_name == recent[2].tool_name
                and recent[1].tool_name == recent[3].tool_name
                and recent[0].tool_name != recent[1].tool_name
            ):
                return (
                    f"[警告] 检测到乒乓循环: "
                    f"'{recent[0].tool_name}' ↔ '{recent[1].tool_name}'。"
                    "请换一种方法。"
                )

        return None

    def reset(self) -> None:
        self.history.clear()
        self.total_calls = 0
