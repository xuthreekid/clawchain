"""Thinking 模式管理

ThinkLevel 分级: off → minimal → low → medium → high → xhigh
- off: 不使用思考
- minimal/low: 轻量思考
- medium: 标准思考
- high/xhigh: 深度思考

运行时通过 /think 命令切换。
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any

THINK_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh"]


class ThinkLevel(IntEnum):
    OFF = 0
    MINIMAL = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    XHIGH = 5


def parse_think_level(value: str | None) -> ThinkLevel:
    if not value:
        return ThinkLevel.OFF
    v = value.strip().lower()
    mapping = {level: ThinkLevel(i) for i, level in enumerate(THINK_LEVELS)}
    if v in mapping:
        return mapping[v]
    if v in ("on", "true", "1", "yes"):
        return ThinkLevel.MEDIUM
    if v in ("false", "0", "no"):
        return ThinkLevel.OFF
    return ThinkLevel.OFF


def think_level_name(level: ThinkLevel) -> str:
    return THINK_LEVELS[level.value]


def think_level_to_budget(level: ThinkLevel) -> int | None:
    """将 ThinkLevel 映射到 thinking budget tokens（用于 Claude extended thinking）"""
    budgets = {
        ThinkLevel.OFF: None,
        ThinkLevel.MINIMAL: 1024,
        ThinkLevel.LOW: 4096,
        ThinkLevel.MEDIUM: 10240,
        ThinkLevel.HIGH: 32768,
        ThinkLevel.XHIGH: 65536,
    }
    return budgets.get(level)


def cycle_think_level(current: ThinkLevel) -> ThinkLevel:
    """循环切换: off → medium → high → off"""
    if current == ThinkLevel.OFF:
        return ThinkLevel.MEDIUM
    if current == ThinkLevel.MEDIUM:
        return ThinkLevel.HIGH
    return ThinkLevel.OFF


def resolve_agent_think_default(agent_id: str) -> ThinkLevel:
    """从 Agent 配置中获取默认 ThinkLevel"""
    try:
        from config import resolve_agent_config
        cfg = resolve_agent_config(agent_id)
        return parse_think_level(cfg.get("thinkingDefault"))
    except Exception:
        return ThinkLevel.OFF
