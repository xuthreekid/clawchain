"""Cron 类型定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class CronSchedule:
    """调度类型：at（绝对时间）、every（间隔）、cron（cron 表达式）"""
    kind: Literal["at", "every", "cron"]
    at: str | None = None  # ISO 时间，kind=at 时使用
    every_ms: int | None = None  # 间隔毫秒，kind=every 时使用
    expr: str | None = None  # cron 表达式如 "0 8 * * *"，kind=cron 时使用
    tz: str | None = None  # 时区，kind=cron 时使用


@dataclass
class CronPayload:
    """Payload：systemEvent 用于主会话提醒"""
    kind: Literal["systemEvent"]
    text: str


@dataclass
class CronJob:
    """Cron 任务"""
    id: str
    name: str
    description: str = ""
    agent_id: str = "main"
    session_key: str | None = None  # 主会话 session_key，如 agent:main:main
    enabled: bool = True
    delete_after_run: bool = False  # 一次性任务执行后自动删除
    schedule: CronSchedule = field(default_factory=lambda: CronSchedule(kind="cron", expr="0 8 * * *"))
    payload: CronPayload = field(default_factory=lambda: CronPayload(kind="systemEvent", text=""))
    created_at_ms: int = 0
    updated_at_ms: int = 0
    next_run_at_ms: int | None = None
    last_run_at_ms: int | None = None
    last_run_status: str | None = None  # ok | error | skipped

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agentId": self.agent_id,
            "sessionKey": self.session_key,
            "enabled": self.enabled,
            "deleteAfterRun": self.delete_after_run,
            "schedule": {
                "kind": self.schedule.kind,
                "at": self.schedule.at,
                "everyMs": self.schedule.every_ms,
                "expr": self.schedule.expr,
                "tz": self.schedule.tz,
            },
            "payload": {"kind": self.payload.kind, "text": self.payload.text},
            "createdAtMs": self.created_at_ms,
            "updatedAtMs": self.updated_at_ms,
            "nextRunAtMs": self.next_run_at_ms,
            "lastRunAtMs": self.last_run_at_ms,
            "lastRunStatus": self.last_run_status,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CronJob:
        s = d.get("schedule") or {}
        if isinstance(s, dict):
            schedule = CronSchedule(
                kind=s.get("kind", "cron"),
                at=s.get("at"),
                every_ms=s.get("everyMs"),
                expr=s.get("expr", "0 8 * * *"),
                tz=s.get("tz"),
            )
        else:
            schedule = CronSchedule(kind="cron", expr="0 8 * * *")
        p = d.get("payload") or {}
        if isinstance(p, dict):
            payload = CronPayload(kind="systemEvent", text=str(p.get("text", "")).strip())
        else:
            payload = CronPayload(kind="systemEvent", text="")
        return cls(
            id=str(d.get("id", "")),
            name=str(d.get("name", "未命名")),
            description=str(d.get("description", "")),
            agent_id=str(d.get("agentId", "main")),
            session_key=d.get("sessionKey"),
            enabled=bool(d.get("enabled", True)),
            delete_after_run=bool(d.get("deleteAfterRun", False)),
            schedule=schedule,
            payload=payload,
            created_at_ms=int(d.get("createdAtMs", 0)),
            updated_at_ms=int(d.get("updatedAtMs", 0)),
            next_run_at_ms=d.get("nextRunAtMs"),
            last_run_at_ms=d.get("lastRunAtMs"),
            last_run_status=d.get("lastRunStatus"),
        )


@dataclass
class CronStore:
    """Cron store 文件结构"""
    version: int = 1
    jobs: list[CronJob] = field(default_factory=list)
