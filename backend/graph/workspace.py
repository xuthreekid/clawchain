"""Agent 工作区初始化 — 从模板创建默认工作区文件"""

from __future__ import annotations

import shutil
from pathlib import Path

from config import DATA_DIR, resolve_agent_dir


TEMPLATES_DIR = DATA_DIR / "templates"

WORKSPACE_SUBDIRS = [
    "workspace",
    "workspace/skills",  # skills 在 workspace 内，Agent 可自写
    "workspace/memory",  # 每日笔记，在 workspace 内
    "knowledge",
    "sessions/archive",
    "storage/memory_index",
    "logs",
]

TEMPLATE_FILES = {
    "workspace/SOUL.md": "SOUL.md",
    "workspace/IDENTITY.md": "IDENTITY.md",
    "workspace/USER.md": "USER.md",
    "workspace/AGENTS.md": "AGENTS.md",
    "workspace/TOOLS.md": "TOOLS.md",
    "workspace/HEARTBEAT.md": "HEARTBEAT.md",
    "workspace/BOOTSTRAP.md": "BOOTSTRAP.md",
}


def _migrate_legacy_skills(agent_dir: Path) -> None:
    """将旧版 agent_dir/skills 迁移到 workspace/skills"""
    legacy = agent_dir / "skills"
    target = agent_dir / "workspace" / "skills"
    if not legacy.exists() or not target.exists():
        return
    for skill_dir in legacy.iterdir():
        if skill_dir.is_dir():
            dest = target / skill_dir.name
            if not dest.exists():
                shutil.copytree(skill_dir, dest)


def _migrate_legacy_memory(agent_dir: Path) -> None:
    """将旧版 agent_dir/memory 迁移到 workspace/memory"""
    legacy = agent_dir / "memory"
    target = agent_dir / "workspace" / "memory"
    if not legacy.exists() or legacy == target:
        return
    target.mkdir(parents=True, exist_ok=True)
    for fp in legacy.rglob("*"):
        if fp.is_file():
            rel = fp.relative_to(legacy)
            dest = target / rel
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(fp, dest)


def ensure_agent_workspace(agent_id: str, *, include_bootstrap: bool = True) -> Path:
    """
    确保 Agent 工作区目录存在并包含所有模板文件。
    已存在的文件不会被覆盖。
    返回 agent 根目录。
    """
    agent_dir = resolve_agent_dir(agent_id)

    for subdir in WORKSPACE_SUBDIRS:
        (agent_dir / subdir).mkdir(parents=True, exist_ok=True)

    _migrate_legacy_skills(agent_dir)
    _migrate_legacy_memory(agent_dir)

    for dest_rel, template_name in TEMPLATE_FILES.items():
        if not include_bootstrap and template_name == "BOOTSTRAP.md":
            continue

        dest = agent_dir / dest_rel
        if dest.exists():
            continue

        src = TEMPLATES_DIR / template_name
        if src.exists():
            shutil.copy2(src, dest)

    memory_md = agent_dir / "workspace" / "MEMORY.md"
    if not memory_md.exists():
        memory_md.write_text(
            "# 长期记忆\n\n（此文件用于记录跨会话的重要信息）\n",
            encoding="utf-8",
        )

    return agent_dir


def has_bootstrap(agent_id: str) -> bool:
    """检查 Agent 是否有未完成的 BOOTSTRAP.md"""
    bootstrap_path = resolve_agent_dir(agent_id) / "workspace" / "BOOTSTRAP.md"
    return bootstrap_path.exists()
