"""实用工具 x1: session_status"""

from __future__ import annotations

import platform
from datetime import datetime

from langchain_core.tools import BaseTool
from pydantic import BaseModel

from config import resolve_agent_config


class SessionStatusTool(BaseTool):
    name: str = "session_status"
    description: str = "显示当前会话状态卡片：Agent ID、模型、系统时间、运行时信息。"
    args_schema: type[BaseModel] | None = None
    agent_id: str = "main"
    current_session_id: str = ""

    def _run(self, **kwargs) -> str:
        cfg = resolve_agent_config(self.agent_id)
        now = datetime.now()

        lines = [
            "📊 会话状态",
            f"  Agent: {self.agent_id}",
            f"  模型: {cfg.get('model', '未配置')}",
            f"  系统时间: {now.strftime('%Y-%m-%d %H:%M:%S')}",
            f"  时区: {cfg.get('user_timezone', '未设置')}",
            f"  操作系统: {platform.system()} {platform.release()} ({platform.machine()})",
            f"  Python: {platform.python_version()}",
        ]

        try:
            from graph.session_manager import session_manager
            from graph.subagent_registry import registry

            session_id = (
                self.current_session_id
                or session_manager.resolve_main_session_id(self.agent_id)
            )
            requester_key = session_manager.session_key_from_session_id(
                self.agent_id, session_id
            )
            active = registry.count_active_for_requester(requester_key)
            lines.append(f"  活跃子 Agent: {active}")
        except Exception:
            pass

        return "\n".join(lines)


def get_status_tools(agent_id: str, session_id: str = "") -> list[BaseTool]:
    from graph.session_manager import session_manager

    effective_session_id = (
        session_id or session_manager.resolve_main_session_id(agent_id)
    )
    return [
        SessionStatusTool(
            agent_id=agent_id,
            current_session_id=effective_session_id,
        ),
    ]
