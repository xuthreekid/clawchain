"""Skills 扫描器 — 扫描 Agent 私有 + 全局共享技能，生成 SKILLS_SNAPSHOT.md

支持 agents.list[].skills 按 Agent 的 allowlist 过滤。
- skills 未定义 → 全部启用
- skills = [] → 全部禁用
- skills = ["a","b"] → 仅 a、b 启用

技能接口规范：SKILL.md frontmatter 需包含 name、description（location 可推导）。
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import yaml

from config import (
    list_agents,
    resolve_agent_config,
    resolve_agent_dir,
    resolve_agent_skills_dir,
    resolve_agent_workspace,
    resolve_global_skills_dir,
)


logger = logging.getLogger(__name__)

REQUIRED_SKILL_FIELDS = ("name", "description")
OPTIONAL_SKILL_FIELDS = ("version", "location")


def _parse_skill_frontmatter(skill_md_path: Path) -> dict[str, str] | None:
    """解析 SKILL.md 的 YAML frontmatter"""
    try:
        text = skill_md_path.read_text(encoding="utf-8")
    except Exception:
        return None

    if not text.startswith("---"):
        return None

    end = text.find("---", 3)
    if end == -1:
        return None

    fm_text = text[3:end].strip()
    try:
        data = yaml.safe_load(fm_text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def validate_skill_frontmatter(fm: dict[str, str] | None, skill_dir_name: str) -> list[str]:
    """校验 SKILL.md frontmatter 必填字段。返回错误列表，空表示通过。"""
    if not fm or not isinstance(fm, dict):
        return ["缺少有效 frontmatter"]
    errors: list[str] = []
    for field in REQUIRED_SKILL_FIELDS:
        val = fm.get(field)
        if not val or (isinstance(val, str) and not val.strip()):
            errors.append(f"缺少必填字段: {field}")
    return errors


def _resolve_agent_skills_allowlist(agent_id: str) -> set[str] | None:
    """解析 Agent 的 skills allowlist。None=全部启用，空 set=全部禁用，非空=仅这些启用"""
    cfg = resolve_agent_config(agent_id)
    raw = cfg.get("skills")
    if raw is None:
        return None
    if not isinstance(raw, list):
        return None
    return set(s.strip() for s in raw if isinstance(s, str) and s.strip())


def sync_global_skills_to_workspace(agent_id: str) -> None:
    """将 data/skills/* 完整同步到 workspace/skills/（含 SKILL.md、scripts/ 等所有文件），使 exec 的 cwd 内可访问"""
    global_dir = resolve_global_skills_dir()
    workspace_skills = resolve_agent_workspace(agent_id) / "skills"
    if not global_dir.exists():
        return
    workspace_skills.mkdir(parents=True, exist_ok=True)
    for skill_dir in global_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        dest = workspace_skills / skill_dir.name
        # 若 workspace 已有同名技能且 SKILL.md 存在，视为 agent 私有，跳过（不覆盖）
        if dest.exists() and (dest / "SKILL.md").exists():
            # 检查是否来自全局：若全局有 scripts 等而 workspace 没有，则补充（agent 私有通常无 scripts）
            for item in skill_dir.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(skill_dir)
                    dest_file = dest / rel
                    if not dest_file.exists():
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dest_file)
            continue
        # 完整复制整个技能目录（含 scripts/ 等子目录）
        shutil.copytree(skill_dir, dest, dirs_exist_ok=True)


def scan_skills_for_agent(agent_id: str) -> list[dict[str, str]]:
    """扫描指定 Agent 的技能（私有 + 全局共享），并标记 enabled 状态（按 agents.list[].skills）"""
    skills: list[dict[str, str]] = []
    seen_names: set[str] = set()
    allowlist = _resolve_agent_skills_allowlist(agent_id)

    def _is_enabled(name: str) -> bool:
        if allowlist is None:
            return True
        return name in allowlist

    def _add(name: str, description: str, location: str) -> None:
        if name not in seen_names:
            seen_names.add(name)
            skills.append({
                "name": name,
                "description": description,
                "location": location,
                "enabled": _is_enabled(name),
            })

    # 仅扫描 workspace/skills/（已包含 sync 后的全局技能，location 统一为 skills/{name}/SKILL.md）
    agent_skills_dir = resolve_agent_skills_dir(agent_id)
    if agent_skills_dir.exists():
        for skill_dir in sorted(agent_skills_dir.iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                fm = _parse_skill_frontmatter(skill_md)
                if fm:
                    errs = validate_skill_frontmatter(fm, skill_dir.name)
                    if errs:
                        logger.warning(
                            "Skill %s SKILL.md 不符合规范: %s (需含 name, description)",
                            skill_dir.name,
                            "; ".join(errs),
                        )
                    name = fm.get("name", skill_dir.name) or skill_dir.name
                    desc = fm.get("description", "") or ""
                    _add(name, desc, f"skills/{skill_dir.name}/SKILL.md")

    return skills


def generate_skills_snapshot(agent_id: str) -> str:
    """生成 SKILLS_SNAPSHOT.md 内容（仅包含 enabled 的 skills）"""
    all_skills = scan_skills_for_agent(agent_id)
    skills = [s for s in all_skills if s.get("enabled", True)]
    if not skills:
        return "<available_skills>\n(暂无可用技能)\n</available_skills>"

    lines = ["<available_skills>"]
    for s in skills:
        lines.append("  <skill>")
        lines.append(f"    <name>{s['name']}</name>")
        lines.append(f"    <description>{s['description']}</description>")
        lines.append(f"    <location>{s['location']}</location>")
        lines.append("  </skill>")
    lines.append("</available_skills>")
    return "\n".join(lines)


def write_skills_snapshot(agent_id: str) -> None:
    """写入 SKILLS_SNAPSHOT.md 到 Agent 目录"""
    sync_global_skills_to_workspace(agent_id)
    content = generate_skills_snapshot(agent_id)
    agent_dir = resolve_agent_dir(agent_id)
    snapshot_path = agent_dir / "SKILLS_SNAPSHOT.md"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(content, encoding="utf-8")


def scan_skills_detailed(agent_id: str) -> list[dict[str, Any]]:
    """返回结构化技能详情列表（用于 API 和前端管理面板）"""
    skills: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    allowlist = _resolve_agent_skills_allowlist(agent_id)

    def _is_enabled(name: str) -> bool:
        if allowlist is None:
            return True
        return name in allowlist

    agent_skills_dir = resolve_agent_skills_dir(agent_id)
    if not agent_skills_dir.exists():
        return skills

    for skill_dir in sorted(agent_skills_dir.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        fm = _parse_skill_frontmatter(skill_md)
        if not fm:
            continue

        name = fm.get("name", skill_dir.name) or skill_dir.name
        if name in seen_names:
            continue
        seen_names.add(name)

        errs = validate_skill_frontmatter(fm, skill_dir.name)
        metadata = fm.get("metadata", {}) or {}
        nanobot_meta = metadata.get("nanobot", {}) or {}
        requires = nanobot_meta.get("requires", {}) or {}

        status = "available"
        missing_deps: list[str] = []
        for bin_name in (requires.get("bins") or []):
            import shutil
            if not shutil.which(bin_name):
                missing_deps.append(f"bin:{bin_name}")
                status = "missing_deps"
        for env_name in (requires.get("env") or []):
            import os
            if not os.environ.get(env_name):
                missing_deps.append(f"env:{env_name}")
                status = "missing_deps"
        if errs:
            status = "invalid"

        skill_body = ""
        try:
            text = skill_md.read_text(encoding="utf-8")
            end = text.find("---", 3)
            if end != -1:
                skill_body = text[end + 3:].strip()[:500]
        except Exception:
            pass

        skills.append({
            "name": name,
            "description": fm.get("description", "") or "",
            "version": fm.get("version", "1.0"),
            "location": f"skills/{skill_dir.name}/SKILL.md",
            "enabled": _is_enabled(name),
            "status": status,
            "missing_deps": missing_deps,
            "validation_errors": errs,
            "always": nanobot_meta.get("always", False),
            "emoji": nanobot_meta.get("emoji", ""),
            "body_preview": skill_body[:200] if skill_body else "",
        })

    return skills


def scan_all_skills() -> None:
    """为所有已配置的 Agent 生成技能快照"""
    for agent in list_agents():
        write_skills_snapshot(agent["id"])
