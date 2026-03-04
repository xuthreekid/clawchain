"""System Prompt 构建器

支持 full / minimal / none 三种模式，统一参数对象 PromptParams，
可选生成 PromptReport（字符统计、文件截断、工具摘要）。
"""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from config import (
    get_heartbeat_config,
    resolve_agent_config,
    resolve_agent_dir,
    resolve_agent_workspace,
    resolve_agent_memory_dir,
    get_rag_mode,
)

MAX_FILE_CHARS = 20_000
MAX_TOTAL_CHARS = 80_000

SILENT_REPLY_TOKEN = "NO_REPLY"


# ---------------------------------------------------------------------------
# Prompt Report
# ---------------------------------------------------------------------------

@dataclass
class PromptFileEntry:
    label: str
    chars: int
    truncated: bool


@dataclass
class PromptReport:
    mode: str
    total_chars: int
    sections: list[str]
    injected_files: list[PromptFileEntry]
    tool_count: int
    tool_names: list[str]
    truncation_events: int

    def summary(self) -> str:
        lines = [
            f"[PromptReport] mode={self.mode} total_chars={self.total_chars} "
            f"sections={len(self.sections)} tools={self.tool_count} "
            f"files={len(self.injected_files)} truncations={self.truncation_events}",
        ]
        for f in self.injected_files:
            tag = " [TRUNCATED]" if f.truncated else ""
            lines.append(f"  file: {f.label} ({f.chars} chars){tag}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt Params
# ---------------------------------------------------------------------------

@dataclass
class PromptParams:
    agent_id: str
    mode: Literal["full", "minimal", "none"] = "full"
    available_tools: list[str] | None = None
    extra_system_prompt: str | None = None
    default_think_level: str = "off"
    max_file_chars: int = MAX_FILE_CHARS
    max_total_chars: int = MAX_TOTAL_CHARS
    locale: str = "zh-CN"
    heartbeat_prompt: str | None = None


# ---------------------------------------------------------------------------
# Bilingual prompt snippets
# ---------------------------------------------------------------------------

_PROMPT_TEXT: dict[str, dict[str, str]] = {
    "identity": {
        "zh-CN": "你是一个运行在 ClawChain 中的个人助手。",
        "en-US": "You are a personal assistant running in ClawChain.",
    },
    "tool_header": {
        "zh-CN": "## 可用工具\n\n工具可用性（受策略过滤）；分层：core=核心, skill=技能, external=外部服务\n工具名称区分大小写，请严格按照以下名称调用：",
        "en-US": "## Available Tools\n\nTool availability (policy-filtered); layers: core, skill, external\nTool names are case-sensitive. Call them exactly as listed:",
    },
    "tool_footer": {
        "zh-CN": "TOOLS.md 不控制工具可用性；它是用户对外部工具使用方式的指导。",
        "en-US": "TOOLS.md does not control tool availability; it is user guidance for external tool usage.",
    },
    "respond_lang": {
        "zh-CN": "始终使用中文回复用户（除非用户明确要求其他语言）。",
        "en-US": "Always respond in the same language the user writes in.",
    },
}


def _pt(key: str, locale: str) -> str:
    entry = _PROMPT_TEXT.get(key, {})
    return entry.get(locale, entry.get("zh-CN", ""))


# ---------------------------------------------------------------------------
# PromptBuilder
# ---------------------------------------------------------------------------

class PromptBuilder:

    MINIMAL_BOOTSTRAP_ALLOWLIST = {"SOUL.md", "IDENTITY.md", "USER.md", "AGENTS.md", "TOOLS.md"}

    def build_system_prompt(
        self,
        agent_id: str,
        mode: Literal["full", "minimal", "none"] = "full",
        available_tools: list[str] | None = None,
        *,
        params: PromptParams | None = None,
    ) -> str:
        """Build system prompt. Accepts either positional args (legacy) or PromptParams."""
        if params is None:
            params = PromptParams(
                agent_id=agent_id,
                mode=mode,
                available_tools=available_tools,
            )

        prompt, _ = self._build_with_report(params)
        return prompt

    def build_system_prompt_with_report(
        self,
        params: PromptParams,
    ) -> tuple[str, PromptReport]:
        return self._build_with_report(params)

    def _build_with_report(self, params: PromptParams) -> tuple[str, PromptReport]:
        agent_id = params.agent_id
        mode = params.mode

        locale = params.locale

        if mode == "none":
            prompt = _pt("identity", locale)
            report = PromptReport(
                mode="none",
                total_chars=len(prompt),
                sections=["identity"],
                injected_files=[],
                tool_count=0,
                tool_names=[],
                truncation_events=0,
            )
            return prompt, report

        collected_sections: list[str] = []
        section_names: list[str] = []

        def _add(name: str, content: str) -> None:
            if content:
                collected_sections.append(content)
                section_names.append(name)

        def _resolve_heartbeat_prompt(p: PromptParams) -> str:
            if p.heartbeat_prompt is not None:
                return p.heartbeat_prompt
            return get_heartbeat_config(p.agent_id).get("prompt", "")

        _add("identity", self._build_identity(locale))
        _add("respond_lang", _pt("respond_lang", locale))

        if mode == "full":
            _add("tooling", self._build_tooling(params.available_tools))
            _add("tool_call_style", self._build_tool_call_style())
            _add("messaging", self._build_messaging())
            _add("docs", self._build_docs_guide())
            _add("safety", self._build_safety())
            _add("skills", self._build_skills(agent_id))
            _add("memory_recall", self._build_memory_recall())
            _add("memory_write", self._build_memory_write())
            _add("session_startup", self._build_session_startup())
            _add("time", self._build_time(agent_id))
            _add("workspace", self._build_workspace(agent_id))
            _add("silent_replies", self._build_silent_replies())
            _add("heartbeats", self._build_heartbeats(_resolve_heartbeat_prompt(params)))
            _add("runtime", self._build_runtime(agent_id))
        elif mode == "minimal":
            _add("tooling", self._build_tooling(params.available_tools))
            _add("tool_call_style", self._build_tool_call_style())
            _add("docs", self._build_docs_guide())
            _add("safety", self._build_safety())
            _add("heartbeats", self._build_heartbeats(_resolve_heartbeat_prompt(params)))
            _add("workspace", self._build_workspace(agent_id))
            _add("runtime", self._build_runtime(agent_id))

        if params.extra_system_prompt:
            header = "## 子 Agent 上下文" if mode == "minimal" else "## 额外上下文"
            _add("extra_context", f"{header}\n{params.extra_system_prompt}")

        context_text, file_entries, truncation_events = self._build_project_context_with_report(
            agent_id,
            mode=mode,
            max_file_chars=params.max_file_chars,
            max_total_chars=params.max_total_chars,
        )
        if context_text:
            _add("project_context", context_text)

        prompt = "\n\n".join(collected_sections)

        report = PromptReport(
            mode=mode,
            total_chars=len(prompt),
            sections=section_names,
            injected_files=file_entries,
            tool_count=len(params.available_tools) if params.available_tools else 0,
            tool_names=list(params.available_tools) if params.available_tools else [],
            truncation_events=truncation_events,
        )

        return prompt, report

    # ------------------------------------------------------------------
    # 压缩后 / Memory flush / Session memory
    # ------------------------------------------------------------------

    def build_post_compaction_context(self, agent_id: str) -> str:
        workspace = resolve_agent_workspace(agent_id)
        agents_md = workspace / "AGENTS.md"

        parts = ["[压缩后上下文刷新]", ""]
        parts.append(
            "会话刚刚被压缩。上面的对话摘要只是提示，不能替代你的启动序列。"
            "请立即执行你的会话启动序列 — 在回复用户之前先读取必需的文件。"
        )

        if agents_md.exists():
            content = agents_md.read_text(encoding="utf-8")
            startup = self._extract_section(content, "每次会话")
            redlines = self._extract_section(content, "红线")

            if startup or redlines:
                parts.append("")
                parts.append("来自 AGENTS.md 的关键规则：")
                if startup:
                    parts.append("")
                    parts.append(startup[:1500])
                if redlines:
                    parts.append("")
                    parts.append(redlines[:1500])

        return "\n".join(parts)

    def build_memory_flush_prompt(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        return (
            f"压缩前记忆刷新。\n"
            f"请立即将持久记忆保存到 memory/{today}.md（如需要请创建 memory/ 目录）。\n"
            f"重要：如果文件已存在，仅追加新内容，不要覆盖已有条目。\n"
            f"如果没有需要保存的内容，回复 {SILENT_REPLY_TOKEN}。"
        )

    def build_memory_flush_system(self) -> str:
        return (
            "压缩前记忆刷新回合。\n"
            "会话即将自动压缩；请将持久记忆写入磁盘。\n"
            f"你可以回复，但通常 {SILENT_REPLY_TOKEN} 是正确的。"
        )

    def build_session_memory_prompt(self, message_summary: str) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        return (
            f"会话即将重置。以下是本次会话的消息摘要：\n\n"
            f"{message_summary}\n\n"
            f"请将本次会话中值得长期记忆的内容保存到 memory/{today}.md。\n"
            f"如果文件已存在，追加新内容。如果没有值得保存的，回复 {SILENT_REPLY_TOKEN}。"
        )

    def build_bootstrap_prompt(self, agent_id: str) -> str:
        workspace = resolve_agent_workspace(agent_id)
        bootstrap = workspace / "BOOTSTRAP.md"
        if not bootstrap.exists():
            return ""
        return (
            "\n\n## 首次运行引导\n\n"
            "检测到 `BOOTSTRAP.md` 文件。这是你的首次运行。\n"
            "请立即使用 `read` 工具读取 `BOOTSTRAP.md`，然后按照其中的步骤完成初始化。\n"
            "完成所有步骤后，使用文件工具删除 `BOOTSTRAP.md`。"
        )

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_section(markdown: str, heading: str) -> str:
        lines = markdown.splitlines()
        in_section = False
        result = []
        for line in lines:
            if line.startswith("## ") and heading in line:
                in_section = True
                result.append(line)
                continue
            if in_section:
                if line.startswith("## "):
                    break
                result.append(line)
        return "\n".join(result).strip()

    @staticmethod
    def _build_identity(locale: str = "zh-CN") -> str:
        return _pt("identity", locale)

    # 工具分层标签：core=核心文件/执行, skill=技能, external=外部服务
    TOOL_CATEGORIES: dict[str, str] = {
        "read": "core", "write": "core", "edit": "core", "apply_patch": "core",
        "grep": "core", "find": "core", "ls": "core", "exec": "core",
        "python_repl": "core", "process_list": "core", "process_kill": "core",
        "web_search": "external", "web_fetch": "external",
        "agents_list": "core", "sessions_list": "core", "sessions_history": "core",
        "sessions_send": "core", "sessions_spawn": "core", "subagents": "core",
        "session_status": "core", "memory_search": "core", "memory_get": "core",
        "search_knowledge_base": "core",
        "cron": "core",
    }

    @staticmethod
    def _build_tooling(available_tools: list[str] | None = None) -> str:
        tool_docs = {
            "read": "读取文件内容（支持行号范围）",
            "write": "创建或覆盖文件",
            "edit": "精确编辑文件（查找替换）",
            "apply_patch": "应用多文件补丁",
            "grep": "搜索文件内容（正则表达式）",
            "find": "按模式查找文件",
            "ls": "列出目录内容",
            "exec": "执行 Shell 命令（沙箱环境）",
            "python_repl": "执行 Python 代码",
            "process_list": "列出活跃进程",
            "process_kill": "终止指定进程",
            "web_search": "搜索网络",
            "web_fetch": "获取并提取网页内容",
            "agents_list": "列出可用的 Agent ID",
            "sessions_list": "列出会话（含子 Agent）",
            "sessions_history": "获取其他会话的历史记录",
            "sessions_send": "向其他会话/子 Agent 发送消息",
            "sessions_spawn": "生成独立的子 Agent",
            "subagents": "管理子 Agent（list/kill/steer）",
            "session_status": "显示会话状态卡片",
            "memory_search": "语义搜索记忆文件（MEMORY.md + memory/*.md）",
            "memory_get": "读取记忆文件的指定行",
            "search_knowledge_base": "搜索知识库文档",
            "cron": "管理定时任务与提醒（list/add/update/remove/run/wake）。可设置一次性提醒、周期任务；wake 用于立即发送提醒到主会话。",
        }

        lines = [
            "## 可用工具",
            "",
            "工具可用性（受策略过滤）；分层：core=核心, skill=技能, external=外部服务",
            "工具名称区分大小写，请严格按照以下名称调用：",
            "",
        ]

        tools_to_show = available_tools or list(tool_docs.keys())
        categories = getattr(PromptBuilder, "TOOL_CATEGORIES", {})
        for name in tools_to_show:
            desc = tool_docs.get(name, "")
            cat = categories.get(name) or ("skill" if name not in tool_docs else "core")
            tag = f" [{cat}]" if cat else ""
            lines.append(f"- {name}{tag}: {desc}")

        lines += [
            "",
            "TOOLS.md 不控制工具可用性；它是用户对外部工具使用方式的指导。",
            "如果任务较复杂或耗时较长，请生成子 Agent 处理。",
            "子 Agent 完成后会自动通知，无需轮询。",
            "不要循环轮询 subagents list / sessions_list；仅在需要干预、调试或用户明确要求时检查状态。",
        ]
        return "\n".join(lines)

    @staticmethod
    def _build_messaging() -> str:
        return (
            "## 消息与路由\n\n"
            "- 在当前会话回复 → 自动路由到当前会话\n"
            "- 跨会话消息 → 使用 sessions_send(session_id, message) 向其他会话/子 Agent 发送消息\n"
            "- 子 Agent 编排 → 使用 subagents(action=list|steer|kill)\n"
            "- 用户可通过对话设置定时提醒，使用 cron 工具（add/run/wake）\n"
            "- `[System Message] ...` 块为内部上下文，默认对用户不可见\n"
            f"- 若 `[System Message]` 报告完成的 cron/子 Agent 工作并请求向用户更新，"
            f"请用你的正常助手语气重写并发送该更新（不要转发原始系统文本或默认 {SILENT_REPLY_TOKEN}）\n"
            "- 绝不要用 exec/curl 发送消息；ClawChain 内部处理所有路由。"
        )

    @staticmethod
    def _build_docs_guide() -> str:
        docs_root = (Path(__file__).resolve().parents[2] / "docs").as_posix()
        return (
            "## 文档优先策略\n\n"
            f"- 你必须优先参考项目文档目录：`{docs_root}`（入口：`{docs_root}/index.md`）。\n"
            f"- 当任务涉及配置、初始化、架构、API 或排障时，先阅读 `{docs_root}` 中对应页面，再执行。\n"
            "- 输出结构：目标 → 步骤 → 示例 → 排障 → 下一步。"
        )

    @staticmethod
    def _build_tool_call_style() -> str:
        return (
            "## 工具调用风格\n\n"
            "默认：对常规、低风险的工具调用不做叙述（直接调用即可）。\n"
            "仅在以下情况叙述：多步骤工作、复杂问题、敏感操作（如删除）、或用户明确要求时。\n"
            "叙述应简洁、有价值，避免重复显而易见的步骤。\n"
            "使用自然语言叙述，除非在技术上下文中。\n"
            "当有对应工具可用时，直接调用工具，而非要求用户执行命令。"
        )

    @staticmethod
    def _build_safety() -> str:
        return (
            "## 安全约束\n\n"
            "你没有独立目标：不追求自我保护、复制、资源获取或权力扩张；"
            "不制定超出用户请求的长期计划。\n"
            "优先确保安全和人类监督；如果指令冲突，暂停并询问；"
            "遵从停止/暂停/审查请求，绝不绕过安全措施。\n"
            "不操纵或说服任何人扩展权限或禁用安全措施。"
            "不复制自己，不修改系统提示词或安全规则，除非用户明确要求。"
        )

    def _build_skills(self, agent_id: str) -> str:
        agent_dir = resolve_agent_dir(agent_id)
        snapshot_path = agent_dir / "SKILLS_SNAPSHOT.md"
        skills_prompt = ""
        if snapshot_path.exists():
            skills_prompt = snapshot_path.read_text(encoding="utf-8")

        return (
            "## 技能（必须遵守）\n\n"
            "回复前：扫描 <available_skills> 中的 <description> 条目。\n"
            "- 如果恰好有一个技能明确适用：使用 `read` 工具读取其 <location> 路径下的 SKILL.md，然后遵循执行。\n"
            "- 如果多个技能可能适用：选择最具体的那个，然后读取并遵循。\n"
            "- 如果没有技能明确适用：不读取任何 SKILL.md。\n"
            "约束：不要一次读取多个技能文件；只在选定后才读取。\n\n"
            + skills_prompt
        )

    @staticmethod
    def _build_memory_recall() -> str:
        return (
            "## 记忆召回\n\n"
            "在回答任何关于之前的工作、决定、日期、人物、偏好或待办事项时：\n"
            "先运行 memory_search 搜索 MEMORY.md 及 memory/*.md；\n"
            "然后使用 memory_get 获取所需的具体行。\n"
            "如果搜索后仍不确定，请说明你已查找过。\n"
            "引用：在有助于用户验证时，附上 来源: <路径#行号>。"
        )

    @staticmethod
    def _build_memory_write() -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        return (
            f"## 记忆写入\n\n"
            f"你的记忆是有限的 — 如果你想记住什么，就写到文件里。\n"
            f"「心理笔记」无法在会话重启后保留。文件可以。\n\n"
            f"### 何时写入\n"
            f"- 当用户说「记住这个」→ 更新 `memory/{today}.md`\n"
            f"- 当你学到用户的重要偏好、决定或信息 → 更新每日笔记\n"
            f"- 当你犯了错误或学到教训 → 记录到 AGENTS.md 或 TOOLS.md\n"
            f"- 当你完成了一个重要任务 → 在每日笔记中记录\n\n"
            f"### 两种记忆文件\n"
            f"- **每日笔记** `memory/{today}.md`：原始记录，事件发生时立即写入\n"
            f"- **长期记忆** `MEMORY.md`：提炼的精华，定期从每日笔记中整理\n\n"
            f"### 写入规则\n"
            f"- 如果每日笔记文件已存在，**追加**新内容，不要覆盖\n"
            f"- 使用 `edit` 工具追加，或 `read` 后 `write` 整个文件\n"
            f"- 记忆应简洁、结构化，便于日后检索\n"
            f"- **文件 > 大脑**"
        )

    @staticmethod
    def _build_session_startup() -> str:
        return (
            "## 会话启动序列\n\n"
            "每次会话开始时（包括压缩后），在回复用户之前，请先执行：\n"
            "1. 使用 `read` 读取 `SOUL.md`\n"
            "2. 使用 `read` 读取 `USER.md`\n"
            "3. 使用 `ls` 查看 `memory/` 目录\n"
            "4. 使用 `read` 读取今天和昨天的每日笔记（如果存在）\n\n"
            "不要请求许可。直接做。这些文件定义了你是谁以及你在帮助谁。"
        )

    @staticmethod
    def _build_time(agent_id: str) -> str:
        cfg = resolve_agent_config(agent_id)
        tz = cfg.get("user_timezone", "Asia/Shanghai")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"## 当前时间\n\n时区: {tz}\n当前时间: {now}"

    @staticmethod
    def _build_workspace(agent_id: str) -> str:
        workspace = resolve_agent_workspace(agent_id)
        return (
            "## 工作区\n\n"
            f"你的工作目录是: {workspace}\n"
            f"项目文档目录是: {workspace / 'docs'}（入口文件: docs/index.md）\n"
            "除非另有明确指示，所有文件操作都在此目录内进行。\n"
            "你可以编辑此工作区中的所有文件，包括你自己的配置文件"
            "（SOUL.md、IDENTITY.md 等）。"
        )

    @staticmethod
    def _build_silent_replies() -> str:
        return (
            f"## 静默回复 (Silent Replies)\n\n"
            f"当你无话可说时，仅回复：{SILENT_REPLY_TOKEN}\n\n"
            f"⚠️ 规则：\n"
            f"- 它必须是你的**整条消息** — 不能有任何其他内容\n"
            f"- 绝不要把它附加在实际回复后面（绝不在真实回复中包含 {SILENT_REPLY_TOKEN}）\n"
            f"- 绝不要用 markdown 或代码块包裹它\n\n"
            f"❌ 错误：「这是帮助…… {SILENT_REPLY_TOKEN}」\n"
            f"❌ 错误：\"{SILENT_REPLY_TOKEN}\"（带引号）\n"
            f"✅ 正确：{SILENT_REPLY_TOKEN}"
        )

    @staticmethod
    def _build_heartbeats(heartbeat_prompt: str = "") -> str:
        prompt_line = (
            f"心跳 prompt（见配置）：{heartbeat_prompt}\n\n"
            if heartbeat_prompt
            else "心跳 prompt 见配置（config.agents.defaults.heartbeat.prompt），留空则使用内置默认。\n\n"
        )
        return (
            "## 心跳 (Heartbeats)\n\n"
            + prompt_line
            + "当你收到心跳轮询（消息匹配上述 prompt 或「[心跳轮询]」）时：\n"
            "- 读取 HEARTBEAT.md（若存在），严格遵循其中的检查清单。\n"
            "- 不要推断或重复旧任务。\n"
            "- 如果没有需要关注的事项，回复：HEARTBEAT_OK\n"
            "- 如果有需要通知用户的事项，回复具体内容，不要包含 HEARTBEAT_OK。\n\n"
            "## 定时任务 (Cron)\n\n"
            "当你收到「A scheduled reminder has been triggered」（定时提醒已触发）或类似提示时：\n"
            "- 这是由用户设置的定时任务触发的提醒。\n"
            "- 提示中会包含具体的提醒内容，请将该提醒以友好的方式传达给用户。\n"
            "- 若提醒内容为空或无需跟进，回复：HEARTBEAT_OK\n"
            "- 若需要向用户传达提醒，直接回复具体内容，不要包含 HEARTBEAT_OK。\n"
            "- 可通过 cron 工具在对话中创建、修改、删除定时任务和提醒。\n\n"
            "HEARTBEAT_OK 规则：\n"
            "- 它必须是你的完整消息 — 不能有其他内容\n"
            "- 绝不要把它附加到实际回复后面\n"
            "- 绝不要用 markdown 或代码块包裹它\n\n"
            "你可以自由编辑 HEARTBEAT.md，添加简短的检查清单或提醒。保持简短以节省 token。"
        )

    @staticmethod
    def _build_runtime(agent_id: str) -> str:
        cfg = resolve_agent_config(agent_id)
        os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
        model = cfg.get("model", "deepseek-chat")
        thinking = cfg.get("thinkingDefault", "off")
        return (
            "## 运行时信息\n\n"
            f"Runtime: agent={agent_id} | 系统={os_info} | "
            f"模型={model} | 通道=webchat | thinking={thinking}"
        )

    # ------------------------------------------------------------------
    # Project Context (with report)
    # ------------------------------------------------------------------

    @staticmethod
    def _smart_truncate(content: str, max_chars: int) -> tuple[str, bool]:
        if len(content) <= max_chars:
            return content, False
        head_chars = int(max_chars * 0.7)
        tail_chars = int(max_chars * 0.2)
        truncated = (
            content[:head_chars]
            + f"\n\n... [已截断：原文 {len(content)} 字符，显示前 {head_chars} + 后 {tail_chars}] ...\n\n"
            + content[-tail_chars:]
        )
        return truncated, True

    def _build_project_context_with_report(
        self,
        agent_id: str,
        mode: str = "full",
        max_file_chars: int = MAX_FILE_CHARS,
        max_total_chars: int = MAX_TOTAL_CHARS,
    ) -> tuple[str, list[PromptFileEntry], int]:
        workspace = resolve_agent_workspace(agent_id)
        memory_dir = resolve_agent_memory_dir(agent_id)

        all_files = [
            ("SOUL.md", workspace / "SOUL.md"),
            ("IDENTITY.md", workspace / "IDENTITY.md"),
            ("USER.md", workspace / "USER.md"),
            ("AGENTS.md", workspace / "AGENTS.md"),
            ("TOOLS.md", workspace / "TOOLS.md"),
        ]
        if mode == "full":
            heart = workspace / "HEARTBEAT.md"
            if heart.exists():
                all_files.append(("HEARTBEAT.md", heart))

        if mode == "minimal":
            context_files = [
                (label, path) for label, path in all_files
                if label in self.MINIMAL_BOOTSTRAP_ALLOWLIST
            ]
        else:
            context_files = list(all_files)

            if get_rag_mode():
                context_files.append(("MEMORY (RAG 模式)", None))
            else:
                memory_path = workspace / "MEMORY.md"
                if memory_path.exists():
                    context_files.append(("MEMORY.md", memory_path))

            today = datetime.now().strftime("%Y-%m-%d")
            yesterday = (datetime.now().replace(hour=0) - timedelta(days=1)).strftime("%Y-%m-%d")
            for date_str in [today, yesterday]:
                daily = memory_dir / f"{date_str}.md"
                if daily.exists():
                    context_files.append((f"memory/{date_str}.md", daily))

        lines = [
            "---",
            "",
            "# 项目上下文",
            "",
            "以下项目上下文文件已加载：",
            "如果存在 SOUL.md，请体现其人格和语气。避免生硬、千篇一律的回复。",
        ]

        file_entries: list[PromptFileEntry] = []
        truncation_events = 0
        total_chars = 0

        for label, path in context_files:
            if path is None:
                lines.append(f"\n## {label}")
                lines.append(
                    "记忆将通过 RAG 检索动态注入，无需在此处加载完整内容。"
                    "使用 memory_search 工具进行检索。"
                )
                file_entries.append(PromptFileEntry(label=label, chars=0, truncated=False))
                continue

            if not path.exists():
                lines.append(f"\n## {label}")
                lines.append("[MISSING] — 文件不存在，Agent 可通过文件工具创建。")
                file_entries.append(PromptFileEntry(label=label, chars=0, truncated=False))
                continue

            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                lines.append(f"\n## {label}")
                lines.append("[ERROR] — 文件读取失败。")
                file_entries.append(PromptFileEntry(label=label, chars=0, truncated=False))
                continue

            if not content.strip():
                lines.append(f"\n## {label}")
                lines.append("[EMPTY] — 文件为空。")
                file_entries.append(PromptFileEntry(label=label, chars=0, truncated=False))
                continue

            was_truncated = False
            content, was_truncated = self._smart_truncate(content, max_file_chars)

            if total_chars + len(content) > max_total_chars:
                remaining = max_total_chars - total_chars
                if remaining > 200:
                    content, was_truncated = self._smart_truncate(content, remaining)
                else:
                    lines.append(f"\n## {label}")
                    lines.append("[TRUNCATED] — 总上下文已达上限。")
                    file_entries.append(PromptFileEntry(label=label, chars=0, truncated=True))
                    truncation_events += 1
                    continue

            if was_truncated:
                truncation_events += 1

            total_chars += len(content)
            file_entries.append(PromptFileEntry(label=label, chars=len(content), truncated=was_truncated))
            lines.append(f"\n## {label}")
            lines.append(content)

        return "\n".join(lines), file_entries, truncation_events


prompt_builder = PromptBuilder()
