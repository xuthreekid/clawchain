"""会话管理 API — 单主会话模式

每个 Agent 只有一个主会话，通过 /new 重置。
保留向后兼容的 session_id 路径参数，但新 API 自动解析主会话。
"""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import list_agents, resolve_agent_sessions_dir
from graph.session_manager import session_manager
from graph.prompt_builder import prompt_builder

router = APIRouter()


@router.get("/agents/{agent_id}/session")
async def get_main_session(agent_id: str):
    """获取 Agent 的主会话信息"""
    session_id = session_manager.resolve_main_session_id(agent_id)
    data = session_manager.load_session(session_id, agent_id)

    if data is None:
        data = session_manager.ensure_session(session_id, agent_id)

    from graph.token_counter import count_messages_tokens, count_tokens
    messages = data.get("messages", [])
    compressed = data.get("compressed_context", "")

    return {
        "session_id": session_id,
        "agent_id": agent_id,
        "message_count": len(messages),
        "token_count": count_messages_tokens(messages) + (count_tokens(compressed) if compressed else 0),
        "has_compressed": bool(compressed),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
    }


@router.get("/agents/{agent_id}/session/messages")
async def get_main_session_messages(agent_id: str):
    """获取主会话的完整消息"""
    session_id = session_manager.resolve_main_session_id(agent_id)
    data = session_manager.load_session(session_id, agent_id)
    if data is None:
        data = session_manager.ensure_session(session_id, agent_id)

    system_prompt = prompt_builder.build_system_prompt(agent_id)
    return {
        "session_id": session_id,
        "system_prompt": system_prompt,
        "messages": data.get("messages", []),
        "compressed_context": data.get("compressed_context"),
    }


@router.post("/agents/{agent_id}/session/reset")
async def reset_main_session(agent_id: str):
    """重置主会话（/new 命令的 API 等价物）"""
    from graph.agent import agent_manager

    session_id = session_manager.resolve_main_session_id(agent_id)
    data = session_manager.load_session(session_id, agent_id)

    result: dict = {"session_id": session_id, "memory_saved": None, "archived": False}

    if data:
        messages = data.get("messages", [])
        if len(messages) >= 2:
            try:
                mem_result = await agent_manager.save_session_memory(session_id, agent_id)
                result["memory_saved"] = mem_result
            except Exception as e:
                result["memory_saved"] = {"saved": False, "reason": str(e)}

    reset_result = session_manager.reset_session(session_id, agent_id)
    result["archived"] = reset_result.get("archived", False)
    result["archive_file"] = reset_result.get("archive_file")

    return result


# ---------------------------------------------------------------------------
# 向后兼容 — 保留带 session_id 的旧端点
# ---------------------------------------------------------------------------

@router.get("/agents/{agent_id}/sessions")
async def list_sessions(agent_id: str):
    """列出会话（单主会话模式下只返回主会话）"""
    session_id = session_manager.resolve_main_session_id(agent_id)
    data = session_manager.load_session(session_id, agent_id)
    if data is None:
        return []
    title = session_manager.derive_session_title(
        data,
        session_id=session_id,
        updated_at=data.get("updated_at"),
    )
    return [{
        "session_id": session_id,
        "title": title,
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "message_count": len(data.get("messages", [])),
    }]


@router.get("/agents/{agent_id}/sessions/{session_id}/messages")
async def get_messages(agent_id: str, session_id: str):
    """获取指定会话的完整消息（含 System Prompt）"""
    data = session_manager.load_session(session_id, agent_id)
    if data is None:
        raise HTTPException(404, "会话不存在")

    system_prompt = prompt_builder.build_system_prompt(agent_id)
    return {
        "system_prompt": system_prompt,
        "messages": data.get("messages", []),
        "compressed_context": data.get("compressed_context"),
    }


@router.get("/agents/{agent_id}/sessions/{session_id}/history")
async def get_history(agent_id: str, session_id: str):
    """获取对话历史"""
    data = session_manager.load_session(session_id, agent_id)
    if data is None:
        raise HTTPException(404, "会话不存在")
    return {
        "messages": data.get("messages", []),
        "compressed_context": data.get("compressed_context"),
    }


@router.post("/agents/{agent_id}/sessions/{session_id}/reset")
async def reset_session(agent_id: str, session_id: str):
    """重置指定会话（兼容旧端点）"""
    from graph.agent import agent_manager

    data = session_manager.load_session(session_id, agent_id)
    if data is None:
        raise HTTPException(404, "会话不存在")

    result: dict = {"session_id": session_id, "memory_saved": None, "archived": False}

    messages = data.get("messages", [])
    if len(messages) >= 2:
        try:
            mem_result = await agent_manager.save_session_memory(session_id, agent_id)
            result["memory_saved"] = mem_result
        except Exception as e:
            result["memory_saved"] = {"saved": False, "reason": str(e)}

    reset_result = session_manager.reset_session(session_id, agent_id)
    result["archived"] = reset_result.get("archived", False)
    result["archive_file"] = reset_result.get("archive_file")

    return result


@router.post("/agents/{agent_id}/sessions/cleanup")
async def sessions_cleanup(agent_id: str, enforce: bool = False, dry_run: bool = False):
    """sessions cleanup：prune 过期 + cap 超限 + 磁盘预算。enforce=true 时忽略 mode=warn"""
    if not any(a["id"] == agent_id for a in list_agents()):
        raise HTTPException(404, f"Agent '{agent_id}' 不存在")
    store, report = session_manager._run_session_maintenance(
        agent_id, enforce=enforce, dry_run=dry_run
    )
    result: dict = {"pruned": report["pruned"], "capped": report["capped"]}
    if report.get("diskBudget"):
        result["diskBudget"] = report["diskBudget"]
    if dry_run:
        result["dry_run"] = True
        result["would_prune"] = report["pruned"]
        result["would_cap"] = report["capped"]
    return result
