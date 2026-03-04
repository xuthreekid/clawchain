"""对话压缩 API — 包含 memory flush + compress + post-compaction 完整流程"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/agents/{agent_id}/sessions/{session_id}/compress")
async def compress_session(agent_id: str, session_id: str):
    """
    完整压缩流程：
    1. Memory Flush — 静默回合保存记忆到 memory/YYYY-MM-DD.md
    2. Compress — 压缩旧消息为摘要
    3. Post-Compaction Context — 注入上下文提醒 Agent 重新执行启动序列
    """
    from graph.agent import agent_manager
    from graph.session_manager import session_manager

    data = session_manager.load_session(session_id, agent_id)
    if data is None:
        raise HTTPException(404, "会话不存在")

    messages = data.get("messages", [])
    if len(messages) < 4:
        raise HTTPException(400, "消息数量不足（至少需要 4 条）")

    try:
        result = await agent_manager.compress_with_flush(session_id, agent_id)
    except Exception as e:
        raise HTTPException(500, f"压缩失败: {e}")

    if "error" in result:
        raise HTTPException(400, result["error"])

    return result
