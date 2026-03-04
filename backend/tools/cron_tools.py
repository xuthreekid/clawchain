"""Cron 工具 — Agent 在对话中管理定时任务与提醒"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from config import get_config, is_cron_enabled
from cron.scheduler import _compute_next_run
from cron.store import load_cron_store, save_cron_store, resolve_cron_store_path
from cron.types import CronJob, CronPayload, CronSchedule


def _store_path() -> Any:
    cfg = get_config()
    cron_cfg = cfg.get("cron") or {}
    override = cron_cfg.get("store")
    return resolve_cron_store_path(override)


class CronToolInput(BaseModel):
    action: Literal["list", "add", "update", "remove", "run", "wake"] = Field(
        ...,
        description="操作类型：list 列出任务，add 创建，update 修改，remove 删除，run 立即执行，wake 立即发送提醒",
    )
    job_id: str | None = Field(default=None, description="任务 ID（update/remove/run 时必填）")
    name: str | None = Field(default=None, description="任务名称（add 时必填）")
    description: str | None = Field(default=None, description="任务描述")
    schedule: dict | None = Field(
        default=None,
        description="调度配置：{kind: at|every|cron, at?: ISO时间, everyMs?: 间隔毫秒, expr?: cron表达式, tz?: 时区}",
    )
    payload: dict | None = Field(
        default=None,
        description="Payload：{text: 提醒内容}",
    )
    text: str | None = Field(default=None, description="wake 时使用的提醒内容")


class CronTool(BaseTool):
    name: str = "cron"
    description: str = (
        "管理定时任务与提醒。action: list 列出任务；add 创建（需 name、schedule、payload）；"
        "update 修改（需 job_id）；remove 删除（需 job_id）；run 立即执行（需 job_id）；"
        "wake 立即发送提醒到主会话（需 text）。"
    )
    args_schema: type[BaseModel] = CronToolInput
    current_agent_id: str = "main"

    def _run(
        self,
        action: str,
        job_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        schedule: dict | None = None,
        payload: dict | None = None,
        text: str | None = None,
    ) -> str:
        if not is_cron_enabled():
            if action == "list":
                return "cron 调度器当前处于禁用状态（config.cron.enabled=false）。可查看任务，但不会自动触发。"
            return "cron 调度器当前处于禁用状态（config.cron.enabled=false）。请先启用后再执行该操作。"

        path = _store_path()
        store = load_cron_store(path)

        if action == "list":
            if not store.jobs:
                return "暂无定时任务。"
            lines = []
            for j in store.jobs:
                s = j.schedule
                sched_str = ""
                if s.kind == "at":
                    sched_str = f"at {s.at}"
                elif s.kind == "every":
                    sched_str = f"every {s.every_ms}ms"
                else:
                    sched_str = f"cron {s.expr or ''}"
                lines.append(
                    f"- {j.id}: {j.name} ({sched_str}) "
                    f"[{'启用' if j.enabled else '禁用'}] {j.payload.text[:50]}..."
                )
            return "\n".join(lines)

        if action == "wake":
            if not (text or "").strip():
                return "wake 需要提供 text 参数。"
            from infra.system_events import enqueue_system_event
            from graph.heartbeat import request_heartbeat_now
            from graph.session_manager import session_manager

            agent_id = self.current_agent_id or "main"
            main_sid = session_manager.resolve_main_session_id(agent_id)
            session_key = session_manager.session_key_from_session_id(agent_id, main_sid)
            enqueue_system_event(
                (text or "").strip(),
                session_key=session_key,
                context_key="cron:wake",
            )
            request_heartbeat_now(agent_id, "wake")
            return f"已发送提醒到主会话，内容：{(text or '').strip()[:100]}..."

        if action == "add":
            if not (name or "").strip():
                return "add 需要提供 name 参数。"
            s = schedule or {}
            if not s.get("kind"):
                return "add 需要提供 schedule，含 kind (at|every|cron)。"
            p = payload or {}
            payload_text = str(p.get("text", "")).strip()
            if not payload_text:
                return "add 需要提供 payload.text（提醒内容）。"

            now_ms = int(time.time() * 1000)
            job_id_new = f"cron-{uuid.uuid4().hex[:12]}"
            schedule_obj = CronSchedule(
                kind=s.get("kind", "cron"),
                at=s.get("at"),
                every_ms=s.get("everyMs"),
                expr=s.get("expr", "0 8 * * *"),
                tz=s.get("tz"),
            )
            payload_obj = CronPayload(kind="systemEvent", text=payload_text)
            job = CronJob(
                id=job_id_new,
                name=(name or "").strip(),
                description=(description or "").strip(),
                agent_id=self.current_agent_id or "main",
                enabled=True,
                delete_after_run=schedule_obj.kind == "at",
                schedule=schedule_obj,
                payload=payload_obj,
                created_at_ms=now_ms,
                updated_at_ms=now_ms,
            )
            job.next_run_at_ms = _compute_next_run(job, now_ms, None)
            store.jobs.append(job)
            save_cron_store(store, path)
            return f"已创建任务 {job_id_new}：{job.name}"

        if action in ("update", "remove", "run"):
            if not (job_id or "").strip():
                return f"{action} 需要提供 job_id 参数。"
            target = None
            for j in store.jobs:
                if j.id == (job_id or "").strip():
                    target = j
                    break
            if not target:
                return f"未找到任务 {job_id}。"

            if action == "remove":
                store.jobs = [j for j in store.jobs if j.id != target.id]
                save_cron_store(store, path)
                return f"已删除任务 {target.id}。"

            if action == "run":
                from infra.system_events import enqueue_system_event
                from graph.heartbeat import request_heartbeat_now
                from graph.session_manager import session_manager

                agent_id = target.agent_id or "main"
                main_sid = session_manager.resolve_main_session_id(agent_id)
                session_key = session_manager.session_key_from_session_id(agent_id, main_sid)
                enqueue_system_event(
                    target.payload.text,
                    session_key=session_key,
                    context_key=f"cron:{target.id}",
                )
                request_heartbeat_now(agent_id, f"cron:{target.id}")
                return f"已触发任务 {target.id}：{target.payload.text[:50]}..."

            if action == "update":
                if isinstance(schedule, dict) and schedule:
                    s = schedule
                    target.schedule = CronSchedule(
                        kind=s.get("kind", target.schedule.kind),
                        at=s.get("at", target.schedule.at),
                        every_ms=s.get("everyMs", target.schedule.every_ms),
                        expr=s.get("expr", target.schedule.expr),
                        tz=s.get("tz", target.schedule.tz),
                    )
                if isinstance(payload, dict) and payload.get("text") is not None:
                    target.payload = CronPayload(kind="systemEvent", text=str(payload.get("text", "")).strip())
                if name is not None:
                    target.name = str(name).strip()
                if description is not None:
                    target.description = str(description).strip()
                target.updated_at_ms = int(time.time() * 1000)
                target.next_run_at_ms = _compute_next_run(
                    target, target.updated_at_ms, target.last_run_at_ms
                )
                save_cron_store(store, path)
                return f"已更新任务 {target.id}。"

        return f"未知操作：{action}"


def get_cron_tools(agent_id: str = "main") -> list[BaseTool]:
    """返回 cron 工具实例"""
    tool = CronTool(current_agent_id=agent_id)
    return [tool]
