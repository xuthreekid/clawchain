"""命令执行安全策略 — 黑名单、环境过滤"""

from __future__ import annotations

import os
import re

COMMAND_BLACKLIST = [
    r"rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+|.*)/\s*$",
    r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/",
    r"mkfs\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bhalt\b",
    r"\bpoweroff\b",
    r"dd\s+if=",
    r":\(\)\s*\{",
    r"chmod\s+-R\s+777\s+/",
    r"chown\s+-R\s+.*\s+/\s*$",
    r">\s*/dev/sd",
    r"\bsudo\s+rm\b",
    r"\bsudo\s+mkfs\b",
    r"\bsudo\s+dd\b",
]

_compiled = [re.compile(p) for p in COMMAND_BLACKLIST]

SENSITIVE_ENV_KEYS = {
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "API_KEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
}


def check_command(command: str) -> tuple[bool, str | None]:
    """
    检查命令是否安全。
    返回 (safe, reason)。safe=True 表示允许执行。
    """
    for pattern in _compiled:
        if pattern.search(command):
            return False, f"命令被安全策略拦截（匹配规则: {pattern.pattern}）"
    return True, None


def get_safe_env(extra_env: dict[str, str] | None = None) -> dict[str, str]:
    """构建安全的环境变量，过滤敏感信息"""
    env = {}
    for k, v in os.environ.items():
        if any(s in k.upper() for s in SENSITIVE_ENV_KEYS):
            continue
        env[k] = v
    if extra_env:
        env.update(extra_env)
    return env
