"""POST /api/chat — SSE 流式对话"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str = ""
    agent_id: str = "main"
    stream: bool = True


class ChatAbortRequest(BaseModel):
    session_id: str = ""
    agent_id: str = "main"
    clear_followups: bool = False


def _should_skip_auto_title(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return True
    return text.startswith("a new session was started via /new or /reset")


async def _event_generator(req: ChatRequest) -> AsyncGenerator[str, None]:
    from graph.agent import agent_manager
    from graph.session_manager import session_manager
    from graph.message_queue import message_queue_manager

    if not req.session_id:
        req.session_id = session_manager.resolve_main_session_id(req.agent_id)

    queue = message_queue_manager.get_queue(req.agent_id, req.session_id)

    from config import get_config
    from graph.command_parser import t
    locale = get_config().get("app", {}).get("locale", "zh-CN")

    if queue.is_busy:
        pos = queue.enqueue_followup(req.message)
        queued_data = json.dumps({
            "type": "queued",
            "position": pos,
            "message": t("chat_queued", locale, pos=str(pos)),
        }, ensure_ascii=False)
        yield f"event: queued\ndata: {queued_data}\n\n"
        done_data = json.dumps({
            "type": "done", "content": t("chat_queued_done", locale),
            "session_id": req.session_id,
        }, ensure_ascii=False)
        yield f"event: done\ndata: {done_data}\n\n"
        return

    await queue.acquire()
    queue.set_active_task(asyncio.current_task())
    try:
        await _run_turn(req, queue)
        async for chunk in _stream_turn(req, queue):
            yield chunk
    finally:
        queue.release()

    # followup 队列自动排空
    while True:
        followup_msg = queue.drain_followup()
        if not followup_msg:
            break
        followup_req = ChatRequest(
            message=followup_msg,
            session_id=req.session_id,
            agent_id=req.agent_id,
            stream=req.stream,
        )
        await queue.acquire()
        queue.set_active_task(asyncio.current_task())
        try:
            async for chunk in _stream_turn(followup_req, queue):
                yield chunk
        finally:
            queue.release()


async def _run_turn(req: ChatRequest, queue: Any) -> None:
    """Placeholder — actual streaming happens in _stream_turn"""
    pass


async def _stream_turn(req: ChatRequest, queue: Any) -> AsyncGenerator[str, None]:
    from graph.agent import agent_manager
    from graph.session_manager import session_manager

    session_data = session_manager.load_session(req.session_id, req.agent_id)
    is_first_message = session_data is None or len(session_data.get("messages", [])) == 0
    partial_text = ""
    run_id = ""

    try:
        async for event in agent_manager.astream(
            message=req.message,
            session_id=req.session_id,
            agent_id=req.agent_id,
        ):
            if event.get("type") == "token":
                partial_text += event.get("content", "") or ""
            elif event.get("type") == "clear_content":
                partial_text = ""
            elif event.get("type") == "content_refresh":
                refreshed = event.get("content")
                if isinstance(refreshed, str):
                    partial_text = refreshed
            elif event.get("type") == "lifecycle" and event.get("event") == "turn_start":
                run_id = str(event.get("run_id") or run_id)
            event_type = event.get("type", "")
            data = json.dumps(event, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {data}\n\n"
    except asyncio.CancelledError:
        # 用户手动停止时，尽量保留本轮输入与已生成的 partial 输出，避免前端重拉后“整轮消失”。
        try:
            queue.clear_followups()
        except Exception:
            pass
        try:
            data = session_manager.load_session(req.session_id, req.agent_id) or {}
            messages = data.get("messages", []) if isinstance(data, dict) else []
            has_user = bool(messages and messages[-1].get("role") == "user" and messages[-1].get("content") == req.message)
            if not has_user:
                session_manager.save_message(req.session_id, req.agent_id, "user", req.message)
            if (partial_text or "").strip():
                session_manager.save_message(
                    req.session_id,
                    req.agent_id,
                    "assistant",
                    partial_text,
                )
        except Exception:
            pass
        aborted_data = json.dumps({
            "type": "aborted",
            "session_id": req.session_id,
            "run_id": run_id,
            "content": partial_text,
            "reason": "stopped_by_user",
        }, ensure_ascii=False)
        yield f"event: aborted\ndata: {aborted_data}\n\n"
        return

    except Exception as e:
        error_data = json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False)
        yield f"event: error\ndata: {error_data}\n\n"
        return

    if is_first_message and not _should_skip_auto_title(req.message):
        title = await _generate_title(req.message, req.agent_id)
        if title:
            session_manager.rename_session(req.session_id, req.agent_id, title)
            title_data = json.dumps(
                {"type": "title", "session_id": req.session_id, "title": title},
                ensure_ascii=False,
            )
            yield f"event: title\ndata: {title_data}\n\n"


async def _generate_title(message: str, agent_id: str) -> str | None:
    """使用 LLM 生成不超过 10 个字的会话标题"""
    from graph.agent import agent_manager

    try:
        llm = agent_manager.get_llm(agent_id)
    except Exception:
        return None

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from config import get_config
        from graph.command_parser import t
        locale = get_config().get("app", {}).get("locale", "zh-CN")

        resp = await llm.ainvoke([
            SystemMessage(content=t("title_gen_system", locale)),
            HumanMessage(content=message),
        ])
        title = resp.content.strip()[:20]
        return title if title else None
    except Exception:
        return None


@router.post("/chat")
async def chat(req: ChatRequest):
    if req.stream:
        return StreamingResponse(
            _event_generator(req),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        from graph.agent import agent_manager

        full_response = ""
        async for event in agent_manager.astream(
            message=req.message,
            session_id=req.session_id,
            agent_id=req.agent_id,
        ):
            if event.get("type") == "token":
                full_response += event.get("content", "")

        return {"content": full_response, "session_id": req.session_id}


@router.post("/chat/abort")
async def abort_chat(req: ChatAbortRequest):
    from graph.session_manager import session_manager
    from graph.message_queue import message_queue_manager

    session_id = req.session_id or session_manager.resolve_main_session_id(req.agent_id)
    queue = message_queue_manager.get_queue(req.agent_id, session_id)
    aborted = queue.abort_active_task()
    cleared = queue.clear_followups() if req.clear_followups else 0
    return {
        "aborted": bool(aborted),
        "pending_followups": queue.pending_count,
        "cleared_followups": cleared,
    }
