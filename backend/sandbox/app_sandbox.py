"""App Sandbox 设计 — 面向普通用户的工作区隔离

为桌面 App 模式设计的工作区沙箱策略:
1. 用户友好的目录结构 (~/ClawChain/)
2. 严格的路径边界控制
3. 文件授权机制 (通过 macOS File Dialog 授权额外目录)
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any

_AUTHORIZED_DIRS: set[str] = set()
_AUTH_FILE: Path | None = None


def get_app_workspace_root() -> Path:
    """获取 App 模式下的工作区根目录 (~/ClawChain/)"""
    if platform.system() == "Darwin":
        return Path.home() / "ClawChain"
    elif platform.system() == "Windows":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ClawChain"
    else:
        return Path.home() / ".clawchain"


def ensure_app_workspace() -> dict[str, Path]:
    """确保 App 工作区目录结构存在，返回各目录路径"""
    root = get_app_workspace_root()
    dirs = {
        "root": root,
        "documents": root / "Documents",
        "downloads": root / "Downloads",
        "skills": root / "Skills",
        "system": root / ".clawchain",
        "config": root / ".clawchain" / "config.json",
        "sessions": root / ".clawchain" / "sessions",
        "memory": root / ".clawchain" / "memory",
        "knowledge": root / ".clawchain" / "knowledge",
        "logs": root / ".clawchain" / "logs",
        "backups": root / ".clawchain" / "backups",
    }
    for key, path in dirs.items():
        if key == "config":
            continue
        path.mkdir(parents=True, exist_ok=True)

    return dirs


def load_authorized_dirs() -> set[str]:
    """加载用户授权的额外目录列表"""
    global _AUTHORIZED_DIRS, _AUTH_FILE
    root = get_app_workspace_root()
    _AUTH_FILE = root / ".clawchain" / "authorized_dirs.json"
    if _AUTH_FILE.exists():
        try:
            with open(_AUTH_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _AUTHORIZED_DIRS = set(data.get("dirs", []))
        except Exception:
            _AUTHORIZED_DIRS = set()
    return _AUTHORIZED_DIRS


def authorize_directory(dir_path: str) -> bool:
    """授权一个额外的目录（通过文件选择器选择后调用）"""
    global _AUTHORIZED_DIRS
    abs_path = str(Path(dir_path).resolve())
    _AUTHORIZED_DIRS.add(abs_path)
    _save_authorized_dirs()
    return True


def revoke_directory(dir_path: str) -> bool:
    """取消目录授权"""
    global _AUTHORIZED_DIRS
    abs_path = str(Path(dir_path).resolve())
    _AUTHORIZED_DIRS.discard(abs_path)
    _save_authorized_dirs()
    return True


def _save_authorized_dirs() -> None:
    if _AUTH_FILE:
        _AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump({"dirs": sorted(_AUTHORIZED_DIRS)}, f, ensure_ascii=False, indent=2)


def is_path_allowed(path: str | Path) -> bool:
    """检查路径是否在允许的范围内（工作区 + 授权目录）"""
    target = Path(path).resolve()
    target_str = str(target)

    root = get_app_workspace_root()
    root_str = str(root.resolve())
    if target_str.startswith(root_str):
        return True

    for auth_dir in _AUTHORIZED_DIRS:
        if target_str.startswith(auth_dir):
            return True

    return False


def get_sandbox_entitlements() -> dict[str, Any]:
    """返回当前 App Sandbox 的权限描述（用于 macOS entitlements）"""
    return {
        "com.apple.security.app-sandbox": True,
        "com.apple.security.network.client": True,
        "com.apple.security.files.user-selected.read-write": True,
        "com.apple.security.files.bookmarks.app-scope": True,
        "com.apple.security.automation.apple-events": True,
    }


def generate_entitlements_plist() -> str:
    """生成 macOS entitlements plist 内容"""
    entitlements = get_sandbox_entitlements()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
             '<plist version="1.0">',
             '<dict>']
    for key, val in entitlements.items():
        lines.append(f'    <key>{key}</key>')
        if isinstance(val, bool):
            lines.append(f'    <{"true" if val else "false"}/>')
        else:
            lines.append(f'    <string>{val}</string>')
    lines.extend(['</dict>', '</plist>'])
    return "\n".join(lines)
