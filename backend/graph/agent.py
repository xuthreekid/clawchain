"""Agent 引擎核心 — AgentManager, AgentState, 生命周期, 自动压缩, 命令处理"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from config import (
    DATA_DIR,
    resolve_agent_config,
    resolve_agent_workspace,
    resolve_agent_dir,
    resolve_agent_memory_dir,
    get_rag_mode,
    list_agents,
)
from graph.prompt_builder import prompt_builder
from graph.session_manager import session_manager
from graph.memory_indexer import MemoryIndexer
from graph.memory_search_engine import MemorySearchEngine
from graph.run_tracker import run_tracker
from graph.audit_log import audit_logger
from graph.token_counter import (
    count_messages_tokens,
    should_compact,
    should_run_memory_flush,
    DEFAULT_COMPACTION_THRESHOLD,
)
from graph.session_pruning import prune_messages
from graph.command_parser import parse_command, execute_command
from graph.tool_call_parser import parse_text_tool_calls, strip_tool_call_patterns
from graph.errors import (
    is_compaction_failure_error,
    is_likely_context_overflow_error,
    is_role_ordering_error,
    is_session_corruption_error,
    is_transient_http_error,
)
from graph.model_selection import (
    resolve_fallback_candidates,
    run_with_fallback_stream,
)
from graph.models_config import ModelRef
from graph.llm_factory import create_llm

logger = logging.getLogger(__name__)

TRANSIENT_HTTP_RETRY_DELAY_MS = 2500

# 裸 /new 或 /reset 后作为首条用户消息注入，触发 Session Startup + 问候
BARE_SESSION_RESET_PROMPT = (
    "A new session was started via /new or /reset. Execute your Session Startup sequence now - "
    "read the required files before responding to the user. Then greet the user in your configured persona, "
    "if one is provided. Be yourself - use your defined voice, mannerisms, and mood. "
    "Keep it to 1-3 sentences and ask what they want to do. "
    "If the runtime model differs from default_model in the system prompt, mention the default model. "
    "Do not mention internal steps, files, tools, or reasoning."
)

# ---------------------------------------------------------------------------
# AgentState — 每个 Agent 实例的运行时状态
# ---------------------------------------------------------------------------

@dataclass
class AgentState:
    agent_id: str
    compaction_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_turns: int = 0
    think_level: int = 0
    verbose: bool = False
    reasoning: bool = False
    last_active: float = 0.0
    _tools_cache: list | None = field(default=None, repr=False)

    @property
    def thinking(self) -> bool:
        return self.think_level > 0

    def record_turn(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_turns += 1
        import time
        self.last_active = time.time()

    def invalidate_tools(self) -> None:
        self._tools_cache = None


# ---------------------------------------------------------------------------
# 生命周期钩子
# ---------------------------------------------------------------------------

@dataclass
class LifecycleHooks:
    """显式生命周期钩子，用于审计、确认、记录等扩展"""

    async def on_before_tool_call(
        self, agent_id: str, run_id: str, tool_name: str, tool_input: dict[str, Any]
    ) -> None:
        """工具调用前（可在此拦截/确认）"""
        pass

    async def on_after_tool_call(
        self, agent_id: str, run_id: str, tool_name: str, tool_input: Any, tool_output: str
    ) -> None:
        """工具调用后（审计、记录）"""
        pass




# ---------------------------------------------------------------------------
# SSE 事件队列 — 用于前端实时更新
# ---------------------------------------------------------------------------

class EventBus:
    """简易事件总线，支持 SSE 订阅"""

    def __init__(self):
        self._queues: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, agent_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._queues.setdefault(agent_id, []).append(queue)
        return queue

    def unsubscribe(self, agent_id: str, queue: asyncio.Queue) -> None:
        queues = self._queues.get(agent_id, [])
        if queue in queues:
            queues.remove(queue)

    def emit(self, agent_id: str, event: dict[str, Any]) -> None:
        for queue in self._queues.get(agent_id, []):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass


event_bus = EventBus()


# ---------------------------------------------------------------------------
# AgentManager — 核心引擎
# ---------------------------------------------------------------------------

class AgentManager:
    def __init__(self):
        self.data_dir: str = ""
        self.memory_indexers: dict[str, MemoryIndexer] = {}
        self.memory_search_engines: dict[str, MemorySearchEngine] = {}
        self._states: dict[str, AgentState] = {}
        self._initialized = False
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self.lifecycle_hooks: LifecycleHooks | None = None  # 可选扩展点

    async def initialize(self, data_dir: str) -> None:
        self.data_dir = data_dir
        self._main_loop = asyncio.get_running_loop()

        from graph.workspace import ensure_agent_workspace

        for agent in list_agents():
            agent_id = agent["id"]
            ensure_agent_workspace(agent_id)
            agent_dir = str(resolve_agent_dir(agent_id))
            self.memory_indexers[agent_id] = MemoryIndexer(agent_dir)
            self.memory_indexers[agent_id].rebuild_index()
            engine = MemorySearchEngine(agent_dir, agent_id)
            engine.rebuild_index()
            engine.start_watching()
            self.memory_search_engines[agent_id] = engine
            from graph.thinking import resolve_agent_think_default
            think_level = resolve_agent_think_default(agent_id)
            self._states[agent_id] = AgentState(agent_id=agent_id, think_level=think_level.value)

        self._initialized = True

    def get_llm(self, agent_id: str = "main"):
        """获取指定 Agent 的 LLM 实例（per-agent 动态创建，按 Provider 配置路由）"""
        from graph.llm_factory import llm_cache
        from graph.model_selection import resolve_agent_model

        ref = resolve_agent_model(agent_id)
        return llm_cache.get_or_create(agent_id, ref)

    def get_current_model_ref(self, agent_id: str = "main"):
        """获取 Agent 当前使用的 ModelRef"""
        from graph.model_selection import resolve_agent_model
        return resolve_agent_model(agent_id)

    def switch_model(self, agent_id: str, model_raw: str) -> str:
        """运行时切换 Agent 模型，返回新模型描述"""
        from graph.llm_factory import llm_cache
        from graph.model_selection import resolve_agent_model, get_model_display_name
        from graph.models_config import parse_model_ref

        ref = parse_model_ref(model_raw)
        if not ref:
            raise ValueError(f"Invalid model reference: {model_raw}")

        if not ref.provider:
            from graph.models_config import models_config
            found = models_config.find_model_by_id(ref.model)
            if found:
                provider, model_def = found
                ref.provider = provider.id
            else:
                raise ValueError(f"Model '{ref.model}' not found in any provider")

        llm_cache.invalidate(agent_id)
        llm_cache.get_or_create(agent_id, ref)

        return get_model_display_name(ref)

    def get_state(self, agent_id: str) -> AgentState:
        if agent_id not in self._states:
            self._states[agent_id] = AgentState(agent_id=agent_id)
        return self._states[agent_id]

    def _build_tools(self, agent_id: str, session_id: str = "") -> list:
        workspace = str(resolve_agent_workspace(agent_id))
        agent_dir = str(resolve_agent_dir(agent_id))

        from tools.file_tools import get_file_tools
        from tools.exec_tools import get_exec_tools
        from tools.web_tools import get_web_tools
        from tools.memory_tools import get_memory_tools
        from tools.knowledge_tool import get_knowledge_tools
        from tools.agent_tools import get_agent_tools
        from tools.cron_tools import get_cron_tools
        from tools.status_tool import get_status_tools

        tools = []
        tools.extend(get_file_tools(workspace, agent_id=agent_id))
        tools.extend(get_exec_tools(workspace, agent_id))
        tools.extend(get_web_tools())
        tools.extend(get_memory_tools(agent_dir))
        tools.extend(get_knowledge_tools(agent_dir))
        tools.extend(get_agent_tools(agent_id, self, session_id, main_loop=self._main_loop))
        tools.extend(get_cron_tools(agent_id))
        tools.extend(get_status_tools(agent_id, session_id))

        tools = self._filter_tools_by_policy(agent_id, tools)
        return tools

    def _filter_tools_by_policy(self, agent_id: str, tools: list) -> list:
        """按 agents.list[].tools.allow/deny 过滤工具"""
        from config import get_config
        cfg = get_config()
        agent_entry = None
        for a in (cfg.get("agents", {}).get("list") or []):
            if a.get("id") == agent_id:
                agent_entry = a
                break
        policy = (agent_entry or {}).get("tools") or {}
        defaults_policy = (cfg.get("agents", {}).get("defaults", {}).get("tools")) or {}
        deny = list(policy.get("deny") or defaults_policy.get("deny") or [])
        allow = list(policy.get("allow") or defaults_policy.get("allow") or [])

        def _normalize(name: str) -> str:
            return name.replace("-", "_").lower().strip()

        deny_set = {_normalize(d) for d in deny if d}
        allow_set = {_normalize(a) for a in allow if a} if allow else None

        def _is_allowed(tool_name: str) -> bool:
            n = _normalize(tool_name)
            if n in deny_set:
                return False
            if allow_set is None:
                return True
            if n in allow_set:
                return True
            if n == "apply_patch" and "exec" in allow_set:
                return True
            return False

        return [t for t in tools if _is_allowed(t.name)]

    def _build_messages(
        self, history: list[dict[str, Any]], new_message: str
    ) -> list:
        messages = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
            elif role == "system":
                messages.append(SystemMessage(content=content))
        messages.append(HumanMessage(content=new_message))
        return messages

    # ------------------------------------------------------------------
    # 核心流式方法
    # ------------------------------------------------------------------

    async def astream(
        self,
        message: str,
        session_id: str,
        agent_id: str = "main",
        prompt_mode: str = "full",
        persist_input_role: str = "user",
    ) -> AsyncGenerator[dict[str, Any], None]:
        from tools.skills_scanner import write_skills_snapshot

        state = self.get_state(agent_id)

        # 命令处理
        parsed = parse_command(message)
        if parsed:
            result = await execute_command(parsed, agent_id, session_id, state)
            if result.get("handled"):
                action = result.get("action", "")

                if action == "reset":
                    # /new：保存 session-memory 后重置，再注入 BARE_SESSION_RESET_PROMPT 跑一轮问候
                    model_override = result.get("model_override")
                    async for evt in self._handle_reset(
                        session_id, agent_id, model_override=model_override
                    ):
                        yield evt
                    message = BARE_SESSION_RESET_PROMPT
                elif action == "reset_noflush":
                    # /reset：不写入 session-memory 的轻量重置，再注入 BARE_SESSION_RESET_PROMPT 跑一轮问候
                    async for evt in self._handle_reset_noflush(session_id, agent_id):
                        yield evt
                    message = BARE_SESSION_RESET_PROMPT
                else:
                    if action == "compact":
                        async for evt in self._handle_compact(session_id, agent_id):
                            yield evt
                        return
                    if action == "stop":
                        yield {"type": "command_response", "response": result["response"]}
                        yield {"type": "done", "content": result["response"], "session_id": session_id}
                        return
                    yield {"type": "command_response", "response": result["response"]}
                    yield {"type": "done", "content": result["response"], "session_id": session_id}
                    return

        write_skills_snapshot(agent_id)

        # 压缩前 Memory Flush：在处理消息前、接近阈值时提前触发
        agent_cfg = resolve_agent_config(agent_id)
        compaction_cfg = agent_cfg.get("compaction", {})
        if compaction_cfg.get("enabled", True) and compaction_cfg.get("memoryFlush", True):
            session_data = session_manager.load_session(session_id, agent_id)
            if should_run_memory_flush(session_data, agent_id, state.compaction_count):
                flush_result = await self.run_memory_flush(session_id, agent_id)
                if flush_result is not None:
                    session_manager.set_memory_flush_compaction_count(
                        session_id, agent_id, state.compaction_count
                    )

        # 检测 BOOTSTRAP.md
        from graph.workspace import has_bootstrap
        extra_prompt = ""
        if has_bootstrap(agent_id):
            bootstrap_path = resolve_agent_workspace(agent_id) / "BOOTSTRAP.md"
            try:
                extra_prompt = (
                    "\n\n## 首次运行引导\n\n"
                    "检测到 BOOTSTRAP.md，请先读取并执行其中的引导步骤。"
                    "完成后删除该文件。\n"
                )
            except Exception:
                pass

        tools = self._build_tools(agent_id, session_id)
        available_tool_names = [t.name for t in tools] if tools else None

        from graph.prompt_builder import PromptParams
        from config import get_config
        _locale = get_config().get("app", {}).get("locale", "zh-CN")
        prompt_params = PromptParams(
            agent_id=agent_id,
            mode=prompt_mode,
            available_tools=available_tool_names,
            extra_system_prompt=extra_prompt or None,
            locale=_locale,
        )
        system_prompt, prompt_report = prompt_builder.build_system_prompt_with_report(prompt_params)
        logger.info(prompt_report.summary())

        history = session_manager.load_session_for_agent(session_id, agent_id)

        # 会话修剪
        history = prune_messages(history)

        # RAG 检索
        if get_rag_mode() and prompt_mode == "full":
            indexer = self.memory_indexers.get(agent_id)
            if indexer:
                results = indexer.retrieve(message, top_k=3)
                if results:
                    yield {
                        "type": "retrieval",
                        "query": message,
                        "results": [
                            {"text": r["text"], "score": r["score"], "source": r["source"]}
                            for r in results
                        ],
                    }
                    context_parts = ["[记忆检索结果]"]
                    for r in results:
                        context_parts.append(f"来源: {r['source']}#L{r['line']}")
                        context_parts.append(r["text"])
                        context_parts.append("")
                    rag_context = "\n".join(context_parts)
                    history.append({"role": "assistant", "content": rag_context})

        agent_cfg = resolve_agent_config(agent_id)
        recursion_limit = agent_cfg.get("recursion_limit", 50)

        candidates = resolve_fallback_candidates(agent_id)
        did_retry_transient = False
        did_reset_compaction = False

        async def run_for_model(provider: str, model: str):
            ref = ModelRef(provider=provider, model=model)
            try:
                llm = create_llm(ref)
            except Exception as e:
                yield {"type": "error", "error": f"LLM 初始化失败: {e}"}
                return

            try:
                from langgraph.prebuilt import create_react_agent
                agent = create_react_agent(
                    model=llm,
                    tools=tools,
                    prompt=system_prompt,
                )
            except ImportError:
                yield {"type": "error", "error": "langgraph 未安装"}
                return

            lc_messages = self._build_messages(history, message)

            turn = run_tracker.start_turn(agent_id, session_id)
            audit_logger.log_turn_start(agent_id, turn.run_id, session_id)
            yield {"type": "lifecycle", "event": "turn_start", "run_id": turn.run_id, "model": str(ref)}

            full_response = ""
            tool_calls_log: list[dict[str, Any]] = []
            tool_input_by_run_id: dict[str, Any] = {}
            _streaming_model_run_id: str | None = None
            step_count = 0
            _content_refresh_sent = False

            try:
                async for event in agent.astream_events(
                    {"messages": lc_messages},
                    version="v2",
                    config={"recursion_limit": recursion_limit},
                ):
                    kind = event.get("event", "")

                    if kind == "on_chat_model_stream":
                        evt_run_id = event.get("run_id", "")
                        if _streaming_model_run_id is None:
                            _streaming_model_run_id = evt_run_id
                        elif evt_run_id != _streaming_model_run_id:
                            continue

                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            content = chunk.content
                            if isinstance(content, str):
                                full_response += content
                                yield {"type": "token", "content": content}

                        if chunk and hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                            usage = chunk.usage_metadata
                            run_tracker.record_tokens(
                                turn.run_id,
                                input_tokens=getattr(usage, "input_tokens", 0),
                                output_tokens=getattr(usage, "output_tokens", 0),
                                cache_read=getattr(usage, "input_token_details", {}).get("cache_read", 0) if hasattr(usage, "input_token_details") else 0,
                            )

                    elif kind == "on_chat_model_end":
                        if event.get("run_id") == _streaming_model_run_id:
                            _streaming_model_run_id = None

                    elif kind == "on_tool_start":
                        # 若 full_response 含文本形式工具调用，首次 tool_start 时刷新前端
                        if not _content_refresh_sent and full_response and parse_text_tool_calls(full_response):
                            cleaned = strip_tool_call_patterns(full_response)
                            yield {"type": "content_refresh", "content": cleaned}
                            _content_refresh_sent = True
                        tool_name = event.get("name", "")
                        tool_input = event.get("data", {}).get("input") or {}
                        if not isinstance(tool_input, dict):
                            tool_input = {}
                        if self.lifecycle_hooks:
                            await self.lifecycle_hooks.on_before_tool_call(
                                agent_id, turn.run_id, tool_name, tool_input
                            )
                        step_count += 1
                        evt_run_id = str(event.get("run_id", ""))
                        if evt_run_id:
                            tool_input_by_run_id[evt_run_id] = tool_input
                        run_tracker.record_tool_start(turn.run_id, tool_name, tool_input)
                        yield {
                            "type": "tool_start", "tool": tool_name, "input": tool_input,
                            "step": step_count, "max_steps": recursion_limit,
                        }

                    elif kind == "on_tool_end":
                        tool_output = event.get("data", {}).get("output", "")
                        if isinstance(tool_output, str):
                            output_str = tool_output
                        elif hasattr(tool_output, "content") and tool_output.content is not None:
                            output_str = str(tool_output.content)
                        else:
                            output_str = str(tool_output)

                        evt_run_id = str(event.get("run_id", ""))
                        tool_input = tool_input_by_run_id.pop(evt_run_id, None)
                        tool_input_for_log = tool_input if tool_input is not None else ""
                        tool_name = event.get("name", "")
                        run_tracker.record_tool_end(turn.run_id, tool_name, output_str)
                        audit_logger.log_tool_call(
                            agent_id, turn.run_id, tool_name,
                            tool_input_for_log,
                            output_str,
                        )

                        tool_calls_log.append({
                            "tool": tool_name,
                            "input": tool_input_for_log,
                            "output": output_str[:2000],
                        })
                        if self.lifecycle_hooks:
                            await self.lifecycle_hooks.on_after_tool_call(
                                agent_id, turn.run_id, tool_name, tool_input_for_log, output_str
                            )
                        yield {"type": "tool_end", "tool": tool_name, "output": output_str[:2000]}

                        # 危险工具执行后通知前端（用于审计/确认提示）
                        if tool_name in ("exec", "process_kill"):
                            safe_input = str(tool_input_for_log)[:200] if tool_input_for_log else ""
                            event_bus.emit(agent_id, {
                                "type": "lifecycle",
                                "event": "tool_dangerous_executed",
                                "tool": tool_name,
                                "input_preview": safe_input,
                            })

            except Exception as e:
                error_str = str(e)
                is_recursion = "recursion" in error_str.lower() or "GraphRecursionError" in type(e).__name__
                run_tracker.error_turn(turn.run_id, error_str)
                audit_logger.log_turn_error(agent_id, turn.run_id, error_str)
                if is_recursion:
                    yield {
                        "type": "lifecycle", "event": "recursion_limit_reached",
                        "step": step_count, "max_steps": recursion_limit,
                    }
                    yield {
                        "type": "error",
                        "error": f"Agent 达到最大迭代次数 ({recursion_limit})，已自动停止。已执行 {step_count} 步工具调用。",
                    }
                else:
                    yield {"type": "lifecycle", "event": "turn_error", "error": error_str}
                    yield {"type": "error", "error": error_str}
                return

            # 生命周期: Turn 完成
            completed = run_tracker.complete_turn(turn.run_id)
            if completed:
                state.record_turn(completed.input_tokens, completed.output_tokens)
                audit_logger.log_turn_end(
                    agent_id, turn.run_id, session_id,
                    tokens={"input": completed.input_tokens, "output": completed.output_tokens},
                    tool_calls=len(tool_calls_log),
                    duration_ms=completed.duration_ms,
                )

            # Fallback: 模型以文本形式输出 tool call 时，解析并执行（Kimi K2 等）
            parsed_calls = parse_text_tool_calls(full_response)
            if parsed_calls and not tool_calls_log:
                if not _content_refresh_sent:
                    cleaned = strip_tool_call_patterns(full_response)
                    yield {"type": "content_refresh", "content": cleaned}
                    _content_refresh_sent = True
                tool_names = {getattr(t, "name", ""): t for t in tools}
                for fallback_tool_name, fallback_tool_args in parsed_calls:
                    matched_tool = tool_names.get(fallback_tool_name)
                    if matched_tool:
                        step_count += 1
                        args_to_use = dict(fallback_tool_args) if fallback_tool_args else {}
                        if fallback_tool_name == "read" and not args_to_use.get("path"):
                            args_to_use["path"] = "IDENTITY.md"
                            logger.info(f"Fallback read: 无 path 参数，使用默认 IDENTITY.md")
                        run_tracker.record_tool_start(turn.run_id, fallback_tool_name, args_to_use)
                        logger.info(f"Fallback tool call: {fallback_tool_name}({args_to_use})")
                        yield {
                            "type": "tool_start", "tool": fallback_tool_name, "input": args_to_use,
                            "step": step_count, "max_steps": recursion_limit,
                        }
                        try:
                            result_str = str(matched_tool._run(**args_to_use))[:2000]
                        except Exception as te:
                            from tools.error_utils import format_tool_error
                            result_str = format_tool_error(fallback_tool_name, te)
                        run_tracker.record_tool_end(turn.run_id, fallback_tool_name, result_str)
                        audit_logger.log_tool_call(agent_id, turn.run_id, fallback_tool_name, args_to_use, result_str)
                        yield {"type": "tool_end", "tool": fallback_tool_name, "output": result_str}
                        tool_calls_log.append({
                            "tool": fallback_tool_name,
                            "input": args_to_use,
                            "output": result_str,
                        })
                full_response = strip_tool_call_patterns(full_response)

            # 保存消息（若含文本形式工具调用则保存清理后的 content）
            session_manager.save_message(session_id, agent_id, persist_input_role, message)
            content_to_save = strip_tool_call_patterns(full_response) if parse_text_tool_calls(full_response) else full_response
            session_manager.save_message(
                session_id, agent_id, "assistant", content_to_save,
                tool_calls=tool_calls_log if tool_calls_log else None,
            )

            write_skills_snapshot(agent_id)

            # 发送完成事件 (含 token 使用信息)
            usage_info = {}
            if completed:
                usage_info = {
                    "input_tokens": completed.input_tokens,
                    "output_tokens": completed.output_tokens,
                    "total_tokens": completed.total_tokens,
                    "duration_ms": completed.duration_ms,
                    "model": str(ref),
                }

            yield {
                "type": "lifecycle",
                "event": "turn_end",
                "run_id": turn.run_id,
                "usage": usage_info,
            }
            done_content = strip_tool_call_patterns(full_response) if parse_text_tool_calls(full_response) else full_response
            yield {
                "type": "done",
                "content": done_content,
                "session_id": session_id,
                "usage": usage_info,
            }

            # 自动压缩检测
            await self._maybe_auto_compact(session_id, agent_id)

        # 外层循环：瞬时 HTTP 重试、压缩失败/role ordering/session 损坏恢复
        while True:
            try:
                async for evt in run_with_fallback_stream(candidates, run_for_model):
                    yield evt
                break
            except Exception as e:
                msg = str(e)
                if is_transient_http_error(msg) and not did_retry_transient:
                    did_retry_transient = True
                    logger.warning(
                        f"Transient HTTP error ({msg[:150]}). Retrying in {TRANSIENT_HTTP_RETRY_DELAY_MS}ms."
                    )
                    await asyncio.sleep(TRANSIENT_HTTP_RETRY_DELAY_MS / 1000)
                    continue

                if is_compaction_failure_error(msg) and not did_reset_compaction:
                    did_reset_compaction = True
                    session_manager.reset_session(session_id, agent_id)
                    state.compaction_count = 0
                    audit_logger.log(agent_id, "session_reset_compaction_failure", {"error": msg[:200]})
                    yield {
                        "type": "session_reset",
                        "session_id": session_id,
                        "memory": {"saved": False, "reason": "compaction_failure"},
                    }
                    yield {
                        "type": "done",
                        "content": (
                            "⚠️ 上下文超出限制，压缩失败。已重置会话，请重试。\n\n"
                            "建议在 config 中提高 agents.defaults.compaction.reserveTokensFloor（如 20000）以降低此问题。"
                        ),
                        "session_id": session_id,
                    }
                    return

                if is_role_ordering_error(msg):
                    session_manager.reset_session(session_id, agent_id)
                    state.compaction_count = 0
                    yield {"type": "session_reset", "session_id": session_id, "memory": {"saved": False}}
                    yield {
                        "type": "done",
                        "content": "⚠️ 消息顺序冲突，已重置会话，请重试。",
                        "session_id": session_id,
                    }
                    return

                if is_session_corruption_error(msg):
                    session_manager.reset_session(session_id, agent_id)
                    state.compaction_count = 0
                    yield {"type": "session_reset", "session_id": session_id, "memory": {"saved": False}}
                    yield {
                        "type": "done",
                        "content": "⚠️ 会话历史损坏，已重置，请重试。",
                        "session_id": session_id,
                    }
                    return

                if is_likely_context_overflow_error(msg):
                    yield {
                        "type": "error",
                        "error": "⚠️ 上下文溢出 — 提示过长。请缩短消息或使用更大 context 的模型。",
                    }
                    return

                yield {"type": "lifecycle", "event": "turn_error", "error": msg}
                yield {"type": "error", "error": msg}
                return

    # ------------------------------------------------------------------
    # 自动压缩
    # ------------------------------------------------------------------

    async def _maybe_auto_compact(self, session_id: str, agent_id: str) -> None:
        agent_cfg = resolve_agent_config(agent_id)
        compaction_cfg = agent_cfg.get("compaction", {})
        if not compaction_cfg.get("enabled", True):
            return

        data = session_manager.load_session(session_id, agent_id)
        if not data:
            return

        messages = data.get("messages", [])
        compressed = data.get("compressed_context")

        from graph.token_counter import resolve_compaction_threshold
        threshold = resolve_compaction_threshold(agent_id)

        if should_compact(messages, compressed, threshold=threshold):
            logger.info(f"Auto-compaction triggered for {agent_id}:{session_id} (threshold={threshold})")
            audit_logger.log(agent_id, "auto_compact_trigger", {"session_id": session_id, "threshold": threshold})
            event_bus.emit(agent_id, {
                "type": "lifecycle",
                "event": "auto_compact_start",
                "session_id": session_id,
            })
            try:
                await self.compress_with_flush(session_id, agent_id)
                event_bus.emit(agent_id, {
                    "type": "lifecycle",
                    "event": "auto_compact_done",
                    "session_id": session_id,
                })
            except Exception as e:
                logger.error(f"Auto-compaction failed: {e}")
                audit_logger.log(agent_id, "auto_compact_error", {"error": str(e)})

    # ------------------------------------------------------------------
    # 会话重置命令处理：/new 与 /reset
    # ------------------------------------------------------------------

    async def _handle_reset(
        self, session_id: str, agent_id: str, model_override: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """/new：保存 session-memory 后重置会话"""
        yield {"type": "command_response", "response": "正在重置会话（写入长期记忆，可能需要数秒）..."}

        data = session_manager.load_session(session_id, agent_id)
        messages = data.get("messages", []) if data else []

        # /new 快速路径：不在前台阻塞等待记忆保存，先重置会话再后台异步归档。
        mem_result: dict[str, Any] = {"saved": False, "reason": "消息过少"}
        if len(messages) >= 2:
            snapshot = [
                {
                    "role": m.get("role", "user"),
                    "content": m.get("content", "") or "",
                }
                for m in messages
            ]
            asyncio.create_task(
                self._save_session_memory_background(
                    agent_id=agent_id,
                    source_session_id=session_id,
                    messages_snapshot=snapshot,
                )
            )
            mem_result = {"saved": False, "queued": True, "reason": "后台保存中"}

        session_manager.reset_session(session_id, agent_id)

        state = self.get_state(agent_id)
        state.compaction_count = 0

        model_msg = ""
        if model_override:
            try:
                new_name = self.switch_model(agent_id, model_override)
                model_msg = f" 模型已切换到 {new_name}。"
            except Exception as e:
                model_msg = f" 模型切换失败: {e}"

        audit_logger.log(
            agent_id,
            "session_reset",
            {
                "session_id": session_id,
                "memory_saved": mem_result.get("saved", False),
                "model_override": model_override,
                "mode": "with_memory",
            },
        )

        msg = "会话已重置。"
        if mem_result.get("queued"):
            msg += " 长期记忆将在后台保存。"
        elif mem_result.get("saved"):
            msg += f" 记忆已保存到 {mem_result.get('path', '')}"
        msg += model_msg

        yield {"type": "command_response", "response": msg}
        yield {"type": "session_reset", "session_id": session_id, "memory": mem_result}
        # 不 yield done：主流程会接着用 BARE_SESSION_RESET_PROMPT 跑问候，由 agent 流产出 done

    async def _handle_reset_noflush(
        self, session_id: str, agent_id: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """/reset：不写入 session-memory 的轻量重置，仅归档会话文件。"""
        yield {"type": "command_response", "response": "正在重置会话（不写入长期记忆）..."}

        session_manager.reset_session(session_id, agent_id)

        state = self.get_state(agent_id)
        state.compaction_count = 0

        audit_logger.log(
            agent_id,
            "session_reset",
            {
                "session_id": session_id,
                "memory_saved": False,
                "mode": "no_memory",
            },
        )

        msg = "会话已重置（本轮对话未写入长期记忆）。"
        yield {"type": "command_response", "response": msg}
        yield {
            "type": "session_reset",
            "session_id": session_id,
            "memory": {"saved": False, "reason": "no-flush"},
        }
        # 不 yield done：主流程会接着用 BARE_SESSION_RESET_PROMPT 跑问候，由 agent 流产出 done

    # ------------------------------------------------------------------
    # /compact 命令处理
    # ------------------------------------------------------------------

    async def _handle_compact(
        self, session_id: str, agent_id: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        yield {"type": "command_response", "response": "正在执行压缩..."}
        event_bus.emit(agent_id, {
            "type": "lifecycle",
            "event": "manual_compact_start",
            "session_id": session_id,
        })

        try:
            result = await self.compress_with_flush(session_id, agent_id)
            if "error" in result:
                reason = str(result.get("error") or "未知原因")
                session_data = session_manager.load_session(session_id, agent_id) or {}
                messages = session_data.get("messages", []) or []
                compressed_ctx = session_data.get("compressed_context") or ""
                msg_tokens = 0
                compressed_tokens = 0
                total_tokens = 0
                threshold = 0
                keep_recent_tokens = 8000
                compressible_count = 0
                try:
                    from graph.token_counter import (
                        count_messages_tokens,
                        count_tokens,
                        resolve_compaction_threshold,
                    )
                    msg_tokens = count_messages_tokens(messages)
                    compressed_tokens = count_tokens(compressed_ctx) if compressed_ctx else 0
                    total_tokens = msg_tokens + compressed_tokens
                    threshold = resolve_compaction_threshold(agent_id)
                except Exception:
                    pass
                try:
                    compaction_cfg = resolve_agent_config(agent_id).get("compaction", {})
                    keep_recent_tokens = int(compaction_cfg.get("keepRecentTokens", 8000) or 8000)
                except Exception:
                    keep_recent_tokens = 8000
                try:
                    compressible_count = self._calc_compress_count(messages, keep_recent_tokens)
                except Exception:
                    compressible_count = 0

                suggestion = "建议：继续对话累积上下文，或降低 compaction.keepRecentTokens。"
                if reason == "消息过少，无需压缩":
                    suggestion = "建议：至少累积到 4 条以上消息后再尝试。"
                elif reason == "无足够消息可压缩":
                    if total_tokens < keep_recent_tokens:
                        suggestion = (
                            f"建议：当前总 token({total_tokens}) 小于 keepRecentTokens({keep_recent_tokens})，"
                            "可继续对话后重试，或调低 compaction.keepRecentTokens。"
                        )
                    else:
                        suggestion = (
                            "建议：当前消息结构导致可压缩段不足，"
                            "可继续对话增加历史，或调低 compaction.keepRecentTokens。"
                        )
                elif reason == "会话不存在":
                    suggestion = "建议：先发送一条消息创建会话，再执行 /compact。"

                msg = (
                    f"压缩未执行：{reason}\n"
                    f"\n当前状态（动态）:\n"
                    f"- 消息数: {len(messages)}\n"
                    f"- 消息 tokens: {msg_tokens}\n"
                    f"- 压缩上下文 tokens: {compressed_tokens}\n"
                    f"- 总 tokens: {total_tokens}\n"
                    f"- 压缩阈值(compaction threshold): {threshold}\n"
                    f"- 保留窗口(compaction.keepRecentTokens): {keep_recent_tokens}\n"
                    f"- 当前可压缩消息数: {compressible_count}\n"
                    f"\n{suggestion}"
                )
                yield {"type": "command_response", "response": msg}
                event_bus.emit(agent_id, {
                    "type": "lifecycle",
                    "event": "manual_compact_skipped",
                    "session_id": session_id,
                    "reason": result.get("error"),
                })
                yield {"type": "done", "content": msg, "session_id": session_id}
                return

            c = result.get("compress", {}) or {}
            flush = result.get("memory_flush")
            if flush is None:
                flush_msg = "记忆刷新：未触发"
            else:
                flush_text = str(flush).strip()
                flush_msg = "记忆刷新：已执行" if flush_text and flush_text != "NO_REPLY" else "记忆刷新：无新增内容"

            msg = (
                f"压缩完成。\n"
                f"- 归档消息：{c.get('archived_count', 0)} 条\n"
                f"- 剩余消息：{c.get('remaining_count', 0)} 条\n"
                f"- {flush_msg}"
            )
            yield {"type": "command_response", "response": msg}
            yield {"type": "session_compacted", "result": result}
            event_bus.emit(agent_id, {
                "type": "lifecycle",
                "event": "manual_compact_done",
                "session_id": session_id,
                "data": {
                    "archived_count": c.get("archived_count", 0),
                    "remaining_count": c.get("remaining_count", 0),
                    "memory_flush": flush is not None,
                },
            })
            yield {"type": "done", "content": msg, "session_id": session_id}
        except Exception as e:
            event_bus.emit(agent_id, {
                "type": "lifecycle",
                "event": "manual_compact_error",
                "session_id": session_id,
                "error": str(e)[:200],
            })
            yield {"type": "error", "error": f"压缩失败: {e}"}

    # ------------------------------------------------------------------
    # Memory Flush
    # ------------------------------------------------------------------

    async def run_memory_flush(
        self, session_id: str, agent_id: str
    ) -> str | None:
        try:
            llm = self.get_llm(agent_id)
        except Exception:
            return None

        flush_prompt = prompt_builder.build_memory_flush_prompt()
        flush_system = prompt_builder.build_memory_flush_system()

        tools = self._build_tools(agent_id, session_id)

        try:
            from langgraph.prebuilt import create_react_agent
            agent = create_react_agent(
                model=llm, tools=tools, prompt=flush_system,
            )
        except ImportError:
            return None

        history = session_manager.load_session_for_agent(session_id, agent_id)
        lc_messages = self._build_messages(history, flush_prompt)

        response_parts: list[str] = []
        try:
            async for event in agent.astream_events(
                {"messages": lc_messages}, version="v2"
            ):
                if event.get("event") == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        if isinstance(chunk.content, str):
                            response_parts.append(chunk.content)
        except Exception:
            return None

        result = "".join(response_parts).strip()

        if result and result != "NO_REPLY":
            session_manager.save_message(
                session_id, agent_id, "system",
                f"[记忆刷新] {result[:500]}"
            )
            audit_logger.log_memory_event(agent_id, "flush", detail=result[:200])

        return result

    # ------------------------------------------------------------------
    # Session Memory Save (session-memory hook)
    # ------------------------------------------------------------------

    async def save_session_memory(
        self, session_id: str, agent_id: str
    ) -> dict[str, Any]:
        data = session_manager.load_session(session_id, agent_id)
        if not data:
            return {"saved": False, "reason": "会话不存在"}

        messages = data.get("messages", [])
        if len(messages) < 2:
            return {"saved": False, "reason": "消息过少"}

        return await self._save_session_memory_from_messages(
            agent_id=agent_id,
            source_session_id=session_id,
            messages=messages,
        )

    async def _save_session_memory_background(
        self,
        agent_id: str,
        source_session_id: str,
        messages_snapshot: list[dict[str, Any]],
    ) -> None:
        """后台异步保存 session-memory，避免阻塞 /new 主链路。"""
        try:
            result = await self._save_session_memory_from_messages(
                agent_id=agent_id,
                source_session_id=source_session_id,
                messages=messages_snapshot,
            )
            if result.get("saved"):
                event_bus.emit(agent_id, {
                    "type": "lifecycle",
                    "event": "session_memory_saved",
                    "session_id": source_session_id,
                    "path": result.get("path"),
                })
            else:
                event_bus.emit(agent_id, {
                    "type": "lifecycle",
                    "event": "session_memory_failed",
                    "session_id": source_session_id,
                    "reason": result.get("reason", "unknown"),
                })
        except Exception as e:
            event_bus.emit(agent_id, {
                "type": "lifecycle",
                "event": "session_memory_failed",
                "session_id": source_session_id,
                "reason": str(e),
            })

    async def _save_session_memory_from_messages(
        self,
        agent_id: str,
        source_session_id: str,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            llm = self.get_llm(agent_id)
        except Exception as e:
            return {"saved": False, "reason": f"LLM 未初始化: {e}"}

        recent = messages[-30:]
        conversation_text = "\n".join(
            f"[{m.get('role', '?')}] {m.get('content', '')[:200]}"
            for m in recent
        )

        # /new 关键路径优化：
        # 1) slug 不再单独调用 LLM，避免双次模型请求造成明显延迟
        # 2) 摘要调用增加超时兜底，超时后退化到本地快速摘要
        slug = "session"

        try:
            summary_resp = await asyncio.wait_for(
                llm.ainvoke([
                    SystemMessage(content=(
                        "将以下对话历史压缩为简洁的中文摘要。\n"
                        "保留：关键决定、用户偏好、重要事件、待办事项、经验教训。\n"
                        "格式：使用 Markdown 列表，不超过 500 字。"
                    )),
                    HumanMessage(content=conversation_text),
                ]),
                timeout=25,
            )
            summary = summary_resp.content.strip()
        except Exception:
            snippets: list[str] = []
            for m in recent[-8:]:
                role = m.get("role", "?")
                content = (m.get("content", "") or "").strip().replace("\n", " ")
                if not content:
                    continue
                snippets.append(f"- [{role}] {content[:80]}")
            summary = "## 会话摘要（快速模式）\n" + ("\n".join(snippets) if snippets else "- 本轮对话已归档。")

        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"{today}-{slug}.md"
        memory_dir = resolve_agent_memory_dir(agent_id)
        memory_dir.mkdir(parents=True, exist_ok=True)
        filepath = memory_dir / filename

        content = f"# 会话记忆 — {today}\n\n{summary}\n"

        if filepath.exists():
            existing = filepath.read_text(encoding="utf-8")
            content = existing.rstrip() + "\n\n---\n\n" + content

        filepath.write_text(content, encoding="utf-8")

        indexer = self.memory_indexers.get(agent_id)
        if indexer:
            # 索引重建改为后台执行，避免阻塞 /new 主链路
            try:
                asyncio.create_task(asyncio.to_thread(indexer.rebuild_index))
            except Exception:
                pass

        audit_logger.log_memory_event(
            agent_id, "session_save", path=f"memory/{filename}",
            detail=summary[:200],
        )

        return {
            "saved": True,
            "path": f"memory/{filename}",
            "summary": summary[:300],
            "source_session_id": source_session_id,
        }

    # ------------------------------------------------------------------
    # Compress with Memory Flush + Post-Compaction
    # ------------------------------------------------------------------

    async def _summarize_with_fallback(
        self,
        agent_id: str,
        to_compress: list[dict[str, Any]],
        text_to_summarize: str,
    ) -> str:
        """摘要生成：全量重试 → 排除超大消息 → 仅记录"""
        from graph.retry import retry_async
        from graph.token_counter import count_tokens
        from graph.model_selection import resolve_agent_model, get_model_context_window

        async def _do_summarize(text: str) -> str:
            llm = self.get_llm(agent_id)
            resp = await llm.ainvoke([
                SystemMessage(content=(
                    "你是一个对话摘要生成器。请将以下对话历史压缩为简洁的中文摘要，不超过500字。"
                    "保留关键信息、决定、上下文和待办事项。"
                )),
                HumanMessage(content=text),
            ])
            return resp.content.strip()

        # 全量摘要 + 重试
        try:
            return await retry_async(
                lambda: _do_summarize(text_to_summarize),
                attempts=3,
                min_delay_ms=500,
                max_delay_ms=5000,
                jitter=0.2,
                should_retry=lambda e, _: "AbortError" not in type(e).__name__,
            )
        except Exception as full_err:
            logger.warning(f"Full summarization failed, trying partial: {full_err}")

        # 渐进降级：排除单条 > 50% context 的消息
        try:
            ref = resolve_agent_model(agent_id)
            context_window = get_model_context_window(ref)
            small_msgs: list[dict[str, Any]] = []
            oversized_notes: list[str] = []
            for m in to_compress:
                content = m.get("content", "")
                tokens = count_tokens(content) + 4
                if tokens > context_window * 0.5:
                    role = m.get("role", "message")
                    oversized_notes.append(
                        f"[Large {role} (~{tokens // 1000}K tokens) omitted from summary]"
                    )
                else:
                    small_msgs.append(m)

            if small_msgs:
                partial_text = "\n".join(
                    f"[{x.get('role', '?')}] {x.get('content', '')}"
                    for x in small_msgs
                )
                partial = await retry_async(
                    lambda: _do_summarize(partial_text),
                    attempts=2,
                    min_delay_ms=500,
                    max_delay_ms=3000,
                    jitter=0.2,
                )
                notes = "\n\n" + "\n".join(oversized_notes) if oversized_notes else ""
                return partial + notes
        except Exception as partial_err:
            logger.warning(f"Partial summarization failed: {partial_err}")

        # 最终降级：仅记录
        return (
            f"Context contained {len(to_compress)} messages. "
            "Summary unavailable due to size limits."
        )

    async def compress_with_flush(
        self, session_id: str, agent_id: str
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "memory_flush": None,
            "compress": None,
            "post_compaction": None,
        }

        agent_cfg = resolve_agent_config(agent_id)
        compaction_cfg = agent_cfg.get("compaction", {})
        do_memory_flush = compaction_cfg.get("memoryFlush", True)
        keep_recent_tokens = compaction_cfg.get("keepRecentTokens", 8000)

        data = session_manager.load_session(session_id, agent_id)
        # 仅在本压缩周期尚未 flush 时执行（避免与 astream 开头的提前 flush 重复）
        state = self.get_state(agent_id)
        if do_memory_flush and data and should_run_memory_flush(data, agent_id, state.compaction_count):
            flush_result = await self.run_memory_flush(session_id, agent_id)
            result["memory_flush"] = flush_result
            if flush_result is not None:
                session_manager.set_memory_flush_compaction_count(
                    session_id, agent_id, state.compaction_count
                )
        if not data:
            return {**result, "error": "会话不存在"}

        messages = data.get("messages", [])
        if len(messages) < 4:
            return {**result, "error": "消息过少，无需压缩"}

        from graph.token_counter import count_messages_tokens
        n = self._calc_compress_count(messages, keep_recent_tokens)
        if n < 2:
            return {**result, "error": "无足够消息可压缩"}

        to_compress = messages[:n]

        text_to_summarize = "\n".join(
            f"[{m.get('role', '?')}] {m.get('content', '')}"
            for m in to_compress
        )

        summary = await self._summarize_with_fallback(
            agent_id, to_compress, text_to_summarize
        )

        compress_result = session_manager.compress_history(
            session_id, agent_id, summary, n
        )
        result["compress"] = {"summary": summary, **compress_result}

        post_context = prompt_builder.build_post_compaction_context(agent_id)
        session_manager.save_message(session_id, agent_id, "system", post_context)
        result["post_compaction"] = "已注入"

        state = self.get_state(agent_id)
        state.compaction_count += 1

        audit_logger.log_compress(
            agent_id, session_id,
            compress_result.get("archived_count", 0),
            compress_result.get("remaining_count", 0),
        )

        return result

    @staticmethod
    def _calc_compress_count(messages: list[dict[str, Any]], keep_recent_tokens: int) -> int:
        """计算需要压缩的消息数量，保留尾部 keep_recent_tokens 的消息"""
        from graph.token_counter import count_tokens

        tail_tokens = 0
        keep_from = len(messages)

        for i in range(len(messages) - 1, -1, -1):
            msg_tokens = count_tokens(messages[i].get("content", "")) + 4
            if tail_tokens + msg_tokens > keep_recent_tokens:
                break
            tail_tokens += msg_tokens
            keep_from = i

        compress_count = keep_from
        return max(compress_count, 2) if compress_count >= 2 else 0

    # ------------------------------------------------------------------
    # Agent 注册
    # ------------------------------------------------------------------

    async def register_agent(self, agent_id: str) -> None:
        from graph.workspace import ensure_agent_workspace

        ensure_agent_workspace(agent_id)
        agent_dir = str(resolve_agent_dir(agent_id))
        self.memory_indexers[agent_id] = MemoryIndexer(agent_dir)
        self.memory_indexers[agent_id].rebuild_index()
        engine = MemorySearchEngine(agent_dir, agent_id)
        engine.rebuild_index()
        engine.start_watching()
        self.memory_search_engines[agent_id] = engine
        self._states[agent_id] = AgentState(agent_id=agent_id)


agent_manager = AgentManager()
