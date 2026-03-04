"""任务生命周期状态机 — 失败重试策略 + 指数退避"""

from __future__ import annotations

import asyncio
import logging
import math
import time
import uuid
from typing import Any, Callable, Coroutine

from scheduler.task_store import TaskStore, TaskRecord, TaskKind, TaskStatus, task_store

logger = logging.getLogger(__name__)

BASE_RETRY_DELAY_S = 10
MAX_RETRY_DELAY_S = 300


def compute_retry_delay(retry_count: int) -> float:
    """指数退避：10s, 20s, 40s, 80s... 最大 300s"""
    return min(BASE_RETRY_DELAY_S * (2 ** retry_count), MAX_RETRY_DELAY_S)


class TaskRunner:
    """通用任务执行器 — 包裹 Agent 调用，处理状态转换和重试"""

    def __init__(self, store: TaskStore | None = None):
        self._store = store or task_store

    def create_task(
        self,
        kind: TaskKind,
        agent_id: str,
        name: str = "",
        payload: str | None = None,
        source_job_id: str | None = None,
        max_retries: int = 3,
    ) -> TaskRecord:
        record = TaskRecord(
            id=str(uuid.uuid4()),
            kind=kind,
            agent_id=agent_id,
            name=name,
            status=TaskStatus.PENDING,
            created_at_ms=int(time.time() * 1000),
            max_retries=max_retries,
            payload=payload,
            source_job_id=source_job_id,
        )
        self._store.insert(record)
        return record

    async def execute(
        self,
        record: TaskRecord,
        run_fn: Callable[..., Coroutine[Any, Any, str | None]],
    ) -> TaskRecord:
        """执行任务，返回更新后的 record"""
        self._store.mark_running(record.id)
        record.status = TaskStatus.RUNNING
        record.started_at_ms = int(time.time() * 1000)

        try:
            result = await run_fn()
            self._store.update_status(record.id, TaskStatus.SUCCESS, preview=result)
            record.status = TaskStatus.SUCCESS
            record.preview = result
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Task {record.id} ({record.kind}) failed: {error_msg}")

            if record.retry_count < record.max_retries:
                retry_count = self._store.increment_retry(record.id)
                record.retry_count = retry_count
                record.status = TaskStatus.RETRYING

                delay = compute_retry_delay(retry_count)
                logger.info(f"Task {record.id} will retry in {delay}s (attempt {retry_count}/{record.max_retries})")
                await asyncio.sleep(delay)
                return await self.execute(record, run_fn)
            else:
                self._store.update_status(record.id, TaskStatus.FAILED, error=error_msg)
                record.status = TaskStatus.FAILED
                record.error = error_msg

        return record

    def cancel(self, task_id: str) -> bool:
        self._store.update_status(task_id, TaskStatus.CANCELLED)
        return True


task_runner = TaskRunner()
