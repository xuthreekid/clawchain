"""LCEL 中间件 — 从模型文本输出中解析并注入 tool_calls

当模型（如 Kimi K2）将工具调用以文本形式输出到 content 时，
此中间件解析并注入为结构化 tool_calls，使 LangGraph 能正常执行。
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableLambda

from graph.tool_call_parser import parse_text_tool_calls, strip_tool_call_patterns

logger = logging.getLogger(__name__)


def _inject_tool_calls_from_content(msg: BaseMessage) -> BaseMessage:
    """解析 AIMessage 的 content，若含工具调用文本则注入 tool_calls。"""
    if not isinstance(msg, AIMessage):
        return msg
    content = msg.content
    if not content or not isinstance(content, str):
        return msg
    parsed = parse_text_tool_calls(content)
    if not parsed:
        return msg
    # 已有原生 tool_calls 则不覆盖
    if getattr(msg, "tool_calls", None):
        return msg
    # 构建 ToolCall 列表（LangChain 格式）
    tool_calls = []
    for i, (name, args) in enumerate(parsed):
        tc = {
            "name": name,
            "args": args,
            "id": f"call_{i}",
            "type": "tool_call",
        }
        tool_calls.append(tc)
    cleaned_content = strip_tool_call_patterns(content)
    logger.info(
        "Injected %d tool call(s) from text: %s",
        len(tool_calls),
        [t["name"] for t in tool_calls],
    )
    return AIMessage(
        content=cleaned_content or "",
        tool_calls=tool_calls,
        additional_kwargs=getattr(msg, "additional_kwargs", None) or {},
    )


def create_tool_call_injector():
    """返回 LCEL Runnable，用于 llm | injector 链。"""
    return RunnableLambda(_inject_tool_calls_from_content)
