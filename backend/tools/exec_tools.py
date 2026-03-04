"""Execution tools: exec, python_repl"""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from config import get_exec_approval_config
from sandbox.exec_policy import check_command, get_safe_env
from sandbox.exec_approval import needs_exec_approval, needs_dangerous_tool_approval


# ---------------------------------------------------------------------------
# exec — Sandbox Shell command execution (supports user approval before execution)
# ---------------------------------------------------------------------------

class ExecInput(BaseModel):
    command: str = Field(description="要执行的 Shell 命令")
    timeout: int = Field(default=30, description="超时秒数（默认 30）")


class ExecTool(BaseTool):
    name: str = "exec"
    description: str = "在沙箱环境下执行 Shell 命令。CWD 限制在工作区内，危险命令会被拦截。"
    args_schema: type[BaseModel] = ExecInput
    root_dir: str = ""
    max_output: int = 5000
    agent_id: str = "main"

    def _do_exec(self, command: str, timeout: int) -> str:
        """Actually execute the command (after blacklist check)"""
        timeout = min(timeout, 120)
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.root_dir,
                env=get_safe_env(),
            )
            output_parts = []
            if result.stdout:
                output_parts.append(result.stdout)
            if result.stderr:
                output_parts.append(f"[stderr]\n{result.stderr}")
            output_parts.append(f"[exit_code: {result.returncode}]")
            output = "\n".join(output_parts)
        except subprocess.TimeoutExpired:
            output = f"Command timed out ({timeout}s)"
        except Exception as e:
            output = f"Execution error: {e}"

        from config import get_config
        locale = get_config().get("app", {}).get("locale", "zh-CN")

        if len(output) > self.max_output:
            truncated_msg = f"\n... [输出截断，超过 {self.max_output} 字符]" if locale == "zh-CN" else f"\n... [Output truncated, exceeded {self.max_output} chars]"
            output = output[: self.max_output] + truncated_msg
        return output

    def _run(self, command: str, timeout: int = 30) -> str:
        """Synchronous execution (no approval, used for non-streaming scenarios)"""
        from config import get_config
        locale = get_config().get("app", {}).get("locale", "zh-CN")
        safe, reason = check_command(command)
        if not safe:
            return f"命令被拒绝: {reason}" if locale == "zh-CN" else f"Command rejected: {reason}"
        return self._do_exec(command, min(timeout, 120))

    async def _arun(self, command: str, timeout: int = 30) -> str:
        """Asynchronous execution (supports approval confirmation)"""
        from config import get_config
        locale = get_config().get("app", {}).get("locale", "zh-CN")

        safe, reason = check_command(command)
        if not safe:
            return f"命令被拒绝: {reason}" if locale == "zh-CN" else f"Command rejected: {reason}"

        needs_approval, deny_reason = needs_dangerous_tool_approval(
            self.agent_id, "exec", command
        )
        if deny_reason:
            return f"命令被拒绝: {deny_reason}" if locale == "zh-CN" else f"Command rejected: {deny_reason}"

        if needs_approval:
            from graph.approval_store import approval_store
            from graph.agent import event_bus

            cfg = get_exec_approval_config()
            timeout_sec = cfg.get("ask_timeout_seconds", 60)
            input_preview = str(command)[:300] if command else ""

            approval_id = approval_store.create(
                self.agent_id, "exec", input_preview
            )
            event_bus.emit(self.agent_id, {
                "type": "lifecycle",
                "event": "approval_required",
                "approval_id": approval_id,
                "tool": "exec",
                "input_preview": input_preview,
            })

            decision = await approval_store.wait(approval_id, timeout_sec)
            if decision != "approved":
                if locale == "zh-CN":
                    reason = "用户拒绝" if decision == "denied" else "确认超时，已自动拒绝"
                    return f"命令被拒绝: {reason}"
                else:
                    reason = "User denied" if decision == "denied" else "Confirmation timed out, automatically rejected"
                    return f"Command rejected: {reason}"

        return self._do_exec(command, min(timeout, 120))


# ---------------------------------------------------------------------------
# python_repl — Python code interpreter
# ---------------------------------------------------------------------------

class PythonReplInput(BaseModel):
    code: str = Field(description="要执行的 Python 代码")


