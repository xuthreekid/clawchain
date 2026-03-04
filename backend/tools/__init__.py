"""工具注册工厂"""

from __future__ import annotations


def get_all_tools(agent_id: str, agent_manager: object | None = None, session_id: str = "") -> list:
    """为指定 Agent 构建完整工具集"""
    from config import resolve_agent_workspace, resolve_agent_dir

    workspace = str(resolve_agent_workspace(agent_id))
    agent_dir = str(resolve_agent_dir(agent_id))

    from tools.file_tools import get_file_tools
    from tools.exec_tools import get_exec_tools
    from tools.web_tools import get_web_tools
    from tools.memory_tools import get_memory_tools
    from tools.knowledge_tool import get_knowledge_tools
    from tools.agent_tools import get_agent_tools
    from tools.status_tool import get_status_tools
    from tools.cron_tools import get_cron_tools

    tools: list = []
    tools.extend(get_file_tools(workspace, agent_id=agent_id))
    tools.extend(get_exec_tools(workspace, agent_id=agent_id))
    tools.extend(get_web_tools())
    tools.extend(get_memory_tools(agent_dir))
    tools.extend(get_knowledge_tools(agent_dir))
    tools.extend(get_agent_tools(agent_id, agent_manager, session_id))
    tools.extend(get_cron_tools(agent_id))
    tools.extend(get_status_tools(agent_id, session_id))

    return tools
