"""Chat command parser — slash commands with i18n support"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ParsedCommand:
    command: str
    args: list[str]
    raw: str
    is_command: bool = True


# ── i18n strings ──

_T: dict[str, dict[str, str]] = {
    "cmd_new":        {"zh": "重置会话（写入长期记忆，保持界面历史）", "en": "Reset session (flush long-term memory, keep UI history)"},
    "cmd_reset":      {"zh": "重置会话（不写入长期记忆，适合'丢弃本轮对话'）", "en": "Reset session (no memory flush, discard this conversation)"},
    "cmd_compact":    {"zh": "手动触发压缩（记忆刷新 + 压缩 + 启动上下文）", "en": "Manually trigger compaction (memory flush + compress + bootstrap)"},
    "cmd_help":       {"zh": "显示所有可用命令", "en": "Show all available commands"},
    "cmd_status":     {"zh": "显示当前 Agent 和会话状态", "en": "Show current Agent and session status"},
    "cmd_context":    {"zh": "显示当前上下文窗口使用情况", "en": "Show context window usage"},
    "cmd_usage":      {"zh": "显示 token 使用量和费用估算", "en": "Show token usage and cost estimates"},
    "cmd_stop":       {"zh": "停止当前生成", "en": "Stop current generation"},
    "cmd_think":      {"zh": "切换 thinking 模式（深度思考）", "en": "Toggle thinking mode (deep reasoning)"},
    "cmd_verbose":    {"zh": "切换 verbose 模式（详细输出）", "en": "Toggle verbose mode (detailed output)"},
    "cmd_reasoning":  {"zh": "切换 reasoning 模式（显示推理过程）", "en": "Toggle reasoning mode (show reasoning)"},
    "cmd_model":      {"zh": "查看或切换当前模型", "en": "View or switch current model"},
    "cmd_subagents":  {"zh": "列出当前子 Agent 状态", "en": "List current sub-agent status"},
    "cmd_whoami":     {"zh": "显示 Agent 身份信息", "en": "Show Agent identity info"},
    "help_title":     {"zh": "## 可用命令\n", "en": "## Available Commands\n"},
    "stopped":        {"zh": "已停止生成。", "en": "Generation stopped."},
    "unknown_cmd":    {"zh": "未知命令: {cmd}", "en": "Unknown command: {cmd}"},
    "no_session":     {"zh": "无活跃会话。", "en": "No active session."},
    "state_unavail":  {"zh": "Agent 状态不可用。", "en": "Agent state unavailable."},
    "compaction_count": {"zh": "本轮压缩次数", "en": "Compactions this turn"},
    "on":             {"zh": "开启", "en": "ON"},
    "off":            {"zh": "关闭", "en": "OFF"},
    "yes":            {"zh": "是", "en": "Yes"},
    "no":             {"zh": "否", "en": "No"},
    "status_title":   {"zh": "## Agent 状态\n", "en": "## Agent Status\n"},
    "msg_count":      {"zh": "消息数", "en": "Messages"},
    "token_est":      {"zh": "Token 估算", "en": "Est. Tokens"},
    "compressed":     {"zh": "已压缩", "en": "Compressed"},
    "ctx_title":      {"zh": "## 上下文窗口\n", "en": "## Context Window\n"},
    "msg_tokens":     {"zh": "消息 tokens", "en": "Message tokens"},
    "ctx_compressed": {"zh": "压缩上下文", "en": "Compressed context"},
    "ctx_total":      {"zh": "合计", "en": "Total"},
    "usage_title":    {"zh": "## Token 使用统计\n", "en": "## Token Usage\n"},
    "model_label":    {"zh": "模型", "en": "Model"},
    "input_label":    {"zh": "输入", "en": "Input"},
    "output_label":   {"zh": "输出", "en": "Output"},
    "cache_read":     {"zh": "缓存读取", "en": "Cache read"},
    "total_label":    {"zh": "总计", "en": "Total"},
    "turns_label":    {"zh": "回合数", "en": "Turns"},
    "thinking_mode":  {"zh": "Thinking 模式: **{name}**", "en": "Thinking mode: **{name}**"},
    "setting_toggled": {"zh": "{setting} 模式已{status}。", "en": "{setting} mode is now {status}."},
    "current_model":  {"zh": "## 当前模型\n", "en": "## Current Model\n"},
    "available_models": {"zh": "## 可用模型\n", "en": "## Available Models\n"},
    "switch_hint":    {"zh": "使用 `/model provider/model` 切换模型。", "en": "Use `/model provider/model` to switch models."},
    "model_switched": {"zh": "模型已切换到: **{name}** (`{target}`)", "en": "Model switched to: **{name}** (`{target}`)"},
    "model_failed":   {"zh": "模型切换失败: {err}", "en": "Model switch failed: {err}"},
    "no_subagents":   {"zh": "暂无活跃的子 Agent。", "en": "No active sub-agents."},
    "subagent_list":  {"zh": "## 子 Agent 列表\n", "en": "## Sub-Agent List\n"},
    "running":        {"zh": "🟢 运行中", "en": "🟢 Running"},
    "task_label":     {"zh": "任务", "en": "Task"},
    "identity_title": {"zh": "## 身份信息\n", "en": "## Identity\n"},
    "name_label":     {"zh": "名称", "en": "Name"},
    "unnamed":        {"zh": "未命名", "en": "Unnamed"},
    "api_protocol":   {"zh": "API 协议", "en": "API Protocol"},
    "workspace_label": {"zh": "工作区", "en": "Workspace"},
    "chat_queued":      {"zh": "Agent 正在处理中，消息已排队（第 {pos} 条）", "en": "Agent is busy, message queued (position {pos})"},
    "chat_queued_done": {"zh": "[消息已排队，等待处理]", "en": "[Message queued, waiting for processing]"},
    "title_gen_system": {"zh": "你是一个标题生成器。根据用户的第一条消息，生成一个不超过10个字的中文标题。只输出标题，不要任何解释或标点。", "en": "You are a title generator. Based on the user's first message, generate a title of no more than 6 words. Output only the title, no explanation or punctuation."},
}

COMMAND_KEYS = [
    "/new", "/reset", "/compact", "/help", "/status", "/context",
    "/usage", "/stop", "/think", "/verbose", "/reasoning",
    "/model", "/subagents", "/whoami",
]

_CMD_KEY_MAP = {
    "/new": "cmd_new", "/reset": "cmd_reset", "/compact": "cmd_compact",
    "/help": "cmd_help", "/status": "cmd_status", "/context": "cmd_context",
    "/usage": "cmd_usage", "/stop": "cmd_stop", "/think": "cmd_think",
    "/verbose": "cmd_verbose", "/reasoning": "cmd_reasoning",
    "/model": "cmd_model", "/subagents": "cmd_subagents",
    "/whoami": "cmd_whoami",
}


def t(key: str, locale: str = "zh-CN", **kwargs: str) -> str:
    lang = "zh" if locale.startswith("zh") else "en"
    s = _T.get(key, {}).get(lang, _T.get(key, {}).get("en", key))
    return s.format(**kwargs) if kwargs else s


def _get_commands(locale: str) -> dict[str, str]:
    return {cmd: t(k, locale) for cmd, k in _CMD_KEY_MAP.items()}


# Keep backwards-compat: default COMMANDS dict
COMMANDS = _get_commands("zh-CN")


def parse_command(text: str) -> ParsedCommand | None:
    """Parse user input, recognise slash commands. Return None for non-commands."""
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None

    parts = stripped.split(None, 1)
    cmd = parts[0].lower()

    if cmd not in _CMD_KEY_MAP:
        return None

    args = parts[1].split() if len(parts) > 1 else []
    return ParsedCommand(command=cmd, args=args, raw=stripped)


def format_help(locale: str = "zh-CN") -> str:
    lines = [t("help_title", locale)]
    for cmd, desc in _get_commands(locale).items():
        lines.append(f"- `{cmd}` — {desc}")
    return "\n".join(lines)


async def execute_command(
    parsed: ParsedCommand,
    agent_id: str,
    session_id: str,
    agent_state: Any = None,
    locale: str = "zh-CN",
) -> dict[str, Any]:
    """Execute a command and return result dict."""
    cmd = parsed.command

    if cmd == "/help":
        return {"handled": True, "response": format_help(locale), "action": "info"}

    if cmd == "/status":
        return await _cmd_status(agent_id, session_id, agent_state, locale)

    if cmd == "/context":
        return await _cmd_context(agent_id, session_id, locale)

    if cmd == "/usage":
        return _cmd_usage(agent_id, session_id, locale)

    if cmd == "/new":
        model_override = parsed.args[0] if parsed.args else None
        return {"handled": True, "response": "", "action": "reset", "model_override": model_override}

    if cmd == "/reset":
        return {"handled": True, "response": "", "action": "reset_noflush"}

    if cmd == "/compact":
        return {"handled": True, "response": "", "action": "compact"}

    if cmd == "/stop":
        return {"handled": True, "response": t("stopped", locale), "action": "stop"}

    if cmd == "/think":
        return _cmd_think(agent_state, parsed.args, locale)

    if cmd == "/verbose":
        return _cmd_toggle_setting(agent_state, "verbose", parsed.args, locale)

    if cmd == "/reasoning":
        return _cmd_toggle_setting(agent_state, "reasoning", parsed.args, locale)

    if cmd == "/model":
        return _cmd_model(agent_id, parsed.args, locale)

    if cmd == "/subagents":
        return _cmd_subagents(agent_id, session_id, locale)

    if cmd == "/whoami":
        return _cmd_whoami(agent_id, locale)

    return {"handled": False, "response": t("unknown_cmd", locale, cmd=cmd), "action": "none"}


async def _cmd_status(agent_id: str, session_id: str, agent_state: Any, locale: str) -> dict[str, Any]:
    from graph.session_manager import session_manager
    from graph.token_counter import count_messages_tokens

    data = session_manager.load_session(session_id, agent_id)
    msg_count = len(data.get("messages", [])) if data else 0
    tokens = count_messages_tokens(data.get("messages", [])) if data else 0
    has_compressed = bool(data.get("compressed_context")) if data else False

    state_info = ""
    if agent_state:
        on = t("on", locale)
        off = t("off", locale)
        state_info = (
            f"\n- {t('compaction_count', locale)}: {getattr(agent_state, 'compaction_count', 0)}"
            f"\n- Thinking: {on if getattr(agent_state, 'thinking', False) else off}"
            f"\n- Verbose: {on if getattr(agent_state, 'verbose', False) else off}"
        )

    yes = t("yes", locale)
    no = t("no", locale)
    response = (
        f"{t('status_title', locale)}"
        f"- Agent: {agent_id}\n"
        f"- Session: {session_id}\n"
        f"- {t('msg_count', locale)}: {msg_count}\n"
        f"- {t('token_est', locale)}: {tokens:,}\n"
        f"- {t('compressed', locale)}: {yes if has_compressed else no}"
        f"{state_info}"
    )
    return {"handled": True, "response": response, "action": "info"}


async def _cmd_context(agent_id: str, session_id: str, locale: str) -> dict[str, Any]:
    from graph.session_manager import session_manager
    from graph.token_counter import count_messages_tokens, count_tokens, DEFAULT_COMPACTION_THRESHOLD

    data = session_manager.load_session(session_id, agent_id)
    if not data:
        return {"handled": True, "response": t("no_session", locale), "action": "info"}

    messages = data.get("messages", [])
    msg_tokens = count_messages_tokens(messages)
    compressed = data.get("compressed_context", "")
    ctx_tokens = count_tokens(compressed) if compressed else 0
    total = msg_tokens + ctx_tokens
    pct = int(total / DEFAULT_COMPACTION_THRESHOLD * 100)

    bar_len = 30
    filled = min(int(bar_len * pct / 100), bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)

    response = (
        f"{t('ctx_title', locale)}"
        f"```\n"
        f"[{bar}] {pct}%\n"
        f"```\n"
        f"- {t('msg_tokens', locale)}: {msg_tokens:,}\n"
        f"- {t('ctx_compressed', locale)}: {ctx_tokens:,}\n"
        f"- **{t('ctx_total', locale)}: {total:,} / {DEFAULT_COMPACTION_THRESHOLD:,}**\n"
        f"- {t('msg_count', locale)}: {len(messages)}"
    )
    return {"handled": True, "response": response, "action": "info"}


def _cmd_usage(agent_id: str, session_id: str, locale: str) -> dict[str, Any]:
    from graph.run_tracker import run_tracker
    from graph.model_selection import resolve_agent_model, get_model_display_name

    model_ref = resolve_agent_model(agent_id)
    model_name = get_model_display_name(model_ref)

    usage = run_tracker.get_cumulative_usage(agent_id, session_id)

    response = (
        f"{t('usage_title', locale)}"
        f"- {t('model_label', locale)}: `{model_ref}` ({model_name})\n"
        f"- {t('input_label', locale)}: {usage['input_tokens']:,}\n"
        f"- {t('output_label', locale)}: {usage['output_tokens']:,}\n"
        f"- {t('cache_read', locale)}: {usage['cache_read_tokens']:,}\n"
        f"- {t('total_label', locale)}: {usage['total_tokens']:,}\n"
        f"- {t('turns_label', locale)}: {usage['turns']}"
    )
    return {"handled": True, "response": response, "action": "info"}


def _cmd_think(agent_state: Any, args: list[str], locale: str) -> dict[str, Any]:
    if agent_state is None:
        return {"handled": True, "response": t("state_unavail", locale), "action": "info"}

    from graph.thinking import (
        ThinkLevel, parse_think_level, think_level_name,
        cycle_think_level, THINK_LEVELS,
    )

    current = ThinkLevel(getattr(agent_state, "think_level", 0))

    if args:
        new_level = parse_think_level(args[0])
    else:
        new_level = cycle_think_level(current)

    agent_state.think_level = new_level.value
    name = think_level_name(new_level)
    levels_str = " → ".join(
        f"**{l}**" if l == name else l for l in THINK_LEVELS
    )
    response = f"{t('thinking_mode', locale, name=name)}\n\n{levels_str}"
    return {"handled": True, "response": response, "action": "setting"}


def _cmd_toggle_setting(agent_state: Any, setting: str, args: list[str], locale: str) -> dict[str, Any]:
    if agent_state is None:
        return {"handled": True, "response": t("state_unavail", locale), "action": "info"}

    current = getattr(agent_state, setting, False)

    if args:
        val = args[0].lower()
        new_val = val in ("on", "true", "1", "是")
    else:
        new_val = not current

    setattr(agent_state, setting, new_val)
    status = t("on", locale) if new_val else t("off", locale)
    response = t("setting_toggled", locale, setting=setting, status=status)
    return {"handled": True, "response": response, "action": "setting"}


def _cmd_model(agent_id: str, args: list[str], locale: str) -> dict[str, Any]:
    from graph.model_selection import resolve_agent_model, get_model_display_name
    from graph.models_config import models_config

    current_ref = resolve_agent_model(agent_id)
    current_name = get_model_display_name(current_ref)

    if not args:
        catalog = models_config.list_all_models()
        lines = [
            f"{t('current_model', locale)}`{current_ref}` ({current_name})\n",
            f"{t('available_models', locale)}",
        ]
        for entry in catalog:
            marker = " **<-**" if entry.provider == current_ref.provider and entry.id == current_ref.model else ""
            caps = []
            if entry.reasoning:
                caps.append("reasoning")
            if entry.input and "image" in entry.input:
                caps.append("vision")
            cap_str = f" [{', '.join(caps)}]" if caps else ""
            lines.append(f"- `{entry.provider}/{entry.id}` — {entry.name}{cap_str}{marker}")

        lines.append(f"\n{t('switch_hint', locale)}")
        return {"handled": True, "response": "\n".join(lines), "action": "info"}

    target = args[0]
    try:
        from graph.agent import agent_manager
        new_name = agent_manager.switch_model(agent_id, target)
        return {
            "handled": True,
            "response": t("model_switched", locale, name=new_name, target=target),
            "action": "setting",
        }
    except Exception as e:
        return {
            "handled": True,
            "response": t("model_failed", locale, err=str(e)),
            "action": "info",
        }


def _cmd_subagents(agent_id: str, session_id: str, locale: str) -> dict[str, Any]:
    from graph.session_manager import session_manager
    from graph.subagent_registry import registry

    requester_key = session_manager.session_key_from_session_id(agent_id, session_id)
    runs = registry.list_runs_for_requester(requester_key)

    if not runs:
        return {"handled": True, "response": t("no_subagents", locale), "action": "info"}

    lines = [t("subagent_list", locale)]
    for r in runs:
        import time
        status = t("running", locale) if r.ended_at is None else f"⚪ {r.outcome}"
        elapsed = ""
        if r.started_at and not r.ended_at:
            elapsed = f" ({int(time.time() - r.started_at)}s)"
        lines.append(
            f"- **{r.label or r.run_id}** | agent:{r.target_agent_id} | {status}{elapsed}"
            f"\n  {t('task_label', locale)}: {r.task[:100]}"
        )

    return {"handled": True, "response": "\n".join(lines), "action": "info"}


def _cmd_whoami(agent_id: str, locale: str) -> dict[str, Any]:
    from config import resolve_agent_config, resolve_agent_workspace
    from graph.model_selection import resolve_agent_model, get_model_display_name
    from graph.models_config import models_config

    cfg = resolve_agent_config(agent_id)
    workspace = resolve_agent_workspace(agent_id)
    model_ref = resolve_agent_model(agent_id)
    model_name = get_model_display_name(model_ref)
    api_protocol = models_config.resolve_api_protocol(model_ref)

    identity_path = workspace / "IDENTITY.md"
    identity = ""
    if identity_path.exists():
        identity = identity_path.read_text(encoding="utf-8")[:500]

    response = (
        f"{t('identity_title', locale)}"
        f"- Agent ID: `{agent_id}`\n"
        f"- {t('name_label', locale)}: {cfg.get('name', t('unnamed', locale))}\n"
        f"- {t('model_label', locale)}: `{model_ref}` ({model_name})\n"
        f"- {t('api_protocol', locale)}: {api_protocol}\n"
        f"- {t('workspace_label', locale)}: `{workspace}`\n\n"
        f"{identity}"
    )
    return {"handled": True, "response": response, "action": "info"}
