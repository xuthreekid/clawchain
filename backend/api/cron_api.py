"""Cron API — CRUD、手动触发、任务历史、自然语言提醒"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config import get_config, list_agents, is_cron_enabled
from cron.store import load_cron_store, save_cron_store, resolve_cron_store_path
from cron.types import CronJob, CronSchedule, CronPayload

router = APIRouter()


def _store_path() -> Path:
    cfg = get_config()
    cron_cfg = cfg.get("cron") or {}
    override = cron_cfg.get("store")
    return resolve_cron_store_path(override)


def _ensure_cron_enabled() -> None:
    if not is_cron_enabled():
        raise HTTPException(
            409,
            "cron is disabled (config.cron.enabled=false); enable it before creating/updating/running reminders.",
        )


class CronJobCreate(BaseModel):
    name: str = Field(..., description="任务名称")
    description: str = Field(default="", description="描述")
    agent_id: str = Field(default="main", description="Agent ID")
    enabled: bool = Field(default=True, description="是否启用")
    delete_after_run: bool = Field(default=False, alias="deleteAfterRun", description="一次性任务执行后自动删除")
    schedule: dict = Field(..., description="调度配置 {kind, at|everyMs|expr, tz?}")
    payload: dict = Field(..., description="Payload {kind: 'systemEvent', text: str}")

    model_config = {"populate_by_name": True}


class CronJobUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    agent_id: str | None = None
    enabled: bool | None = None
    delete_after_run: bool | None = Field(default=None, alias="deleteAfterRun")
    schedule: dict | None = None
    payload: dict | None = None

    model_config = {"populate_by_name": True}


@router.get("/cron/jobs")
async def list_cron_jobs():
    """列出所有 Cron 任务"""
    store = load_cron_store(_store_path())
    return [j.to_dict() for j in store.jobs]


@router.post("/cron/jobs")
async def create_cron_job(body: CronJobCreate):
    """创建 Cron 任务"""
    _ensure_cron_enabled()
    store = load_cron_store(_store_path())
    now_ms = int(time.time() * 1000)
    job_id = f"cron-{uuid.uuid4().hex[:12]}"
    s = body.schedule or {}
    schedule = CronSchedule(
        kind=s.get("kind", "cron"),
        at=s.get("at"),
        every_ms=s.get("everyMs"),
        expr=s.get("expr", "0 8 * * *"),
        tz=s.get("tz"),
    )
    p = body.payload or {}
    if p.get("kind") != "systemEvent":
        raise HTTPException(400, "main session cron jobs require payload.kind='systemEvent'")
    payload = CronPayload(kind="systemEvent", text=str(p.get("text", "")).strip())
    job = CronJob(
        id=job_id,
        name=body.name,
        description=body.description,
        agent_id=body.agent_id,
        enabled=body.enabled,
        delete_after_run=body.delete_after_run,
        schedule=schedule,
        payload=payload,
        created_at_ms=now_ms,
        updated_at_ms=now_ms,
    )
    from cron.scheduler import _compute_next_run
    job.next_run_at_ms = _compute_next_run(job, now_ms, None)
    store.jobs.append(job)
    save_cron_store(store, _store_path())
    return job.to_dict()


@router.get("/cron/jobs/{job_id}")
async def get_cron_job(job_id: str):
    """获取单个 Cron 任务"""
    store = load_cron_store(_store_path())
    for j in store.jobs:
        if j.id == job_id:
            return j.to_dict()
    raise HTTPException(404, f"Job {job_id} not found")


@router.patch("/cron/jobs/{job_id}")
async def update_cron_job(job_id: str, body: CronJobUpdate):
    """更新 Cron 任务"""
    _ensure_cron_enabled()
    store = load_cron_store(_store_path())
    for i, j in enumerate(store.jobs):
        if j.id == job_id:
            if body.name is not None:
                j.name = body.name
            if body.description is not None:
                j.description = body.description
            if body.agent_id is not None:
                j.agent_id = body.agent_id
            if body.enabled is not None:
                j.enabled = body.enabled
            if body.delete_after_run is not None:
                j.delete_after_run = body.delete_after_run
            if body.schedule is not None:
                s = body.schedule
                j.schedule = CronSchedule(
                    kind=s.get("kind", j.schedule.kind),
                    at=s.get("at"),
                    every_ms=s.get("everyMs"),
                    expr=s.get("expr", j.schedule.expr),
                    tz=s.get("tz"),
                )
            if body.payload is not None:
                p = body.payload
                if p.get("kind") == "systemEvent":
                    j.payload = CronPayload(kind="systemEvent", text=str(p.get("text", "")).strip())
            j.updated_at_ms = int(time.time() * 1000)
            from cron.scheduler import _compute_next_run
            now_ms = int(time.time() * 1000)
            j.next_run_at_ms = _compute_next_run(j, now_ms, j.last_run_at_ms)
            save_cron_store(store, _store_path())
            return j.to_dict()
    raise HTTPException(404, f"Job {job_id} not found")


@router.delete("/cron/jobs/{job_id}")
async def delete_cron_job(job_id: str):
    """删除 Cron 任务"""
    _ensure_cron_enabled()
    store = load_cron_store(_store_path())
    for i, j in enumerate(store.jobs):
        if j.id == job_id:
            store.jobs.pop(i)
            save_cron_store(store, _store_path())
            return {"ok": True}
    raise HTTPException(404, f"Job {job_id} not found")


@router.post("/cron/jobs/{job_id}/run")
async def run_cron_job(job_id: str, mode: str = "force"):
    """手动触发 Cron 任务"""
    _ensure_cron_enabled()
    store = load_cron_store(_store_path())
    for j in store.jobs:
        if j.id == job_id:
            from infra.system_events import enqueue_system_event
            from graph.session_manager import session_manager
            from graph.heartbeat import request_heartbeat_now
            agent_id = j.agent_id or "main"
            main_sid = session_manager.resolve_main_session_id(agent_id)
            session_key = session_manager.session_key_from_session_id(agent_id, main_sid)
            enqueue_system_event(
                j.payload.text,
                session_key=session_key,
                context_key=f"cron:{j.id}",
            )
            request_heartbeat_now(agent_id, f"cron:{j.id}")
            return {"ok": True, "message": "Triggered"}
    raise HTTPException(404, f"Job {job_id} not found")


# ---------------------------------------------------------------------------
# 任务历史 API (SQLite)
# ---------------------------------------------------------------------------

@router.get("/tasks/history")
async def get_task_history(
    agent_id: str | None = None,
    kind: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    """查询任务执行历史"""
    from scheduler.task_store import task_store, TaskKind, TaskStatus
    tk = TaskKind(kind) if kind else None
    ts = TaskStatus(status) if status else None
    records = task_store.query(agent_id=agent_id, kind=tk, status=ts, limit=limit, offset=offset)
    total = task_store.count(agent_id=agent_id)
    return {"items": records, "total": total, "limit": limit, "offset": offset}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消任务"""
    from scheduler.lifecycle import task_runner
    ok = task_runner.cancel(task_id)
    return {"ok": ok}


