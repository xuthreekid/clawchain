"""文件读写 API + 技能列表"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config import DATA_DIR, resolve_agent_dir, resolve_agent_workspace

router = APIRouter()

ALLOWED_PREFIXES = ("workspace/", "memory/", "skills/", "knowledge/")
ALLOWED_ROOT_FILES = ("SKILLS_SNAPSHOT.md",)


def _validate_file_path(path: str, agent_id: str) -> Path:
    """验证文件路径，确保在白名单范围内"""
    if ".." in path:
        raise HTTPException(403, "路径中不允许包含 '..'")

    agent_dir = resolve_agent_dir(agent_id)
    workspace = resolve_agent_workspace(agent_id)

    # global/skills/xxx -> data/skills/xxx（只读，不用于 save）
    if path.startswith("global/skills/"):
        rel = path[len("global/skills/"):]
        full_path = (DATA_DIR / "skills" / rel).resolve()
        skills_root = (DATA_DIR / "skills").resolve()
        try:
            full_path.relative_to(skills_root)
        except ValueError:
            raise HTTPException(403, "路径逃逸出全局 skills 目录")
        return full_path

    is_allowed = (
        any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES)
        or path in ALLOWED_ROOT_FILES
    )
    if not is_allowed:
        raise HTTPException(403, f"不允许访问路径: {path}")

    # skills/xxx -> workspace/skills/xxx；memory/xxx -> workspace/memory/xxx
    if path.startswith("skills/"):
        full_path = (workspace / path).resolve()
    elif path.startswith("memory/"):
        full_path = (workspace / path).resolve()
    else:
        full_path = (agent_dir / path).resolve()

    try:
        full_path.relative_to(agent_dir.resolve())
    except ValueError:
        # global 路径已单独处理；workspace 下的 skills 需额外校验
        if path.startswith("skills/"):
            try:
                full_path.relative_to(workspace.resolve())
            except ValueError:
                raise HTTPException(403, "路径逃逸出工作区")
        else:
            raise HTTPException(403, "路径逃逸出 Agent 目录")

    return full_path


@router.get("/agents/{agent_id}/files")
async def read_file(agent_id: str, path: str = Query(...)):
    fp = _validate_file_path(path, agent_id)
    if not fp.exists():
        raise HTTPException(404, f"文件不存在: {path}")
    try:
        content = fp.read_text(encoding="utf-8")
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(500, str(e))


class FileSaveRequest(BaseModel):
    path: str
    content: str


@router.post("/agents/{agent_id}/files")
async def save_file(agent_id: str, req: FileSaveRequest):
    if req.path.startswith("global/"):
        raise HTTPException(403, "不允许修改全局 skills")
    fp = _validate_file_path(req.path, agent_id)
    try:
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(req.content, encoding="utf-8")

        if req.path == "workspace/MEMORY.md" or req.path == "MEMORY.md":
            from graph.agent import agent_manager
            indexer = agent_manager.memory_indexers.get(agent_id)
            if indexer:
                indexer.rebuild_index()

        if req.path.startswith("skills/") or req.path.startswith("workspace/skills/"):
            from tools.skills_scanner import write_skills_snapshot
            write_skills_snapshot(agent_id)

        return {"status": "ok", "path": req.path}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/agents/{agent_id}/skills")
async def list_skills(agent_id: str):
    from tools.skills_scanner import scan_skills_for_agent, scan_skills_detailed
    try:
        return scan_skills_detailed(agent_id)
    except Exception:
        return scan_skills_for_agent(agent_id)


class SkillToggleRequest(BaseModel):
    skill_name: str
    enabled: bool


@router.put("/agents/{agent_id}/skills")
async def update_agent_skill(agent_id: str, req: SkillToggleRequest):
    """按 Agent 切换 skill 启用状态，更新 config.agents.list[].skills（allowlist）"""
    from config import get_raw_config, save_config

    cfg = get_raw_config()
    agents_list = cfg.get("agents", {}).get("list", [])
    idx = next((i for i, a in enumerate(agents_list) if a.get("id") == agent_id), -1)
    if idx < 0:
        raise HTTPException(404, f"Agent '{agent_id}' 不存在")

    from tools.skills_scanner import scan_skills_for_agent, _resolve_agent_skills_allowlist

    all_names = [s["name"] for s in scan_skills_for_agent(agent_id)]
    allowlist = _resolve_agent_skills_allowlist(agent_id)
    current = list(allowlist) if allowlist is not None else all_names
    current_set = set(current)
    name = req.skill_name.strip()
    if not name:
        raise HTTPException(400, "skill_name 不能为空")

    if req.enabled:
        current_set.add(name)
    else:
        current_set.discard(name)

    agents_list[idx] = dict(agents_list[idx])
    if current_set == set(all_names):
        agents_list[idx].pop("skills", None)
    else:
        agents_list[idx]["skills"] = sorted(current_set)

    save_config(cfg)

    from tools.skills_scanner import write_skills_snapshot
    write_skills_snapshot(agent_id)

    return {"status": "ok", "skills": agents_list[idx].get("skills")}
