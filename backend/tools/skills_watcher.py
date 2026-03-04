"""Skills 热加载 — 监听 skills/ 目录变更，自动更新 SKILLS_SNAPSHOT.md

监听:
  - data/skills/ (全局共享) → 影响所有 Agent
  - data/agents/{id}/workspace/skills/ (Agent 私有) → 影响对应 Agent
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from config import DATA_DIR, list_agents, resolve_agent_workspace, resolve_global_skills_dir

logger = logging.getLogger(__name__)

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _HAS_WATCHDOG = True
except ImportError:
    _HAS_WATCHDOG = False

# 防抖：变更后延迟 N 秒再执行，避免连续编辑触发多次
_DEBOUNCE_SEC = 1.5
_pending: set[str] = set()  # agent_id
_timer: threading.Timer | None = None
_lock = threading.Lock()


def _flush_snapshots() -> None:
    """对 pending 中的 agent 执行 write_skills_snapshot，并推送 skills_updated 事件给前端"""
    global _timer, _pending
    with _lock:
        agents = list(_pending)
        _pending.clear()
        _timer = None
    if not agents:
        return
    try:
        from tools.skills_scanner import write_skills_snapshot
        from graph.agent import event_bus
        for agent_id in agents:
            try:
                write_skills_snapshot(agent_id)
                logger.debug(f"Skills snapshot updated for agent {agent_id} (hot reload)")
                event_bus.emit(agent_id, {"type": "lifecycle", "event": "skills_updated"})
            except Exception as e:
                logger.warning(f"Failed to update skills snapshot for {agent_id}: {e}")
    except Exception as e:
        logger.warning(f"Skills watcher flush failed: {e}")


def _schedule_flush(agent_ids: set[str]) -> None:
    global _timer, _pending
    with _lock:
        _pending.update(agent_ids)
        if _timer is not None:
            _timer.cancel()
        _timer = threading.Timer(_DEBOUNCE_SEC, _flush_snapshots)
        _timer.daemon = True
        _timer.start()


def _agent_id_from_workspace_skills(path: Path, agents_dir: Path) -> str | None:
    """从 data/agents/{id}/workspace/skills/... 解析 agent_id"""
    try:
        path = path.resolve()
        agents_resolved = agents_dir.resolve()
        if not str(path).startswith(str(agents_resolved)):
            return None
        rel = path.relative_to(agents_resolved)
        # rel = main/workspace/skills/foo/SKILL.md
        if len(rel.parts) >= 1:
            return rel.parts[0]
    except (ValueError, IndexError):
        pass
    return None


def _is_skill_related(path: Path) -> bool:
    """判断路径是否与技能相关（SKILL.md 或 skills 目录下的文件）"""
    p = Path(path)
    if p.is_dir():
        return False
    if p.name == "SKILL.md":
        return True
    if "skills" in p.parts and p.suffix in (".md", ".py", ".sh", ".js", ".ts"):
        return True
    return False


if _HAS_WATCHDOG:

    class _SkillsFileHandler(FileSystemEventHandler):
        def __init__(self, global_dir: Path, agents_dir: Path):
            self.global_dir = global_dir
            self.agents_dir = agents_dir

        def _on_event(self, event):
            if event.is_directory:
                return
            path = Path(event.src_path)
            if not _is_skill_related(path):
                return
            try:
                path = path.resolve()
                global_resolved = self.global_dir.resolve()
                agents_resolved = self.agents_dir.resolve()
                if str(path).startswith(str(global_resolved)):
                    agent_ids = {a["id"] for a in list_agents()}
                    if agent_ids:
                        _schedule_flush(agent_ids)
                    return
                if str(path).startswith(str(agents_resolved)):
                    aid = _agent_id_from_workspace_skills(path, self.agents_dir)
                    if aid:
                        _schedule_flush({aid})
            except Exception as e:
                logger.debug(f"Skills watcher path resolve: {e}")

        def on_modified(self, event):
            self._on_event(event)

        def on_created(self, event):
            self._on_event(event)

        def on_deleted(self, event):
            self._on_event(event)


class SkillsWatcher:
    """Skills 目录监听器，变更时自动更新 SKILLS_SNAPSHOT.md"""

    def __init__(self):
        self._observer: Observer | None = None

    def start(self) -> None:
        if not _HAS_WATCHDOG:
            logger.debug("watchdog not installed, skills hot reload disabled")
            return
        global_dir = resolve_global_skills_dir()
        agents_dir = DATA_DIR / "agents"
        handler = _SkillsFileHandler(global_dir, agents_dir)
        self._observer = Observer()
        if global_dir.exists():
            self._observer.schedule(handler, str(global_dir), recursive=True)
        if agents_dir.exists():
            for agent in list_agents():
                ws_skills = resolve_agent_workspace(agent["id"]) / "skills"
                if ws_skills.exists():
                    self._observer.schedule(handler, str(ws_skills), recursive=True)
        self._observer.daemon = True
        self._observer.start()
        logger.info("Skills watcher started (hot reload enabled)")

    def stop(self) -> None:
        global _timer
        with _lock:
            if _timer is not None:
                _timer.cancel()
                _timer = None
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            logger.info("Skills watcher stopped")


skills_watcher = SkillsWatcher()
