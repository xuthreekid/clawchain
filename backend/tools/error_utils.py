"""工具错误格式 — 返回模型可见的结构化错误字符串（JSON）

模型收到结构化错误后可更好地重试或向用户解释。
"""

from __future__ import annotations

import json


def format_tool_error(tool_name: str, error: str | Exception) -> str:
    """返回模型可见的结构化错误字符串（JSON）"""
    msg = str(error) if isinstance(error, Exception) else error
    return json.dumps(
        {"status": "error", "tool": tool_name, "error": msg[:500]},
        ensure_ascii=False,
    )
