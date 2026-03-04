"""沙箱安全系统"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SandboxPolicy:
    """沙箱策略配置"""
    root_dir: str
    workspace_only: bool = True
    command_blacklist: list[str] = field(default_factory=lambda: [
        r"rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+|.*)/\s*$",
        r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/",
        r"mkfs",
        r"shutdown",
        r"reboot",
        r"halt",
        r"poweroff",
        r"dd\s+if=",
        r":\(\)\s*\{\s*:\|\:&\s*\}\s*;",
        r"chmod\s+-R\s+777\s+/",
        r"chown\s+-R\s+.*\s+/",
        r">\s*/dev/sd",
        r"mv\s+.*\s+/dev/null",
    ])
    max_output_chars: int = 5000
    exec_timeout: int = 30
