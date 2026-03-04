"""SQLite 任务历史存储 — 持久化心跳、Cron、提醒等任务执行记录"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any


class TaskKind(str, Enum):
    HEARTBEAT = "heartbeat"
    CRON = "cron"
    REMINDER = "reminder"
    SYSTEM = "system"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class TaskRecord:
    id: str
    kind: TaskKind
    agent_id: str
    name: str = ""
    status: TaskStatus = TaskStatus.PENDING
    created_at_ms: int = 0
    started_at_ms: int | None = None
    ended_at_ms: int | None = None
    duration_ms: int | None = None
    retry_count: int = 0
    max_retries: int = 3
    error: str | None = None
    preview: str | None = None
    payload: str | None = None
    source_job_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["status"] = self.status.value
        return d


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS task_history (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    name TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at_ms INTEGER NOT NULL,
    started_at_ms INTEGER,
    ended_at_ms INTEGER,
    duration_ms INTEGER,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    error TEXT,
    preview TEXT,
    payload TEXT,
    source_job_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_task_agent ON task_history(agent_id);
CREATE INDEX IF NOT EXISTS idx_task_kind ON task_history(kind);
CREATE INDEX IF NOT EXISTS idx_task_status ON task_history(status);
CREATE INDEX IF NOT EXISTS idx_task_created ON task_history(created_at_ms);
"""


class TaskStore:
    """SQLite-backed task history store"""

    def __init__(self, db_path: Path | str | None = None):
        if db_path is None:
            from config import DATA_DIR
            db_path = DATA_DIR / "task_history.db"
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.executescript(_CREATE_TABLE_SQL)
                conn.commit()
            finally:
                conn.close()

    def insert(self, record: TaskRecord) -> None:
        if not record.created_at_ms:
            record.created_at_ms = int(time.time() * 1000)
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO task_history
                    (id, kind, agent_id, name, status, created_at_ms,
                     started_at_ms, ended_at_ms, duration_ms, retry_count,
                     max_retries, error, preview, payload, source_job_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.id, record.kind.value, record.agent_id,
                        record.name, record.status.value, record.created_at_ms,
                        record.started_at_ms, record.ended_at_ms, record.duration_ms,
                        record.retry_count, record.max_retries, record.error,
                        record.preview, record.payload, record.source_job_id,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        error: str | None = None,
        preview: str | None = None,
    ) -> None:
        now_ms = int(time.time() * 1000)
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    "SELECT started_at_ms FROM task_history WHERE id = ?", (task_id,)
                ).fetchone()
                duration = None
                if row and row["started_at_ms"]:
                    duration = now_ms - row["started_at_ms"]

                ended = now_ms if status in (TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED) else None
                conn.execute(
                    """UPDATE task_history SET status = ?, ended_at_ms = ?,
                       duration_ms = ?, error = ?,
                       preview = COALESCE(?, preview)
                    WHERE id = ?""",
                    (status.value, ended, duration, error, preview, task_id),
                )
                conn.commit()
            finally:
                conn.close()

    def mark_running(self, task_id: str) -> None:
        now_ms = int(time.time() * 1000)
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "UPDATE task_history SET status = 'running', started_at_ms = ? WHERE id = ?",
                    (now_ms, task_id),
                )
                conn.commit()
            finally:
                conn.close()

    def increment_retry(self, task_id: str) -> int:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "UPDATE task_history SET retry_count = retry_count + 1, status = 'retrying' WHERE id = ?",
                    (task_id,),
                )
                conn.commit()
                row = conn.execute("SELECT retry_count FROM task_history WHERE id = ?", (task_id,)).fetchone()
                return row["retry_count"] if row else 0
            finally:
                conn.close()

    def query(
        self,
        agent_id: str | None = None,
        kind: TaskKind | None = None,
        status: TaskStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if kind:
            conditions.append("kind = ?")
            params.append(kind.value)
        if status:
            conditions.append("status = ?")
            params.append(status.value)

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM task_history WHERE {where} ORDER BY created_at_ms DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(sql, params).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def count(self, agent_id: str | None = None) -> int:
        with self._lock:
            conn = self._get_conn()
            try:
                if agent_id:
                    row = conn.execute("SELECT COUNT(*) as cnt FROM task_history WHERE agent_id = ?", (agent_id,)).fetchone()
                else:
                    row = conn.execute("SELECT COUNT(*) as cnt FROM task_history").fetchone()
                return row["cnt"] if row else 0
            finally:
                conn.close()

    def cleanup(self, max_age_days: int = 30) -> int:
        cutoff = int((time.time() - max_age_days * 86400) * 1000)
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute(
                    "DELETE FROM task_history WHERE created_at_ms < ? AND status IN ('success', 'failed', 'cancelled')",
                    (cutoff,),
                )
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()


task_store = TaskStore()
