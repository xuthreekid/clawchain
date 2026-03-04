"""会话修剪

在发送给模型前截断旧的大型工具结果，减少上下文膨胀。
不同于压缩：修剪是无损的消息预处理，原始数据保留在会话文件中。
"""

from __future__ import annotations

from typing import Any

TOOL_OUTPUT_MAX_CHARS = 3000

TOOL_OUTPUT_RECENT_PRESERVE = 4

TOOL_OUTPUT_SUMMARY_CHARS = 500

LARGE_SYSTEM_MSG_MAX = 2000


def prune_messages(
    messages: list[dict[str, Any]],
    recent_preserve: int = TOOL_OUTPUT_RECENT_PRESERVE,
    tool_max_chars: int = TOOL_OUTPUT_MAX_CHARS,
) -> list[dict[str, Any]]:
    """
    修剪消息列表中的旧大型工具输出。
    最近 recent_preserve 条消息不修剪。
    返回新列表（不修改原列表）。
    """
    if len(messages) <= recent_preserve:
        return messages

    pruned = []
    cutoff = len(messages) - recent_preserve

    for i, msg in enumerate(messages):
        if i >= cutoff:
            pruned.append(msg)
            continue

        pruned_msg = _prune_single_message(msg, tool_max_chars)
        pruned.append(pruned_msg)

    return pruned


def _prune_single_message(msg: dict[str, Any], max_chars: int) -> dict[str, Any]:
    """修剪单条消息中的大型工具输出"""
    tool_calls = msg.get("tool_calls")
    if not tool_calls:
        content = msg.get("content", "")
        if msg.get("role") == "system" and len(content) > LARGE_SYSTEM_MSG_MAX:
            return {
                **msg,
                "content": content[:LARGE_SYSTEM_MSG_MAX] + "\n...[已修剪]",
            }
        return msg

    pruned_tools = []
    for tc in tool_calls:
        output = tc.get("output", "")
        if len(output) > max_chars:
            pruned_output = (
                output[:TOOL_OUTPUT_SUMMARY_CHARS]
                + f"\n\n...[工具输出已修剪: 原始 {len(output)} 字符 → {TOOL_OUTPUT_SUMMARY_CHARS} 字符]"
            )
            pruned_tools.append({**tc, "output": pruned_output})
        else:
            pruned_tools.append(tc)

    return {**msg, "tool_calls": pruned_tools}


def estimate_pruning_savings(
    messages: list[dict[str, Any]],
    recent_preserve: int = TOOL_OUTPUT_RECENT_PRESERVE,
    tool_max_chars: int = TOOL_OUTPUT_MAX_CHARS,
) -> dict[str, int]:
    """估算修剪能节省的字符数"""
    original_chars = 0
    pruned_chars = 0

    for msg in messages:
        content = msg.get("content", "")
        original_chars += len(content)
        for tc in msg.get("tool_calls", []):
            original_chars += len(tc.get("output", ""))

    pruned = prune_messages(messages, recent_preserve, tool_max_chars)
    for msg in pruned:
        content = msg.get("content", "")
        pruned_chars += len(content)
        for tc in msg.get("tool_calls", []):
            pruned_chars += len(tc.get("output", ""))

    return {
        "original_chars": original_chars,
        "pruned_chars": pruned_chars,
        "saved_chars": original_chars - pruned_chars,
    }