# ---------------------------------------------------------------------------
# 自然语言提醒 (底层映射为一次性 Cron)
# ---------------------------------------------------------------------------

class ReminderCreate(BaseModel):
    text: str = Field(..., description="提醒内容")
    at: str = Field(..., description="提醒时间 (ISO 8601)")
    agent_id: str = Field(default="main")

    model_config = {"populate_by_name": True}


@router.post("/reminders")
async def create_reminder(body: ReminderCreate):
    """创建自然语言提醒 — 底层是一次性 at cron job"""
    _ensure_cron_enabled()
    store = load_cron_store(_store_path())
    now_ms = int(time.time() * 1000)
    job_id = f"reminder-{uuid.uuid4().hex[:12]}"

    schedule = CronSchedule(kind="at", at=body.at)
    payload = CronPayload(kind="systemEvent", text=body.text.strip())
    job = CronJob(
        id=job_id,
        name=f"提醒: {body.text[:40]}",
        description=body.text,
        agent_id=body.agent_id,
        enabled=True,
        delete_after_run=True,
        schedule=schedule,
        payload=payload,
        created_at_ms=now_ms,
        updated_at_ms=now_ms,
    )
    from cron.scheduler import _compute_next_run
    job.next_run_at_ms = _compute_next_run(job, now_ms, None)
    store.jobs.append(job)
    save_cron_store(store, _store_path())
    return {"ok": True, "job": job.to_dict()}
