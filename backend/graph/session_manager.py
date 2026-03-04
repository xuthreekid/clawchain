"""会话管理器 — JSON 文件持久化 + 生命周期事件 + LRU 缓存"""

from __future__ import annotations

import asyncio
import json
import re
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any

from config import get_config, resolve_agent_sessions_dir


class _SessionCache:
    """LRU 缓存: 只保留最近 N 个会话在内存中"""

    def __init__(self, max_size: int = 20):
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def put(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._cache[key] = value
            self._cache.move_to_end(key)
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


class SessionManager:
    _locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()
    _cache = _SessionCache(max_size=30)
    _SESSION_BOOTSTRAP_PREFIXES = (
        "a new session was started via /new or /reset",
        "[system message]",
    )

    def _is_bootstrap_text(self, text: str | None) -> bool:
        raw = (text or "").strip()
        if not raw:
            return False
        lowered = raw.lower()
        return any(lowered.startswith(prefix) for prefix in self._SESSION_BOOTSTRAP_PREFIXES)

    def _get_lock(self, session_id: str, agent_id: str) -> threading.Lock:
        key = f"{agent_id}:{session_id}"
        with self._locks_guard:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            return self._locks[key]

    @staticmethod
    def _emit_lifecycle(event_name: str, agent_id: str, session_id: str, **extra: Any) -> None:
        try:
            from graph.session_lifecycle import lifecycle_bus, LifecycleEvent, LifecyclePayload
            ev = LifecycleEvent(event_name)
            lifecycle_bus.emit(LifecyclePayload(
                event=ev, agent_id=agent_id, session_id=session_id, data=extra,
            ))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 主会话 — 每个 Agent 有且仅有一个主会话
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_main_session_id(agent_id: str) -> str:
        """返回 Agent 的固定主会话 ID（用于文件命名）"""
        return f"{agent_id}-main"

    @staticmethod
    def session_key_from_session_id(agent_id: str, session_id: str) -> str:
        """session_id -> session_key（agent:agentId:main / agent:agentId:subagent:xxx）"""
        main_sid = f"{agent_id}-main"
        if session_id == main_sid:
            return f"agent:{agent_id}:main"
        return f"agent:{agent_id}:subagent:{session_id}"

    @staticmethod
    def session_id_from_session_key(session_key: str) -> tuple[str, str] | None:
        """session_key -> (agent_id, session_id)。主会话 session_id=agent_id-main；子会话 session_id=subagent-xxx"""
        parts = (session_key or "").strip().split(":")
        if len(parts) < 3:
            return None
        if parts[0].lower() != "agent":
            return None
        agent_id = parts[1]
        rest = ":".join(parts[2:])
        if rest == "main":
            return (agent_id, f"{agent_id}-main")
        if len(parts) >= 4 and parts[2].lower() == "subagent":
            return (agent_id, parts[3])  # session_id = subagent-xxx
        return (agent_id, rest)

    # ------------------------------------------------------------------
    # 读取
    # ------------------------------------------------------------------

    def _session_path(self, session_id: str, agent_id: str) -> Path:
        return resolve_agent_sessions_dir(agent_id) / f"{session_id}.json"

    def load_session(self, session_id: str, agent_id: str) -> dict[str, Any] | None:
        cache_key = f"{agent_id}:{session_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        path = self._session_path(session_id, agent_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                data = {
                    "label": "未命名",
                    "agent_id": agent_id,
                    "created_at": time.time(),
                    "updated_at": time.time(),
                    "compressed_context": None,
                    "messages": data,
                }
            if isinstance(data, dict):
                current_label = str(data.get("label", "")).strip()
                if current_label and self._is_bootstrap_text(current_label):
                    data.pop("label", None)
                if not data.get("label") and data.get("title"):
                    candidate = str(data.get("title", "")).strip()
                    if candidate and not self._is_bootstrap_text(candidate):
                        data["label"] = candidate

            self._cache.put(cache_key, data)
            return data
        except Exception:
            return None

    def load_session_for_agent(
        self, session_id: str, agent_id: str
    ) -> list[dict[str, Any]]:
        """
        为 LLM 优化的消息列表：
        - 合并连续 assistant 消息
        - 在头部注入 compressed_context
        """
        data = self.load_session(session_id, agent_id)
        if data is None:
            return []

        messages: list[dict[str, Any]] = []

        compressed = data.get("compressed_context")
        if compressed:
            messages.append({
                "role": "assistant",
                "content": f"[以下是之前对话的摘要]\n{compressed}",
            })

        raw_messages = data.get("messages", [])
        for msg in raw_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if messages and messages[-1]["role"] == "assistant" and role == "assistant":
                messages[-1]["content"] += "\n\n" + content
            else:
                messages.append({"role": role, "content": content})

        return messages

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def ensure_session(
        self,
        session_id: str,
        agent_id: str,
        spawned_by: str | None = None,
        label: str | None = None,
    ) -> dict[str, Any]:
        data = self.load_session(session_id, agent_id)
        if data is not None:
            return data
        if not spawned_by and session_id.startswith("subagent-"):
            try:
                from graph.subagent_registry import registry
                child_sk = self.session_key_from_session_id(agent_id, session_id)
                resolved = registry.resolve_requester_for_child_session(child_sk)
                if resolved:
                    spawned_by = resolved[0]
            except Exception:
                pass
        data = {
            "session_id": session_id,
            "agent_id": agent_id,
            "created_at": time.time(),
            "updated_at": time.time(),
            "compressed_context": None,
            "messages": [],
        }
        if label and str(label).strip():
            data["label"] = str(label).strip()[:120]
        if spawned_by:
            data["spawned_by"] = spawned_by
        self._save_session_data(session_id, agent_id, data)
        self._update_session_store_entry(
            agent_id,
            self.session_key_from_session_id(agent_id, session_id),
            session_id,
            data["updated_at"],
            label=data.get("label", ""),
            spawned_by=spawned_by,
        )
        self._emit_lifecycle("session_create", agent_id, session_id)
        return data

    def rollback_last_turn(self, session_id: str, agent_id: str) -> bool:
        """移除最后一轮 user + assistant 消息（用于心跳 HEARTBEAT_OK 时不持久化）"""
        data = self.load_session(session_id, agent_id)
        if not data or not data.get("messages"):
            return False
        msgs = data["messages"]
        if len(msgs) < 2:
            return False
        last = msgs[-1]
        second = msgs[-2]
        if last.get("role") != "assistant" or second.get("role") != "user":
            return False
        data["messages"] = msgs[:-2]
        data["updated_at"] = time.time()
        self._save_session_data(session_id, agent_id, data)
        return True

    def save_message(
        self,
        session_id: str,
        agent_id: str,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        data = self.ensure_session(session_id, agent_id)
        msg: dict[str, Any] = {"role": role, "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        data["messages"].append(msg)
        data["updated_at"] = time.time()
        self._save_session_data(session_id, agent_id, data)

    def _session_store_path(self, agent_id: str) -> Path:
        """sessions.json 索引路径"""
        return resolve_agent_sessions_dir(agent_id) / "sessions.json"

    def _load_session_store(self, agent_id: str) -> dict[str, dict[str, Any]]:
        """加载 sessions.json 索引"""
        path = self._session_store_path(agent_id)
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_session_store(
        self, agent_id: str, store: dict[str, dict[str, Any]]
    ) -> None:
        """持久化 sessions.json"""
        path = self._session_store_path(agent_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=2)

    def _update_session_store_entry(
        self,
        agent_id: str,
        session_key: str,
        session_id: str,
        updated_at: float,
        label: str = "",
        spawned_by: str | None = None,
    ) -> None:
        """更新 sessions.json 中的会话条目，并在 mode=enforce 时执行 maintenance"""
        store = self._load_session_store(agent_id)
        entry = store.get(session_key, {})
        entry["sessionId"] = session_id
        entry["updatedAt"] = int(updated_at * 1000)
        if label:
            entry["label"] = label
        elif "label" in entry:
            entry.pop("label", None)
        if "title" in entry:
            entry.pop("title", None)
        if spawned_by:
            entry["spawnedBy"] = spawned_by
        store[session_key] = entry
        store, _ = self._run_session_maintenance(agent_id, store=store, enforce=False)
        self._save_session_store(agent_id, store)

    def _remove_session_store_entry(self, agent_id: str, session_key: str) -> None:
        """从 sessions.json 移除会话"""
        store = self._load_session_store(agent_id)
        store.pop(session_key, None)
        self._save_session_store(agent_id, store)

    def _parse_byte_size(self, raw: str | int | float | None, default_unit: str = "b") -> int | None:
        """解析字节大小，如 '500mb'、'1gb'。支持 b/kb/mb/gb。返回 None 表示无效或未设置。"""
        if raw is None or raw == "":
            return None
        s = str(raw).strip().lower()
        if not s:
            return None
        units: dict[str, int] = {
            "b": 1,
            "kb": 1024,
            "k": 1024,
            "mb": 1024**2,
            "m": 1024**2,
            "gb": 1024**3,
            "g": 1024**3,
        }
        m = re.match(r"^(\d+(?:\.\d+)?)\s*([a-z]+)?$", s)
        if not m:
            return None
        try:
            val = float(m.group(1))
            unit = (m.group(2) or default_unit).lower()
            mult = units.get(unit, 1)
            return int(val * mult)
        except (ValueError, TypeError):
            return None

    def _resolve_disk_budget(self) -> tuple[int | None, int | None]:
        """解析 maxDiskBytes、highWaterBytes。highWaterBytes 未设时默认为 maxDiskBytes 的 80%。"""
        cfg = get_config()
        maint = (cfg.get("session") or {}).get("maintenance") or {}
        max_raw = maint.get("maxDiskBytes")
        high_raw = maint.get("highWaterBytes")
        max_bytes = self._parse_byte_size(max_raw) if max_raw is not None else None
        if max_bytes is not None and max_bytes <= 0:
            max_bytes = None
        if high_raw is not None and str(high_raw).strip():
            high_bytes = self._parse_byte_size(high_raw)
            if high_bytes is not None and max_bytes is not None:
                high_bytes = min(high_bytes, max_bytes)
        elif max_bytes is not None:
            high_bytes = max(1, int(max_bytes * 0.8))
        else:
            high_bytes = None
        return max_bytes, high_bytes

    def _enforce_disk_budget(
        self, agent_id: str, store: dict, dry_run: bool = False
    ) -> dict[str, Any] | None:
        """按 updatedAt 从最旧开始删除直到低于 highWaterBytes"""
        max_bytes, high_bytes = self._resolve_disk_budget()
        if max_bytes is None or high_bytes is None:
            return None
        sessions_dir = resolve_agent_sessions_dir(agent_id)
        if not sessions_dir.exists():
            return {"totalBytesBefore": 0, "totalBytesAfter": 0, "removedFiles": 0, "removedEntries": 0, "freedBytes": 0, "maxBytes": max_bytes, "highWaterBytes": high_bytes, "overBudget": False}

        def _dir_size(p: Path) -> int:
            total = 0
            for f in p.rglob("*"):
                if f.is_file():
                    try:
                        total += f.stat().st_size
                    except OSError:
                        pass
            return total

        total = _dir_size(sessions_dir)
        total_before = total
        if total <= max_bytes:
            return {
                "totalBytesBefore": total_before,
                "totalBytesAfter": total,
                "removedFiles": 0,
                "removedEntries": 0,
                "freedBytes": 0,
                "maxBytes": max_bytes,
                "highWaterBytes": high_bytes,
                "overBudget": False,
            }

        removed_files = 0
        removed_entries = 0
        freed = 0

        # 1. 先删 archive 目录下最旧的文件
        archive_dir = sessions_dir / "archive"
        if archive_dir.exists():
            archive_files: list[tuple[Path, float, int]] = []
            for f in archive_dir.iterdir():
                if f.is_file():
                    try:
                        st = f.stat()
                        archive_files.append((f, st.st_mtime, st.st_size))
                    except OSError:
                        pass
            archive_files.sort(key=lambda x: x[1])
            for path_f, _, size in archive_files:
                if total <= high_bytes:
                    break
                if not dry_run:
                    try:
                        path_f.unlink()
                        total -= size
                        freed += size
                        removed_files += 1
                    except OSError:
                        pass

        # 2. 若仍超限，按 updatedAt 从最旧开始删 store 条目及对应 transcript
        main_sid = self.resolve_main_session_id(agent_id)
        main_key = self.session_key_from_session_id(agent_id, main_sid)
        keys_sorted = sorted(
            store.keys(),
            key=lambda k: store.get(k, {}).get("updatedAt") or 0,
        )
        for key in keys_sorted:
            if total <= high_bytes:
                break
            if key == main_key:
                continue
            entry = store.get(key, {})
            if not entry:
                continue
            sid = entry.get("sessionId")
            if not sid:
                continue
            path_f = self._session_path(sid, agent_id)
            size = 0
            if path_f.exists():
                try:
                    size = path_f.stat().st_size
                except OSError:
                    pass
            if not dry_run:
                store.pop(key, None)
                removed_entries += 1
                if path_f.exists():
                    try:
                        path_f.unlink()
                    except OSError:
                        pass
                total -= size
                freed += size
                removed_files += 1

        if not dry_run and removed_entries:
            self._save_session_store(agent_id, store)

        return {
            "totalBytesBefore": total_before,
            "totalBytesAfter": total,
            "removedFiles": removed_files,
            "removedEntries": removed_entries,
            "freedBytes": freed,
            "maxBytes": max_bytes,
            "highWaterBytes": high_bytes,
            "overBudget": total > high_bytes,
        }

    def _parse_prune_after_ms(self) -> int:
        """解析 session.maintenance.pruneAfter（如 30d、7d）为毫秒"""
        cfg = get_config()
        raw = (cfg.get("session") or {}).get("maintenance") or {}
        s = str(raw.get("pruneAfter", "30d")).strip().lower()
        m = re.match(r"^(\d+)\s*(d|h|m|s)?$", s)
        if not m:
            return 30 * 24 * 3600 * 1000
        num = int(m.group(1))
        unit = (m.group(2) or "d").lower()
        if unit == "d":
            return num * 24 * 3600 * 1000
        if unit == "h":
            return num * 3600 * 1000
        if unit == "m":
            return num * 60 * 1000
        return num * 1000

    def _run_session_maintenance(
        self, agent_id: str, store: dict | None = None, enforce: bool = False, dry_run: bool = False
    ) -> tuple[dict, dict[str, Any]]:
        """prune 过期 + cap 超限 + 磁盘预算。返回 (store, report)"""
        if store is None:
            store = self._load_session_store(agent_id)
        cfg = get_config()
        maint = (cfg.get("session") or {}).get("maintenance") or {}
        mode = maint.get("mode", "warn")
        if not enforce and not dry_run and mode == "warn":
            disk_budget = self._enforce_disk_budget(agent_id, store, dry_run=True)
            return store, {"pruned": 0, "capped": 0, "diskBudget": disk_budget}
        prune_after_ms = self._parse_prune_after_ms()
        max_entries = int(maint.get("maxEntries", 500))
        now_ms = int(time.time() * 1000)
        cutoff_ms = now_ms - prune_after_ms
        to_remove: set[str] = set()

        for key, entry in list(store.items()):
            updated = entry.get("updatedAt")
            if isinstance(updated, (int, float)) and updated < cutoff_ms:
                to_remove.add(key)
        pruned = len(to_remove)

        keys_sorted = sorted(
            store.keys(),
            key=lambda k: store.get(k, {}).get("updatedAt") or 0,
            reverse=True,
        )
        if len(keys_sorted) > max_entries:
            for k in keys_sorted[max_entries:]:
                if k not in to_remove:
                    to_remove.add(k)
        capped = len(to_remove) - pruned

        if not dry_run:
            for key in to_remove:
                entry = store.get(key, {})
                sid = entry.get("sessionId")
                if sid:
                    path = self._session_path(sid, agent_id)
                    if path.exists():
                        try:
                            archive_dir = path.parent / "archive"
                            archive_dir.mkdir(parents=True, exist_ok=True)
                            path.rename(archive_dir / f"{sid}.deleted.{int(time.time())}.json")
                        except Exception:
                            try:
                                path.unlink()
                            except Exception:
                                pass
                store.pop(key, None)
            if to_remove:
                self._save_session_store(agent_id, store)

        disk_budget = self._enforce_disk_budget(agent_id, store, dry_run=dry_run)
        return store, {"pruned": pruned, "capped": capped, "diskBudget": disk_budget}

    def _save_session_data(
        self, session_id: str, agent_id: str, data: dict[str, Any]
    ) -> None:
        lock = self._get_lock(session_id, agent_id)
        with lock:
            path = self._session_path(session_id, agent_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            cache_key = f"{agent_id}:{session_id}"
            self._cache.put(cache_key, data)
            session_key = self.session_key_from_session_id(agent_id, session_id)
            self._update_session_store_entry(
                agent_id,
                session_key,
                session_id,
                data.get("updated_at", time.time()),
                label=data.get("label", ""),
                spawned_by=data.get("spawned_by"),
            )

    # ------------------------------------------------------------------
    # 会话管理
    # ------------------------------------------------------------------

    def list_sessions(
        self,
        agent_id: str,
        spawned_by_session_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出会话。优先从 sessions.json 索引读取并按 updatedAt 排序。
        spawned_by_session_key: 仅返回该 requester 派生的子会话。"""
        sessions_dir = resolve_agent_sessions_dir(agent_id)
        store = self._load_session_store(agent_id)
        main_sid = self.resolve_main_session_id(agent_id)
        main_key = self.session_key_from_session_id(agent_id, main_sid)

        # 确保主会话在 store 中
        if main_key not in store:
            main_data = self.load_session(main_sid, agent_id)
            if main_data:
                if isinstance(main_data, list):
                    main_data = {"messages": main_data, "label": "未命名"}
            else:
                main_data = {"messages": [], "label": "主会话", "created_at": 0, "updated_at": 0}
            self._update_session_store_entry(
                agent_id, main_key, main_sid,
                main_data.get("updated_at", time.time()),
                label=main_data.get("label", "主会话"),
            )
            store[main_key] = {
                "sessionId": main_sid,
                "updatedAt": int((main_data.get("updated_at") or 0) * 1000),
                "label": main_data.get("label", "主会话"),
            }

        # 扫描 subagent-*.json，补充 store 中缺失的
        if sessions_dir.exists():
            for fp in sessions_dir.glob("subagent-*.json"):
                session_id = fp.stem
                sk = self.session_key_from_session_id(agent_id, session_id)
                if sk not in store:
                    try:
                        with open(fp, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if isinstance(data, list):
                            data = {"messages": data, "label": "未命名"}
                        spawned_by = data.get("spawned_by")
                        if not spawned_by:
                            try:
                                from graph.subagent_registry import registry
                                resolved = registry.resolve_requester_for_child_session(sk)
                                if resolved:
                                    spawned_by = resolved[0]
                            except Exception:
                                pass
                        self._update_session_store_entry(
                            agent_id, sk, session_id,
                            data.get("updated_at", fp.stat().st_mtime),
                            label=data.get("label", ""),
                            spawned_by=spawned_by,
                        )
                        store[sk] = {
                            "sessionId": session_id,
                            "updatedAt": int((data.get("updated_at") or 0) * 1000),
                            "label": data.get("label", ""),
                            "spawnedBy": spawned_by,
                        }
                    except Exception:
                        continue

        result: list[dict[str, Any]] = []
        for session_key, entry in store.items():
            if spawned_by_session_key and entry.get("spawnedBy") != spawned_by_session_key:
                continue
            session_id = entry.get("sessionId", "")
            data = self.load_session(session_id, agent_id)
            if data is None and session_id != main_sid:
                continue
            if data:
                if isinstance(data, list):
                    data = {"messages": data, "label": "未命名"}
            else:
                data = {"messages": [], "label": "主会话", "created_at": 0, "updated_at": 0}
            resolved_title = self.derive_session_title(
                data,
                session_id=session_id,
                updated_at=data.get("updated_at"),
            )
            result.append({
                "session_id": session_id,
                "session_key": session_key,
                "title": resolved_title,
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "message_count": len(data.get("messages", [])),
                "spawned_by": entry.get("spawnedBy"),
            })

        result.sort(key=lambda x: (x.get("updated_at") or 0), reverse=True)
        return result

    def create_session(self, agent_id: str, title: str = "新会话") -> str:
        session_id = uuid.uuid4().hex[:12]
        data = {
            "session_id": session_id,
            "agent_id": agent_id,
            "created_at": time.time(),
            "updated_at": time.time(),
            "compressed_context": None,
            "messages": [],
        }
        if title and title.strip():
            data["label"] = title.strip()
        self._save_session_data(session_id, agent_id, data)
        return session_id

    def rename_session(self, session_id: str, agent_id: str, title: str) -> bool:
        data = self.load_session(session_id, agent_id)
        if data is None:
            return False
        data["label"] = title
        data["updated_at"] = time.time()
        self._save_session_data(session_id, agent_id, data)
        return True

    def set_memory_flush_compaction_count(
        self, session_id: str, agent_id: str, count: int
    ) -> None:
        """记录本压缩周期已执行 Memory Flush"""
        data = self.load_session(session_id, agent_id)
        if data is None:
            return
        data["memory_flush_compaction_count"] = count
        data["updated_at"] = time.time()
        self._save_session_data(session_id, agent_id, data)

    def delete_session(self, session_id: str, agent_id: str) -> bool:
        path = self._session_path(session_id, agent_id)
        if path.exists():
            path.unlink()
            cache_key = f"{agent_id}:{session_id}"
            self._cache.invalidate(cache_key)
            session_key = self.session_key_from_session_id(agent_id, session_id)
            self._remove_session_store_entry(agent_id, session_key)
            return True
        return False

    # ------------------------------------------------------------------
    # 压缩
    # ------------------------------------------------------------------

    def compress_history(
        self,
        session_id: str,
        agent_id: str,
        summary: str,
        n_messages: int,
    ) -> dict[str, int]:
        data = self.load_session(session_id, agent_id)
        if data is None:
            return {"archived_count": 0, "remaining_count": 0}

        messages = data.get("messages", [])
        if len(messages) < 4:
            return {"archived_count": 0, "remaining_count": len(messages)}

        archive_count = min(n_messages, len(messages))
        archived = messages[:archive_count]
        remaining = messages[archive_count:]

        archive_dir = resolve_agent_sessions_dir(agent_id) / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"{session_id}_{int(time.time())}.json"
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(archived, f, ensure_ascii=False, indent=2)

        existing_context = data.get("compressed_context") or ""
        if existing_context:
            data["compressed_context"] = existing_context + "\n---\n" + summary
        else:
            data["compressed_context"] = summary

        data["messages"] = remaining
        data["updated_at"] = time.time()
        self._save_session_data(session_id, agent_id, data)

        # 记录压缩历史（用于审计/回滚）
        compactions_path = resolve_agent_sessions_dir(agent_id) / "compactions.jsonl"
        try:
            record = {
                "session_id": session_id,
                "agent_id": agent_id,
                "ts": time.time(),
                "archived_count": archive_count,
                "remaining_count": len(remaining),
                "summary_len": len(summary),
            }
            with open(compactions_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass  # 非关键，静默忽略

        return {
            "archived_count": archive_count,
            "remaining_count": len(remaining),
        }

    def get_compressed_context(self, session_id: str, agent_id: str) -> str | None:
        data = self.load_session(session_id, agent_id)
        if data is None:
            return None
        return data.get("compressed_context")

    # ------------------------------------------------------------------
    # 会话标题推导
    # ------------------------------------------------------------------

    DERIVED_TITLE_MAX_LEN = 60

    def derive_session_title(
        self, data: dict[str, Any] | None, session_id: str = "", updated_at: float | None = None
    ) -> str:
        """从 label/displayName/subject/首条真实用户消息或 session_id 推导标题"""
        if not data:
            return "未命名"
        label = str(data.get("label", "")).strip()
        if label and not self._is_bootstrap_text(label):
            return label[: self.DERIVED_TITLE_MAX_LEN]
        if data.get("displayName", "").strip():
            return data["displayName"].strip()[: self.DERIVED_TITLE_MAX_LEN]
        if data.get("subject", "").strip():
            return data["subject"].strip()[: self.DERIVED_TITLE_MAX_LEN]
        for msg in data.get("messages", []):
            if msg.get("role") == "user" and msg.get("content", "").strip():
                text = " ".join(str(msg.get("content", "")).split()).strip()
                lowered = text.lower()
                if any(lowered.startswith(prefix) for prefix in self._SESSION_BOOTSTRAP_PREFIXES):
                    continue
                if text.startswith("/new") or text.startswith("/reset"):
                    continue
                if len(text) > self.DERIVED_TITLE_MAX_LEN:
                    cut = text[: self.DERIVED_TITLE_MAX_LEN - 1]
                    last_space = cut.rfind(" ")
                    if last_space > self.DERIVED_TITLE_MAX_LEN * 0.6:
                        text = cut[:last_space] + "…"
                    else:
                        text = cut + "…"
                return text or "未命名"
        if session_id and updated_at:
            return f"{session_id} @ {int(updated_at)}"
        return "未命名"

    # ------------------------------------------------------------------
    # 会话重置
    # ------------------------------------------------------------------

    def reset_session(self, session_id: str, agent_id: str) -> dict[str, Any]:
        """
        重置会话：归档旧 JSON 并创建空白会话。
        返回 {"archived": bool, "archive_file": str}
        标题：使用 derive_session_title 推导，避免重复追加 (续)
        """
        import time as _time

        result: dict[str, Any] = {"archived": False}

        path = self._session_path(session_id, agent_id)
        if path.exists():
            archive_dir = resolve_agent_sessions_dir(agent_id) / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            ts = int(_time.time())
            archive_name = f"{session_id}.reset.{ts}.json"
            path.rename(archive_dir / archive_name)
            result["archived"] = True
            result["archive_file"] = f"archive/{archive_name}"

        cache_key = f"{agent_id}:{session_id}"
        self._cache.invalidate(cache_key)
        self.ensure_session(session_id, agent_id)

        return result

    # ------------------------------------------------------------------
    # 获取活跃会话 ID
    # ------------------------------------------------------------------

    def get_active_session_id(self, agent_id: str) -> str | None:
        """返回 Agent 最近活跃的会话 ID"""
        sessions = self.list_sessions(agent_id)
        return sessions[0]["session_id"] if sessions else None


session_manager = SessionManager()
