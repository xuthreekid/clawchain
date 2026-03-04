"""工具调用文本解析 — 支持 Kimi K2 等模型以文本形式输出 functions.TOOL:N{args}

ClawChain 从模型文本输出解析工具调用；部分模型依赖 API 返回结构化 tool_calls。
ClawChain 需兼容将工具调用写在 content 中的模型。
"""

from __future__ import annotations

import json
import re
from typing import Any

# 匹配 functions.TOOL:N 或 functions.TOOL:N<|tool_call_argument_begin|>
# 支持前导文本、多个调用、换行
_FUNC_CALL_PATTERN = re.compile(
    r'functions\.(\w+):\d+'
    r'(?:<\|tool_call_argument_begin\|>)?'  # Kimi 特殊 token
    r'\s*'
    r'(\{)',  # JSON 起始，后续用括号匹配
    re.IGNORECASE,
)


def _extract_json_from_brace(text: str, start: int) -> tuple[dict[str, Any] | None, int]:
    """从 start 位置的 { 开始，提取完整 JSON 对象，返回 (parsed_dict, end_pos)。"""
    if start >= len(text) or text[start] != '{':
        return None, start
    depth = 0
    i = start
    in_string = False
    escape = False
    quote_char = None
    while i < len(text):
        c = text[i]
        if in_string:
            if escape:
                escape = False
            elif c == '\\':
                escape = True
            elif c == quote_char:
                in_string = False
            i += 1
            continue
        if c in ('"', "'"):
            in_string = True
            quote_char = c
            i += 1
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(text[start : i + 1])
                    return parsed if isinstance(parsed, dict) else {}, i + 1
                except json.JSONDecodeError:
                    return None, i + 1
        i += 1
    return None, start


def parse_text_tool_calls(content: str) -> list[tuple[str, dict[str, Any]]]:
    """从模型输出的文本中解析工具调用。

    支持格式：
    - functions.read:3{"path": "SOUL.md"}
    - functions.read:8<|tool_call_argument_begin|>{"path": "SOUL.md"}
    - 前导文本 + 多个调用：好的。functions.read:0{...}functions.read:1{...}
    - 换行分隔

    Returns:
        [(tool_name, args), ...]
    """
    if not content or not isinstance(content, str):
        return []
    results: list[tuple[str, dict[str, Any]]] = []
    for m in _FUNC_CALL_PATTERN.finditer(content):
        tool_name = m.group(1)
        brace_start = m.start(2)
        parsed, _ = _extract_json_from_brace(content, brace_start)
        if parsed is not None:
            results.append((tool_name, parsed))
    return results


def strip_tool_call_patterns(content: str) -> str:
    """移除文本中的工具调用模式，保留自然语言部分。"""
    if not content or not isinstance(content, str):
        return content
    # 找出所有匹配的起止位置
    spans: list[tuple[int, int]] = []
    for m in _FUNC_CALL_PATTERN.finditer(content):
        brace_start = m.start(2)
        _, end_pos = _extract_json_from_brace(content, brace_start)
        if end_pos > brace_start:
            spans.append((m.start(), end_pos))
    if not spans:
        return content.strip()
    # 从后往前替换，避免偏移变化
    result = content
    for start, end in reversed(spans):
        before = result[:start].rstrip()
        after = result[end:].lstrip()
        # 去掉中间可能残留的空白/换行，合并时保留一个空格
        sep = " " if before and after and not before.endswith("\n") else ""
        result = before + sep + after
    return result.strip()
