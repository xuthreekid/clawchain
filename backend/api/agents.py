"""Agent CRUD API"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import (
    list_agents,
    resolve_agent_config,
    resolve_agent_dir,
    add_agent_to_config,
    save_config,
    get_raw_config,
)

router = APIRouter()


class AgentCreateRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    model: str | None = None


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    model: str | None = None


@router.get("/agents")
async def get_agents():
    agents = list_agents()
    result = []
    for a in agents:
        agent_dir = resolve_agent_dir(a["id"])
        result.append({
            **a,
            "has_workspace": (agent_dir / "workspace").exists(),
        })
    return result


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    cfg = resolve_agent_config(agent_id)
    if not any(a["id"] == agent_id for a in list_agents()):
        raise HTTPException(404, f"Agent '{agent_id}' 不存在")
    return cfg


@router.get("/agents/{agent_id}/tools")
async def get_agent_tools(agent_id: str):
    """列出指定 Agent 的 function call 工具（含 allowed 状态，供侧边栏 toggle 使用）"""
    if not any(a["id"] == agent_id for a in list_agents()):
        raise HTTPException(404, f"Agent '{agent_id}' 不存在")
    from tools import get_all_tools
    from config import is_tool_allowed_by_policy
    tools = get_all_tools(agent_id)
    categories = {
        "file": ["read", "write", "edit", "apply_patch", "grep", "find", "ls"],
        "runtime": ["exec", "python_repl", "process_list", "process_kill"],
        "web": ["web_search", "web_fetch"],
        "memory": ["memory_search", "memory_get"],
        "knowledge": ["search_knowledge_base"],
        "agent": ["agents_list", "sessions_list", "sessions_history", "sessions_send", "sessions_spawn", "subagents"],
        "cron": ["cron"],
        "status": ["session_status"],
    }
    result = []
    for t in tools:
        cat = "other"
        for k, names in categories.items():
            if t.name in names:
                cat = k
                break
        allowed = is_tool_allowed_by_policy(agent_id, t.name)
        result.append({"name": t.name, "description": t.description or "", "category": cat, "allowed": allowed})
    return result


@router.post("/agents")
async def create_agent(req: AgentCreateRequest):
    existing = [a["id"] for a in list_agents()]
    if req.id in existing:
        raise HTTPException(400, f"Agent '{req.id}' 已存在")

    from graph.workspace import ensure_agent_workspace

    ensure_agent_workspace(req.id, include_bootstrap=True)

    agent_dir = resolve_agent_dir(req.id)
    identity_path = agent_dir / "workspace" / "IDENTITY.md"
    with open(identity_path, "a", encoding="utf-8") as f:
        f.write(f"\n\n- **名称：** {req.name}\n")
        if req.description:
            f.write(f"- **描述：** {req.description}\n")

    agent_cfg = {
        "id": req.id,
        "name": req.name,
        "description": req.description,
        "model": req.model,
        "subagents": {
            "allow_agents": ["*"],
            "max_spawn_depth": 3,
            "max_children_per_agent": 5,
        },
    }
    add_agent_to_config(agent_cfg)

    from tools.skills_scanner import write_skills_snapshot
    write_skills_snapshot(req.id)

    from graph.agent import agent_manager
    await agent_manager.register_agent(req.id)

    from graph.heartbeat import heartbeat_runner
    await heartbeat_runner.add_agent(req.id)

    return {"status": "ok", "agent_id": req.id}


@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, req: AgentUpdateRequest):
    cfg = get_raw_config()
    agents_list = cfg.get("agents", {}).get("list", [])
    found = False
    for a in agents_list:
        if a["id"] == agent_id:
            if req.name is not None:
                a["name"] = req.name
            if req.description is not None:
                a["description"] = req.description
            if req.model is not None:
                a["model"] = req.model
            found = True
            break
    if not found:
        raise HTTPException(404, f"Agent '{agent_id}' 不存在")
    save_config(cfg)
    return {"status": "ok"}


@router.get("/agents/{agent_id}/heartbeat/config")
async def get_heartbeat_config_api(agent_id: str):
    """获取该 Agent 的心跳配置（enabled、every 等），供前端展示与开关"""
    if not any(a["id"] == agent_id for a in list_agents()):
        raise HTTPException(404, f"Agent '{agent_id}' 不存在")
    from config import get_heartbeat_config
    hb = get_heartbeat_config(agent_id)
    return {
        "enabled": bool(hb.get("enabled")),
        "every": hb.get("every", "30m"),
        "interval_seconds": hb.get("interval_seconds"),
    }


@router.get("/agents/{agent_id}/heartbeat/history")
async def get_heartbeat_history(agent_id: str, limit: int = 30):
    """获取该 Agent 最近的心跳事件列表（有界，用于右侧栏展示）"""
    if not any(a["id"] == agent_id for a in list_agents()):
        raise HTTPException(404, f"Agent '{agent_id}' 不存在")
    from graph.heartbeat import get_heartbeat_history as _get
    return _get(agent_id, limit=limit)


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, delete_files: bool = True):
    import shutil
    import time as _time
    from config import DATA_DIR

    if agent_id == "main":
        raise HTTPException(400, "不能删除默认 Agent 'main'")

    cfg = get_raw_config()
    agents_list = cfg.get("agents", {}).get("list", [])
    new_list = [a for a in agents_list if a["id"] != agent_id]
    if len(new_list) == len(agents_list):
        raise HTTPException(404, f"Agent '{agent_id}' 不存在")
    cfg["agents"]["list"] = new_list
    save_config(cfg)

    files_msg = "目录保留"
    if delete_files:
        agent_dir = resolve_agent_dir(agent_id)
        if agent_dir.exists():
            trash_dir = DATA_DIR / "trash"
            trash_dir.mkdir(parents=True, exist_ok=True)
            trash_dest = trash_dir / f"{agent_id}_{int(_time.time())}"
            try:
                shutil.move(str(agent_dir), str(trash_dest))
                files_msg = f"文件已移至回收站"
            except Exception:
                try:
                    shutil.rmtree(str(agent_dir))
                    files_msg = "文件已删除"
                except Exception:
                    files_msg = "文件清理失败"

    try:
        from graph.heartbeat import heartbeat_runner
        heartbeat_runner.update_config()
    except Exception:
        pass

    return {"status": "ok", "message": f"Agent '{agent_id}' 已删除（{files_msg}）"}


