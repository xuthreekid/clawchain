"""Token 计数器 — 用于自动压缩阈值检测"""

from __future__ import annotations

from typing import Any

_encoding = None


def _get_encoding():
    global _encoding
    if _encoding is None:
        try:
            import tiktoken
            _encoding = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            _encoding = "fallback"
    return _encoding


def count_tokens(text: str) -> int:
    enc = _get_encoding()
    if enc == "fallback":
        return len(text) // 3
    return len(enc.encode(text))


def count_messages_tokens(messages: list[dict[str, Any]]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        total += count_tokens(content)
        total += 4  # role overhead
        tool_calls = msg.get("tool_calls", [])
        for tc in tool_calls:
            total += count_tokens(str(tc.get("input", "")))
            total += count_tokens(str(tc.get("output", "")))
    return total


DEFAULT_COMPACTION_THRESHOLD = 80000


def resolve_compaction_threshold(agent_id: str | None = None) -> int:
    """根据 Agent 配置动态计算压缩阈值

    threshold = contextTokens * compaction.threshold
    """
    if not agent_id:
        return DEFAULT_COMPACTION_THRESHOLD
    try:
        from config import resolve_agent_config
        cfg = resolve_agent_config(agent_id)
        context_tokens = cfg.get("contextTokens", 200000)
        compaction = cfg.get("compaction", {})
        ratio = compaction.get("threshold", 0.8)
        return int(context_tokens * ratio)
    except Exception:
        return DEFAULT_COMPACTION_THRESHOLD

def should_compact(
    messages: list[dict[str, Any]],
    compressed_context: str | None = None,
    threshold: int = DEFAULT_COMPACTION_THRESHOLD,
) -> bool:
    total = count_messages_tokens(messages)
    if compressed_context:
        total += count_tokens(compressed_context)
    return total >= threshold


def resolve_memory_flush_soft_threshold(agent_id: str | None = None) -> int:
    """压缩前 Memory Flush 的软阈值

    当 total_tokens >= compaction_threshold - softThresholdTokens 时触发 flush。
    即：在即将压缩前提前提醒，而非等到压缩时才提醒。
    """
    compaction_threshold = resolve_compaction_threshold(agent_id)
    soft = 4000
    if agent_id:
        try:
            from config import resolve_agent_config
            cfg = resolve_agent_config(agent_id)
            soft = cfg.get("compaction", {}).get("softThresholdTokens", 4000)
            if not isinstance(soft, (int, float)) or soft < 0:
                soft = 4000
            soft = int(soft)
        except Exception:
            pass
    return max(0, compaction_threshold - soft)


def should_run_memory_flush(
    session_data: dict[str, Any] | None,
    agent_id: str,
    compaction_count: int,
) -> bool:
    """是否应执行 Memory Flush

    - 当 total_tokens >= soft_threshold 时触发
    - 每个压缩周期只执行一次（memory_flush_compaction_count 去重）
    """
    if not session_data:
        return False
    messages = session_data.get("messages", [])
    compressed = session_data.get("compressed_context")
    total = count_messages_tokens(messages)
    if compressed:
        total += count_tokens(compressed)
    soft_threshold = resolve_memory_flush_soft_threshold(agent_id)
    if total < soft_threshold:
        return False
    last_flush = session_data.get("memory_flush_compaction_count")
    if isinstance(last_flush, (int, float)) and int(last_flush) == int(compaction_count):
        return False
    return True
