"""操作撤销栈 — 记录文件变更 diff，支持 /undo 回滚"""

from __future__ import annotations

import json
import shutil
import time
import threading
from collections import deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any


class OpKind(str, Enum):
    WRITE = "write"
    EDIT = "edit"
    DELETE = "delete"
    EXEC = "exec"


@dataclass
class UndoEntry:
    op: OpKind
    path: str
    timestamp: float = field(default_factory=time.time)
    backup_path: str | None = None
    old_content: str | None = None
    new_content: str | None = None
    was_new_file: bool = False
    command: str | None = None
    agent_id: str = "main"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["op"] = self.op.value
        return d


class UndoStack:
    """Per-agent 撤销栈，支持文件操作回滚"""

    def __init__(self, max_size: int = 50):
        self._stacks: dict[str, deque[UndoEntry]] = {}
        self._max_size = max_size
        self._lock = threading.Lock()

    def _get_stack(self, agent_id: str) -> deque[UndoEntry]:
        if agent_id not in self._stacks:
            self._stacks[agent_id] = deque(maxlen=self._max_size)
        return self._stacks[agent_id]

    def record_write(
        self,
        agent_id: str,
        path: str,
        old_content: str | None,
        new_content: str,
        was_new_file: bool = False,
    ) -> None:
        with self._lock:
            entry = UndoEntry(
                op=OpKind.WRITE,
                path=path,
                old_content=old_content,
                new_content=new_content,
                was_new_file=was_new_file,
                agent_id=agent_id,
            )
            self._get_stack(agent_id).append(entry)

    def record_edit(
        self,
        agent_id: str,
        path: str,
        old_content: str,
        new_content: str,
    ) -> None:
        with self._lock:
            entry = UndoEntry(
                op=OpKind.EDIT,
                path=path,
                old_content=old_content,
                new_content=new_content,
                agent_id=agent_id,
            )
            self._get_stack(agent_id).append(entry)

    def record_delete(
        self,
        agent_id: str,
        path: str,
        old_content: str,
    ) -> None:
        with self._lock:
            entry = UndoEntry(
                op=OpKind.DELETE,
                path=path,
                old_content=old_content,
                agent_id=agent_id,
            )
            self._get_stack(agent_id).append(entry)

    def undo(self, agent_id: str) -> UndoEntry | None:
        """回滚最近一次文件操作。成功返回 entry，栈空返回 None。"""
        with self._lock:
            stack = self._get_stack(agent_id)
            if not stack:
                return None
            entry = stack.pop()

        target = Path(entry.path)
        try:
            if entry.op == OpKind.WRITE:
                if entry.was_new_file:
                    if target.exists():
                        target.unlink()
                elif entry.old_content is not None:
                    target.write_text(entry.old_content, encoding="utf-8")
            elif entry.op == OpKind.EDIT:
                if entry.old_content is not None:
                    target.write_text(entry.old_content, encoding="utf-8")
            elif entry.op == OpKind.DELETE:
                if entry.old_content is not None:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(entry.old_content, encoding="utf-8")
        except Exception:
            pass

        return entry

    def peek(self, agent_id: str, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            stack = self._get_stack(agent_id)
            items = list(stack)[-limit:][::-1]
            result = []
            for e in items:
                d = e.to_dict()
                d.pop("old_content", None)
                d.pop("new_content", None)
                d.pop("backup_path", None)
                result.append(d)
            return result

    def clear(self, agent_id: str) -> int:
        with self._lock:
            stack = self._get_stack(agent_id)
            count = len(stack)
            stack.clear()
            return count


def _get_undo_stack_size() -> int:
    try:
        from config import get_config
        return get_config().get("sandbox", {}).get("undoStackSize", 50)
    except Exception:
        return 50


undo_stack = UndoStack(max_size=50)


def refresh_undo_stack_size() -> None:
    """配置加载后调用，更新撤销栈大小"""
    size = _get_undo_stack_size()
    undo_stack._max_size = size


def safe_write_atomic(path: Path, content: str, encoding: str = "utf-8") -> None:
    """事务性写入：先写 .tmp 再 rename，避免写入中断导致数据损坏"""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(content, encoding=encoding)
        shutil.move(str(tmp_path), str(path))
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise
