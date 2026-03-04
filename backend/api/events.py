"""SSE 事件流 — 用于前端实时接收 Agent 生命周期事件"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()


class SubagentKillRequest(BaseModel):
    target: str  # run_id or "all"
    session_id: str | None = None


class SubagentSteerRequest(BaseModel):
    run_id: str
    message: str


@router.get("/agents/{agent_id}/events")
async def agent_events(agent_id: str):
    """SSE 端点：订阅 Agent 的生命周期事件"""
    from graph.agent import event_bus

    queue = event_bus.subscribe(agent_id)

    async def event_stream():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    data = json.dumps(event, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(agent_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/agents/{agent_id}/usage")
async def agent_usage(agent_id: str, session_id: str | None = None):
    """获取 Agent 的 token 使用统计"""
    from graph.run_tracker import run_tracker
    from config import resolve_agent_config

    usage = run_tracker.get_cumulative_usage(agent_id, session_id)
    model = resolve_agent_config(agent_id).get("model", "deepseek-chat")

    return {
        **usage,
        "model": model,
    }


@router.get("/agents/{agent_id}/audit-log")
async def agent_audit_log(agent_id: str, limit: int = 50):
    """获取最近的审计日志"""
    from graph.audit_log import audit_logger
    return audit_logger.read_recent(agent_id, limit)


def _run_to_item(r, session_manager, time_module) -> dict:
    """将 SubagentRunRecord 转为 API 项"""
    elapsed = None
    duration_ms = None
    if r.started_at:
        end = r.ended_at or time_module.time()
        elapsed = int(end - r.started_at)
        duration_ms = max(0, int((end - r.started_at) * 1000))
    status = "running" if r.ended_at is None else (r.outcome or "completed")
    state = getattr(r, "state", "running" if r.ended_at is None else "succeeded")
    child_parts = r.child_session_key.split(":")
    child_session = child_parts[-1] if len(child_parts) >= 2 else r.child_session_key
    child_agent = child_parts[1] if len(child_parts) >= 2 else r.target_agent_id
    messages = []
    data = session_manager.load_session(child_session, child_agent)
    if data:
        for m in data.get("messages", []):
            messages.append({
                "role": m.get("role"),
                "content": (m.get("content", "") or "")[:500],
                "tool_calls": m.get("tool_calls"),
            })
    return {
        "run_id": r.run_id,
        "label": r.label or "子Agent",
        "task": r.task,
        "target_agent_id": r.target_agent_id,
        "status": status,
        "state": state,
        "terminal_reason": getattr(r, "terminal_reason", None),
        "elapsed": elapsed,
        "duration_ms": duration_ms,
        "started_at": r.started_at,
        "ended_at": r.ended_at,
        "result_summary": (r.result_summary or "")[:300],
        "messages": messages,
        "created_at": r.created_at,
        "spawn_depth": r.spawn_depth,
        "requester_session_key": r.requester_session_key,
        "child_session_key": r.child_session_key,
        "announce_state": getattr(r, "announce_state", "pending"),
        "announce_retry_count": getattr(r, "announce_retry_count", 0),
        "archive_at_ms": getattr(r, "archive_at_ms", None),
    }


def _build_subagent_tree(
    registry,
    session_manager,
    agent_id: str,
    root_session_key: str,
    session_id_filter: str | None,
    time_module,
    cutoff: float | None = None,
) -> list[dict]:
    """递归构建子 Agent 树。cutoff 为 None 时不过滤；否则只包含 ended_at is None 或 ended_at >= cutoff 的 run"""
    children_sk = registry.session_key_from_child_session_key
    tree: list[dict] = []
    for r in registry._runs.values():
        if r.requester_session_key != root_session_key:
            continue
        if session_id_filter and session_id_filter not in r.requester_session_key:
            continue
        if cutoff is not None and r.ended_at is not None and r.ended_at < cutoff:
            continue
        item = _run_to_item(r, session_manager, time_module)
        child_sk = children_sk(r.child_session_key)
        item["descendants_active_count"] = registry.count_active_descendant_runs(child_sk)
        item["children"] = _build_subagent_tree(
            registry,
            session_manager,
            agent_id,
            child_sk,
            session_id_filter,
            time_module,
            cutoff=cutoff,
        )
        tree.append(item)
    tree.sort(key=lambda x: x["created_at"], reverse=True)
    return tree


@router.get("/agents/{agent_id}/subagents")
async def list_subagents(
    agent_id: str,
    session_id: str | None = None,
    include_recent_minutes: int | None = None,
):
    """获取子 Agent 列表及状态，返回树结构 + 扁平列表（按 requester_session_key 建树）

    include_recent_minutes: 只展示运行中 + 最近 N 分钟内完成的子 Agent，超过的不出现在 list 中。
    默认从 config.agents.defaults.subagents.recent_minutes 读取（30），API 参数可覆盖。
    """
    import time as time_module
    from config import get_config
    from graph.subagent_registry import registry
    from graph.session_manager import session_manager

    cfg = get_config()
    default_recent = (
        cfg.get("agents", {}).get("defaults", {}).get("subagents", {}).get("recent_minutes")
    )
    if default_recent is not None and isinstance(default_recent, (int, float)):
        default_recent = max(1, min(24 * 60, int(default_recent)))
    else:
        default_recent = 30
    minutes = (
        include_recent_minutes
        if include_recent_minutes is not None and include_recent_minutes > 0
        else default_recent
    )
    minutes = max(1, min(24 * 60, minutes))  # 限制 1 ~ 1440
    cutoff = time_module.time() - minutes * 60

    main_sid = session_manager.resolve_main_session_id(agent_id)
    if not session_id or not (session_id or "").strip():
        root_session_key = session_manager.session_key_from_session_id(agent_id, main_sid)
    else:
        root_session_key = session_manager.session_key_from_session_id(
            agent_id, session_id.strip()
        )
    tree = _build_subagent_tree(
        registry,
        session_manager,
        agent_id,
        root_session_key,
        None,
        time_module,
        cutoff=cutoff,
    )

    flat: list[dict] = []

    def flatten(nodes: list[dict]) -> None:
        for n in nodes:
            flat.append({k: v for k, v in n.items() if k != "children"})
            if n.get("children"):
                flatten(n["children"])

    flatten(tree)
    flat.sort(key=lambda x: x["created_at"], reverse=True)

    return {"tree": tree, "flat": flat, "include_recent_minutes": minutes}


@router.post("/agents/{agent_id}/subagents/kill")
async def kill_subagents(agent_id: str, req: SubagentKillRequest):
    from graph.subagent_registry import registry
    from graph.session_manager import session_manager

    session_id = (req.session_id or "").strip() or session_manager.resolve_main_session_id(agent_id)
    root_session_key = session_manager.session_key_from_session_id(agent_id, session_id)
    target = (req.target or "").strip()
    if not target:
        return {"ok": False, "error": "missing target"}

    descendants = registry.list_descendant_runs(root_session_key, include_recent_minutes=24 * 60)
    allowed_run_ids = {r.run_id for r in descendants}

    if target in ("all", "*"):
        killed = 0
        for run in descendants:
            if run.ended_at is None and registry.kill(run.run_id):
                killed += 1
        return {"ok": True, "killed": killed, "scope": root_session_key}

    if target not in allowed_run_ids:
        return {"ok": False, "error": "run not found in current session scope"}
    entry = registry.get_run(target)
    if not entry:
        return {"ok": False, "error": "run not found"}
    if entry.ended_at is not None:
        return {"ok": False, "error": "run already finished"}
    killed = registry.kill(target)
    if not killed:
        return {"ok": False, "error": "failed to kill run"}
    return {"ok": True, "run_id": target}


@router.post("/agents/{agent_id}/subagents/steer")
async def steer_subagent(agent_id: str, req: SubagentSteerRequest):
    import uuid

    from graph.subagent_registry import registry
    from graph.session_manager import session_manager
    from graph.agent import agent_manager
    from tools.agent_tools import SessionsSpawnTool

    run_id = (req.run_id or "").strip()
    message = (req.message or "").strip()
    if not run_id or not message:
        return {"ok": False, "error": "run_id and message are required"}
    if len(message) > 4000:
        return {"ok": False, "error": "message too long (>4000)"}

    entry = registry.get_run(run_id)
    if not entry:
        return {"ok": False, "error": f"run_id not found: {run_id}"}
    if entry.ended_at is not None:
        return {"ok": False, "error": "run already finished"}

    parsed_requester = session_manager.session_id_from_session_key(entry.requester_session_key)
    if not parsed_requester:
        return {"ok": False, "error": "invalid requester session key"}
    requester_agent_id, requester_session_id = parsed_requester
    if requester_agent_id != agent_id:
        return {"ok": False, "error": "run does not belong to current agent scope"}

    parsed_child = session_manager.session_id_from_session_key(entry.child_session_key)
    if not parsed_child:
        return {"ok": False, "error": "invalid child session key"}
    target_agent_id, target_session_id = parsed_child

    session_manager.save_message(target_session_id, target_agent_id, "user", message)
    registry.kill(run_id)
    new_run_id = uuid.uuid4().hex[:12]
    next_record = registry.replace_run_after_steer(
        previous_run_id=run_id,
        next_run_id=new_run_id,
        task=message,
        fallback=entry,
    )
    if not next_record:
        return {"ok": False, "error": "failed to replace run after steer"}

    spawn_tool = SessionsSpawnTool(
        current_agent_id=requester_agent_id,
        current_session_id=requester_session_id,
    )
    spawn_tool._agent_manager = agent_manager
    spawn_tool._main_loop = getattr(agent_manager, "_main_loop", None)

    if not spawn_tool._main_loop:
        return {"ok": False, "error": "agent event loop is unavailable"}

    coro = spawn_tool._run_subagent(
        new_run_id,
        target_session_id,
        target_agent_id,
        message,
        entry.requester_session_key,
    )
    future = asyncio.run_coroutine_threadsafe(coro, spawn_tool._main_loop)
    registry.set_task(new_run_id, future)
    return {"ok": True, "run_id": new_run_id, "replaced_run_id": run_id}


@router.get("/agents/{agent_id}/status")
async def agent_status(agent_id: str):
    """获取 Agent 运行状态"""
    from graph.agent import agent_manager
    from graph.heartbeat import heartbeat_runner

    state = agent_manager.get_state(agent_id)
    return {
        "agent_id": agent_id,
        "total_turns": state.total_turns,
        "total_input_tokens": state.total_input_tokens,
        "total_output_tokens": state.total_output_tokens,
        "compaction_count": state.compaction_count,
        "thinking": state.thinking,
        "verbose": state.verbose,
        "reasoning": state.reasoning,
        "last_active": state.last_active,
        "heartbeat_active": agent_id in heartbeat_runner.active_agents,
    }
