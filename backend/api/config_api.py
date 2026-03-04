"""配置管理 API — GET/PUT /api/config, 模型目录 API, Secrets API"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Any

import copy

from config import get_config, get_raw_config, save_config, get_config_path, is_initialized, resolve_chat_timeout_seconds
from config_schema import validate_config, sanitize_config_for_client, SENSITIVE_KEYS

router = APIRouter()


class ConfigUpdateRequest(BaseModel):
    updates: dict[str, Any]


class ConfigReplaceRequest(BaseModel):
    config: dict[str, Any]


class ToolPolicyUpdateRequest(BaseModel):
    agent_id: str
    tool_name: str
    allowed: bool


class SecretsUpdateRequest(BaseModel):
    path: str
    value: str


TOOLS_CATALOG = [
    "read", "write", "edit", "apply_patch", "grep", "find", "ls",
    "exec", "python_repl", "process_list", "process_kill",
    "web_search", "web_fetch",
    "memory_search", "memory_get", "search_knowledge_base",
    "agents_list",
    "sessions_list", "sessions_history", "sessions_send", "sessions_spawn", "subagents",
    "cron",
    "session_status",
]


@router.get("/config")
async def get_full_config():
    """Return sanitized configuration (sensitive fields masked)"""
    cfg = get_config()
    return sanitize_config_for_client(cfg)


@router.get("/config/raw")
async def get_raw_config_endpoint(request: Request):
    """Return full raw configuration (for JSON editor, includes secrets)"""
    allow_remote = os.getenv("CLAWCHAIN_ALLOW_REMOTE_RAW_CONFIG", "").strip().lower() in ("1", "true", "yes")
    client_host = (request.client.host if request.client else "") or ""
    if not allow_remote and client_host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, detail="Raw config access is restricted to localhost")
    return get_raw_config()


@router.get("/tools/catalog")
async def get_tools_catalog():
    return {"tools": TOOLS_CATALOG}


@router.get("/config/path")
async def get_config_file_path():
    return {"path": get_config_path()}


@router.get("/config/chat")
async def get_chat_config():
    """返回聊天相关配置（超时等），供前端请求时使用"""
    return {"timeoutSeconds": resolve_chat_timeout_seconds()}


@router.get("/init/status")
async def get_init_status():
    """初始化状态：支持前端首次引导页判断"""
    file_initialized = is_initialized()
    cfg = get_raw_config()

    providers = (cfg.get("models", {}).get("providers") or {})
    valid_provider_count = 0
    for p in providers.values():
        if not isinstance(p, dict):
            continue
        has_base_url = bool((p.get("baseUrl") or "").strip())
        has_models = bool(p.get("models"))
        if has_base_url and has_models:
            valid_provider_count += 1

    default_model = (cfg.get("agents", {}).get("defaults", {}).get("model") or "").strip()
    config_ready = valid_provider_count > 0 and bool(default_model)

    missing: list[str] = []
    if not providers:
        missing.append("models.providers")
    elif valid_provider_count == 0:
        missing.append("models.providers[*].baseUrl/models")
    if not default_model:
        missing.append("agents.defaults.model")

    return {
        "file_initialized": file_initialized,
        "config_ready": config_ready,
        "providers_count": len(providers),
        "valid_providers_count": valid_provider_count,
        "default_model": default_model or None,
        "missing": missing,
    }


@router.put("/config")
async def update_config(req: ConfigUpdateRequest):
    """Deep-merge updates into current config and save"""
    cfg = get_raw_config()
    _deep_merge_inplace(cfg, req.updates)

    result = validate_config(cfg)
    if not result.ok:
        raise HTTPException(400, detail=f"配置校验失败: {'; '.join(result.errors)}")

    save_config(cfg)
    _reload_subsystems(req.updates)

    return {"status": "ok", "config": sanitize_config_for_client(cfg)}


@router.put("/config/tools-policy")
async def update_tool_policy(req: ToolPolicyUpdateRequest):
    from config import get_raw_config, save_config
    cfg = get_raw_config()
    agents_list = cfg.setdefault("agents", {}).setdefault("list", [])
    agent_entry = next((a for a in agents_list if a.get("id") == req.agent_id), None)
    if not agent_entry:
        raise HTTPException(404, f"Agent '{req.agent_id}' 不存在")
    defaults = cfg.get("agents", {}).get("defaults", {})
    tools_defaults = defaults.get("tools") or {}
    tools_agent = agent_entry.get("tools") or {}
    deny = list(tools_agent.get("deny") or tools_defaults.get("deny") or [])
    allow = list(tools_agent.get("allow") or tools_defaults.get("allow") or [])

    def _norm(n: str) -> str:
        return n.replace("-", "_").lower().strip()

    name_norm = _norm(req.tool_name)
    allow_set = {_norm(a) for a in allow if a} if allow else None

    if req.allowed:
        deny = [x for x in deny if _norm(x) != name_norm]
        if allow_set is not None and name_norm not in allow_set:
            allow = allow + [req.tool_name]
    else:
        if name_norm not in {_norm(d) for d in deny if d}:
            deny = deny + [req.tool_name]
        if allow_set is not None and name_norm in allow_set:
            allow = [x for x in allow if _norm(x) != name_norm]

    agent_entry.setdefault("tools", {})
    agent_entry["tools"]["deny"] = deny if deny else None
    agent_entry["tools"]["allow"] = allow if allow else None
    agent_entry["tools"] = {k: v for k, v in agent_entry["tools"].items() if v is not None}
    if not agent_entry["tools"]:
        del agent_entry["tools"]
    save_config(cfg)
    try:
        from graph.heartbeat import heartbeat_runner
        heartbeat_runner.update_config()
    except Exception:
        pass
    return {"status": "ok", "config": sanitize_config_for_client(get_config())}


@router.put("/config/replace")
async def replace_config(req: ConfigReplaceRequest):
    """完整替换配置（Raw JSON 编辑器使用），带校验。"""
    merged = _restore_masked_secrets(req.config, get_raw_config())

    result = validate_config(merged)
    if not result.ok:
        raise HTTPException(400, detail=f"配置校验失败: {'; '.join(result.errors)}")

    save_config(merged)
    _reload_subsystems(merged)
    return {"status": "ok", "config": sanitize_config_for_client(get_config())}


@router.put("/config/secrets")
async def update_secrets(req: SecretsUpdateRequest):
    """写入敏感字段（如 apiKey），不走脱敏返回"""
    cfg = get_raw_config()
    parts = req.path.split(".")
    current = cfg
    for p in parts[:-1]:
        if isinstance(current, dict):
            current = current.setdefault(p, {})
        else:
            raise HTTPException(400, f"Invalid path: {req.path}")
    if isinstance(current, dict):
        current[parts[-1]] = req.value
    else:
        raise HTTPException(400, f"Invalid path: {req.path}")

    save_config(cfg)
    _reload_subsystems({"models": True})
    return {"status": "ok", "path": req.path}


@router.get("/models")
async def list_models():
    from graph.models_config import models_config

    providers = []
    for p in models_config.list_providers():
        providers.append({
            "id": p.id,
            "api": p.api,
            "models": [
                {
                    "id": m.id,
                    "name": m.name,
                    "reasoning": m.reasoning,
                    "input": m.input,
                    "contextWindow": m.context_window,
                    "maxTokens": m.max_tokens,
                    "cost": m.cost,
                }
                for m in p.models
            ],
        })

    catalog = [
        {
            "id": e.id,
            "name": e.name,
            "provider": e.provider,
            "reasoning": e.reasoning,
            "input": e.input,
            "contextWindow": e.context_window,
        }
        for e in models_config.list_all_models()
    ]

    return {"providers": providers, "catalog": catalog}


@router.get("/models/current/{agent_id}")
async def get_current_model(agent_id: str):
    from graph.model_selection import resolve_agent_model, get_model_display_name
    from graph.models_config import models_config

    try:
        ref = resolve_agent_model(agent_id)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    model_def = models_config.get_model(ref)

    return {
        "provider": ref.provider,
        "model": ref.model,
        "ref": str(ref),
        "name": get_model_display_name(ref),
        "reasoning": model_def.reasoning if model_def else False,
        "input": model_def.input if model_def else ["text"],
        "contextWindow": model_def.context_window if model_def else 128000,
        "maxTokens": model_def.max_tokens if model_def else 8192,
        "api": models_config.resolve_api_protocol(ref),
    }


class ModelSwitchRequest(BaseModel):
    model: str
    scope: str = "agent"


@router.post("/models/switch/{agent_id}")
async def switch_model(agent_id: str, req: ModelSwitchRequest):
    """运行时切换模型。scope='agent' 仅改该 agent；scope='default' 改全局默认。"""
    from graph.agent import agent_manager
    from config import get_raw_config, save_config

    try:
        new_name = agent_manager.switch_model(agent_id, req.model)

        cfg = get_raw_config()
        if req.scope == "default":
            cfg.setdefault("agents", {}).setdefault("defaults", {})["model"] = req.model
        else:
            agents_list = cfg.get("agents", {}).get("list", [])
            for a in agents_list:
                if a.get("id") == agent_id:
                    a["model"] = req.model
                    break
            else:
                cfg.setdefault("agents", {}).setdefault("defaults", {})["model"] = req.model

        save_config(cfg)

        return {"status": "ok", "model": req.model, "name": new_name, "scope": req.scope}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_masked(v: Any) -> bool:
    """检测值是否为脱敏后的占位符（包含 ***）"""
    return isinstance(v, str) and "***" in v


def _restore_masked_secrets(incoming: dict, existing: dict, depth: int = 0) -> dict:
    """将提交配置中的脱敏值还原为现有配置中的真实值，防止覆盖。"""
    if depth > 10:
        return incoming
    result = copy.deepcopy(incoming)
    for k, v in result.items():
        k_lower = k.lower().replace("-", "").replace("_", "")
        is_sensitive = any(
            sk.lower().replace("-", "").replace("_", "") == k_lower
            for sk in SENSITIVE_KEYS
        )
        if is_sensitive and _is_masked(v):
            if k in existing:
                result[k] = existing[k]
        elif isinstance(v, dict) and isinstance(existing.get(k), dict):
            result[k] = _restore_masked_secrets(v, existing[k], depth + 1)
        elif isinstance(v, list):
            ex_list = existing.get(k, [])
            if isinstance(ex_list, list):
                result[k] = [
                    _restore_masked_secrets(item, ex_list[i], depth + 1)
                    if isinstance(item, dict) and i < len(ex_list) and isinstance(ex_list[i], dict)
                    else item
                    for i, item in enumerate(v)
                ]
    return result


def _deep_merge_inplace(base: dict, override: dict) -> None:
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge_inplace(base[k], v)
        else:
            base[k] = v


def _reload_subsystems(updates: dict[str, Any]) -> None:
    if "models" in updates:
        try:
            from graph.models_config import models_config
            from graph.llm_factory import llm_cache
            from config import get_config
            models_config.reload(get_config().get("models"))
            llm_cache.invalidate_all()
        except Exception:
            pass

    if "agents" in updates:
        try:
            from graph.heartbeat import heartbeat_runner
            heartbeat_runner.update_config()
        except Exception:
            pass