class PythonReplTool(BaseTool):
    name: str = "python_repl"
    description: str = "执行 Python 代码。适合数据处理、计算和脚本任务。"
    args_schema: type[BaseModel] = PythonReplInput
    root_dir: str = ""
    max_output: int = 5000

    def _run(self, code: str) -> str:
        import sys
        import io
        import os

        old_cwd = os.getcwd()
        old_stdout = sys.stdout
        old_stderr = sys.stderr

        try:
            os.chdir(self.root_dir)
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()

            exec_globals: dict[str, Any] = {}
            exec(code, exec_globals)

            stdout_val = sys.stdout.getvalue()
            stderr_val = sys.stderr.getvalue()
            output = stdout_val
            if stderr_val:
                output += f"\n[stderr]\n{stderr_val}"
            if not output.strip():
                output = "(无输出)"
        except Exception as e:
            output = f"执行错误: {type(e).__name__}: {e}"
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            os.chdir(old_cwd)

        if len(output) > self.max_output:
            truncated_msg = "\n... [输出截断]"
            output = output[: self.max_output] + truncated_msg
        return output


# ---------------------------------------------------------------------------
# process_list — List active processes
# ---------------------------------------------------------------------------

class ProcessListTool(BaseTool):
    name: str = "process_list"
    description: str = "列出当前系统正在运行的进程概要。可用于查找占资源的进程或排查问题。"

    def _run(self, **kwargs: Any) -> str:
        try:
            result = subprocess.run(
                "ps aux --sort=-%mem | head -20",
                shell=True, capture_output=True, text=True, timeout=10,
            )
            return result.stdout or "(无结果)"
        except Exception as e:
            return f"获取进程列表失败: {e}"


# ---------------------------------------------------------------------------
# process_kill — Terminate process
# ---------------------------------------------------------------------------

class ProcessKillInput(BaseModel):
    pid: int = Field(description="要终止的进程 PID")
    signal: str = Field(default="TERM", description="信号类型: TERM / KILL")


class ProcessKillTool(BaseTool):
    name: str = "process_kill"
    description: str = "向指定 PID 发送终止信号。默认 TERM，可选 KILL。"
    args_schema: type[BaseModel] = ProcessKillInput
    agent_id: str = "main"

    def _do_kill(self, pid: int, signal: str) -> str:
        import os as _os
        import signal as _signal
        sig = _signal.SIGTERM if signal.upper() != "KILL" else _signal.SIGKILL
        try:
            _os.kill(pid, sig)
            return f"已向 PID {pid} 发送 SIG{signal.upper()}"
        except ProcessLookupError:
            return f"进程 {pid} 不存在"
        except PermissionError:
            return f"权限不足，无法终止 PID {pid}"
        except Exception as e:
            return f"终止失败: {e}"

    def _run(self, pid: int, signal: str = "TERM") -> str:
        return self._do_kill(pid, signal)

    async def _arun(self, pid: int, signal: str = "TERM") -> str:
        input_preview = f"kill -{signal} {pid}"
        needs_approval, deny_reason = needs_dangerous_tool_approval(
            self.agent_id, "process_kill", input_preview
        )
        if deny_reason:
            return f"命令被拒绝: {deny_reason}"

        if needs_approval:
            from graph.approval_store import approval_store
            from graph.agent import event_bus

            cfg = get_exec_approval_config()
            timeout_sec = cfg.get("ask_timeout_seconds", 60)

            approval_id = approval_store.create(
                self.agent_id, "process_kill", input_preview
            )
            event_bus.emit(self.agent_id, {
                "type": "lifecycle",
                "event": "approval_required",
                "approval_id": approval_id,
                "tool": "process_kill",
                "input_preview": input_preview,
            })

            decision = await approval_store.wait(approval_id, timeout_sec)
            if decision != "approved":
                reason = "用户拒绝" if decision == "denied" else "确认超时，已自动拒绝"
                return f"命令被拒绝: {reason}"

        return self._do_kill(pid, signal)


# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------

def get_exec_tools(root_dir: str, agent_id: str = "main") -> list[BaseTool]:
    return [
        ExecTool(root_dir=root_dir, agent_id=agent_id),
        PythonReplTool(root_dir=root_dir),
        ProcessListTool(),
        ProcessKillTool(agent_id=agent_id),
    ]
