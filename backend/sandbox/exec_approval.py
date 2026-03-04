"""工具 approval 策略检查 — exec / write / edit / delete / process_kill"""

from __future__ import annotations

import fnmatch
from typing import Literal

from config import get_exec_approval_config, get_config


# ---- 工具安全等级 ----

TOOL_RISK_LEVEL: dict[str, str] = {
    "read": "safe",
    "ls": "safe",
    "find": "safe",
    "grep": "safe",
    "web_search": "safe",
    "web_fetch": "safe",
    "memory_search": "safe",
    "memory_get": "safe",
    "session_status": "safe",
    "agents_list": "safe",
    "sessions_list": "safe",

    "write": "caution",
    "edit": "caution",
    "apply_patch": "caution",
    "python_repl": "caution",

    "exec": "danger",
    "process_kill": "danger",
    "delete": "danger",
}


def get_tool_risk_level(tool: str) -> str:
    return TOOL_RISK_LEVEL.get(tool, "caution")


def _first_token(command: str) -> str:
    """取命令的首个 token（程序名）"""
    cmd = (command or "").strip()
    if not cmd:
        return ""
    parts = cmd.split()
    return parts[0] if parts else ""


def _matches_allowlist(command: str, allowlist: list[str]) -> bool:
    """检查命令是否匹配 allowlist 中的任一模式（glob）"""
    first = _first_token(command)
    if not first:
        return False
    for pattern in allowlist:
        if not pattern or not isinstance(pattern, str):
            continue
        if fnmatch.fnmatch(first, pattern) or fnmatch.fnmatch(command, pattern):
            return True
    return False


def _get_sandbox_config() -> dict:
    cfg = get_config()
    defaults = {
        "mode": "soft",
        "snapshotBeforeExec": False,
        "undoStackSize": 50,
        "writeApproval": "on_overwrite",
    }
    sandbox = cfg.get("sandbox", {})
    return {**defaults, **sandbox}


def needs_exec_approval(agent_id: str, command: str) -> tuple[bool, str | None]:
    """
    判断 exec 命令是否需要用户确认。
    返回 (needs_approval, deny_reason)。
    """
    cfg = get_exec_approval_config()
    security = cfg.get("security", "allowlist")
    ask = cfg.get("ask", "on_miss")
    allowlist = cfg.get("allowlist") or []

    if security == "deny":
        return False, "exec 已被配置禁用 (security=deny)"

    if security == "full" and ask == "off":
        return False, None

    if security == "allowlist":
        if not _matches_allowlist(command, allowlist):
            if ask == "off":
                return False, "命令不在白名单中，已拒绝"
            return True, None
        if ask == "always":
            return True, None
        return False, None

    if ask == "always":
        return True, None
    return False, None


def needs_write_approval(
    agent_id: str, path: str, is_overwrite: bool
) -> tuple[bool, str | None]:
    """
    判断 write/edit 是否需要用户确认。
    覆盖已有文件时在 caution/danger 模式下需要确认。
    """
    sandbox = _get_sandbox_config()
    mode = sandbox.get("mode", "soft")
    if mode == "off":
        return False, None
    ask = sandbox.get("writeApproval", "on_overwrite")
    if ask == "off":
        return False, None
    if ask == "always":
        return True, None
    if ask == "on_overwrite" and is_overwrite:
        return True, None
    return False, None


def needs_dangerous_tool_approval(
    agent_id: str, tool: str, input_preview: str
) -> tuple[bool, str | None]:
    """
    判断工具是否需要用户确认。
    覆盖范围: exec, process_kill, write(覆盖), edit, delete
    """
    if tool == "exec":
        return needs_exec_approval(agent_id, input_preview)
    if tool == "process_kill":
        cfg = get_exec_approval_config()
        ask = cfg.get("ask", "off")
        if ask == "off":
            return False, None
        return True, None
    if tool in ("write", "edit", "delete"):
        is_overwrite = tool in ("write", "edit")
        return needs_write_approval(agent_id, input_preview, is_overwrite)
    return False, None
