"""文件操作工具 x6: read, write, edit, grep, find, ls"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from sandbox.fs_policy import (
    validate_path, validate_path_relaxed, validate_path_for_fs, PathSecurityError,
    write_atomic, is_protected_file,
)
from sandbox.undo_stack import undo_stack
from tools.error_utils import format_tool_error


def _resolve_read_path(path: str, root_dir: str) -> Path | None:
    """解析读取路径。技能已同步到 workspace/skills/，通过 skills/xxx 访问。"""
    return None


# ---------------------------------------------------------------------------
# read — 读取文件内容（支持行号范围）
# ---------------------------------------------------------------------------

class ReadInput(BaseModel):
    path: str = Field(description="要读取的文件路径（相对于工作区）")
    offset: int | None = Field(default=None, description="起始行号（1-based）")
    limit: int | None = Field(default=None, description="要读取的行数")


def _get_fs_readonly_config() -> tuple[tuple[str, ...], Path | None]:
    """从 config 读取 tools.fs.readonly_dirs 和 project_root"""
    try:
        from config import get_config, PROJECT_ROOT
        cfg = get_config()
        rd = cfg.get("tools", {}).get("fs", {}).get("readonly_dirs") or []
        dirs = tuple(rd) if isinstance(rd, (list, tuple)) else ()
        return (dirs, PROJECT_ROOT)
    except Exception:
        return ((), None)


class ReadTool(BaseTool):
    name: str = "read"
    description: str = "读取文件内容。支持 offset（起始行号，1-based）和 limit（行数）参数做行号范围读取。"
    args_schema: type[BaseModel] = ReadInput
    root_dir: str = ""

    def _run(self, path: str, offset: int | None = None, limit: int | None = None) -> str:
        safe_path = _resolve_read_path(path, self.root_dir)
        if safe_path is None:
            try:
                readonly_dirs, project_root = _get_fs_readonly_config()
                if readonly_dirs and project_root is not None:
                    safe_path = validate_path_for_fs(path, self.root_dir, readonly_dirs, project_root, is_write=False)
                else:
                    safe_path = validate_path(path, self.root_dir)
            except PathSecurityError as e:
                return format_tool_error("read", e)

        if not safe_path.exists():
            return format_tool_error("read", f"文件不存在 '{path}'")
        if not safe_path.is_file():
            return format_tool_error("read", f"'{path}' 不是文件")

        try:
            content = safe_path.read_text(encoding="utf-8")
        except Exception as e:
            return format_tool_error("read", f"读取文件失败 — {e}")

        lines = content.splitlines()

        if offset is not None or limit is not None:
            start = max((offset or 1) - 1, 0)
            end = start + (limit or len(lines)) if limit else len(lines)
            selected = lines[start:end]
            numbered = [f"{start + i + 1:>6}|{line}" for i, line in enumerate(selected)]
            return "\n".join(numbered)

        numbered = [f"{i + 1:>6}|{line}" for i, line in enumerate(lines)]
        return "\n".join(numbered)


# ---------------------------------------------------------------------------
# write — 创建或覆盖文件
# ---------------------------------------------------------------------------

class WriteInput(BaseModel):
    path: str = Field(description="文件路径（相对于工作区）")
    content: str = Field(description="要写入的内容")


class WriteTool(BaseTool):
    name: str = "write"
    description: str = "创建或覆盖文件。如果父目录不存在会自动创建。"
    args_schema: type[BaseModel] = WriteInput
    root_dir: str = ""
    agent_id: str = "main"

    def _run(self, path: str, content: str) -> str:
        try:
            readonly_dirs, project_root = _get_fs_readonly_config()
            if readonly_dirs and project_root is not None:
                safe_path = validate_path_for_fs(path, self.root_dir, readonly_dirs, project_root, is_write=True)
            else:
                safe_path = validate_path_relaxed(path, self.root_dir)
        except PathSecurityError as e:
            return format_tool_error("write", e)

        if is_protected_file(safe_path):
            return format_tool_error("write", f"拒绝写入受保护文件类型: {safe_path.suffix}")

        try:
            was_new = not safe_path.exists()
            old_content = None
            if not was_new:
                try:
                    old_content = safe_path.read_text(encoding="utf-8")
                except Exception:
                    pass

            write_atomic(safe_path, content)

            undo_stack.record_write(
                self.agent_id,
                str(safe_path),
                old_content,
                content,
                was_new_file=was_new,
            )

            return f"已写入 {safe_path.relative_to(Path(self.root_dir).resolve())} ({len(content)} 字符)"
        except Exception as e:
            return format_tool_error("write", f"写入失败 — {e}")


# ---------------------------------------------------------------------------
# edit — 精确查找替换
# ---------------------------------------------------------------------------

class EditInput(BaseModel):
    path: str = Field(description="文件路径（相对于工作区）")
    old_text: str = Field(description="要替换的原始文本（必须在文件中唯一匹配）")
    new_text: str = Field(description="替换后的文本")


class EditTool(BaseTool):
    name: str = "edit"
    description: str = "精确编辑文件：查找 old_text 并替换为 new_text。old_text 必须在文件中唯一出现。"
    args_schema: type[BaseModel] = EditInput
    root_dir: str = ""
    agent_id: str = "main"

    def _run(self, path: str, old_text: str, new_text: str) -> str:
        try:
            readonly_dirs, project_root = _get_fs_readonly_config()
            if readonly_dirs and project_root is not None:
                safe_path = validate_path_for_fs(path, self.root_dir, readonly_dirs, project_root, is_write=True)
            else:
                safe_path = validate_path(path, self.root_dir)
        except PathSecurityError as e:
            return format_tool_error("edit", e)

        if not safe_path.exists():
            return format_tool_error("edit", f"文件不存在 '{path}'")

        try:
            content = safe_path.read_text(encoding="utf-8")
        except Exception as e:
            return format_tool_error("edit", f"读取失败 — {e}")

        count = content.count(old_text)
        if count == 0:
            return format_tool_error("edit", "old_text 未在文件中找到。请确保文本精确匹配（包括空格和缩进）。")
        if count > 1:
            return format_tool_error("edit", f"old_text 在文件中出现了 {count} 次，需要唯一匹配。请提供更多上下文以精确定位。")

        new_content = content.replace(old_text, new_text, 1)
        write_atomic(safe_path, new_content)

        undo_stack.record_edit(
            self.agent_id,
            str(safe_path),
            content,
            new_content,
        )

        return f"已编辑 {path}（替换了 1 处匹配）"


# ---------------------------------------------------------------------------
# grep — 正则搜索文件内容
# ---------------------------------------------------------------------------

class GrepInput(BaseModel):
    pattern: str = Field(description="正则表达式模式")
    path: str = Field(default=".", description="搜索目录或文件路径（相对于工作区）")
    include: str | None = Field(default=None, description="文件名 glob 过滤（如 '*.py'）")


class GrepTool(BaseTool):
    name: str = "grep"
    description: str = "使用正则表达式搜索文件内容。支持 include 参数做文件名过滤（如 '*.py'）。"
    args_schema: type[BaseModel] = GrepInput
    root_dir: str = ""

    def _run(self, pattern: str, path: str = ".", include: str | None = None) -> str:
        try:
            readonly_dirs, project_root = _get_fs_readonly_config()
            if readonly_dirs and project_root is not None:
                safe_path = validate_path_for_fs(path, self.root_dir, readonly_dirs, project_root, is_write=False)
            else:
                safe_path = validate_path(path, self.root_dir)
        except PathSecurityError as e:
            return f"错误: {e}"

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"错误: 无效的正则表达式 — {e}"

        results: list[str] = []
        max_results = 100
        root = Path(self.root_dir).resolve()

        if safe_path.is_file():
            files = [safe_path]
        else:
            glob_pattern = include or "*"
            files = list(safe_path.rglob(glob_pattern))

        for fp in files:
            if not fp.is_file():
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    rel = fp.relative_to(root)
                    results.append(f"{rel}:{i}:{line}")
                    if len(results) >= max_results:
                        results.append(f"... 结果过多，已截断（最多 {max_results} 条）")
                        return "\n".join(results)

        if not results:
            return f"未找到匹配 '{pattern}' 的内容。"
        return "\n".join(results)


# ---------------------------------------------------------------------------
# find — glob 查找文件
# ---------------------------------------------------------------------------

class FindInput(BaseModel):
    glob_pattern: str = Field(description="glob 模式（如 '**/*.py', '*.md'）")
    path: str = Field(default=".", description="搜索起始目录（相对于工作区）")


class FindTool(BaseTool):
    name: str = "find"
    description: str = "按 glob 模式递归查找文件，返回文件路径列表。"
    args_schema: type[BaseModel] = FindInput
    root_dir: str = ""

    def _run(self, glob_pattern: str, path: str = ".") -> str:
        try:
            readonly_dirs, project_root = _get_fs_readonly_config()
            if readonly_dirs and project_root is not None:
                safe_path = validate_path_for_fs(path, self.root_dir, readonly_dirs, project_root, is_write=False)
            else:
                safe_path = validate_path(path, self.root_dir)
        except PathSecurityError as e:
            return f"错误: {e}"

        if not safe_path.is_dir():
            return f"错误: '{path}' 不是目录"

        root = Path(self.root_dir).resolve()
        matches = sorted(safe_path.rglob(glob_pattern))
        if not matches:
            return f"未找到匹配 '{glob_pattern}' 的文件。"

        lines = []
        for m in matches[:200]:
            rel = m.relative_to(root)
            suffix = "/" if m.is_dir() else ""
            lines.append(f"{rel}{suffix}")
        if len(matches) > 200:
            lines.append(f"... 共 {len(matches)} 个结果，已截断")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# ls — 列出目录内容
# ---------------------------------------------------------------------------

class LsInput(BaseModel):
    path: str = Field(default=".", description="目录路径（相对于工作区）")


class LsTool(BaseTool):
    name: str = "ls"
    description: str = "列出目录内容，显示文件类型和大小。"
    args_schema: type[BaseModel] = LsInput
    root_dir: str = ""

    def _run(self, path: str = ".") -> str:
        try:
            readonly_dirs, project_root = _get_fs_readonly_config()
            if readonly_dirs and project_root is not None:
                safe_path = validate_path_for_fs(path, self.root_dir, readonly_dirs, project_root, is_write=False)
            else:
                safe_path = validate_path(path, self.root_dir)
        except PathSecurityError as e:
            return f"错误: {e}"

        if not safe_path.is_dir():
            return f"错误: '{path}' 不是目录"

        entries = sorted(safe_path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        if not entries:
            return "(空目录)"

        lines = []
        for entry in entries:
            if entry.is_dir():
                lines.append(f"  {entry.name}/")
            else:
                size = entry.stat().st_size
                if size < 1024:
                    size_str = f"{size}B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f}KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f}MB"
                lines.append(f"  {entry.name}  ({size_str})")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------

def get_file_tools(root_dir: str, agent_id: str = "main") -> list[BaseTool]:
    from config import get_config
    from tools.apply_patch_tool import get_apply_patch_tool

    tools: list[BaseTool] = [
        ReadTool(root_dir=root_dir),
        WriteTool(root_dir=root_dir, agent_id=agent_id),
        EditTool(root_dir=root_dir, agent_id=agent_id),
        GrepTool(root_dir=root_dir),
        FindTool(root_dir=root_dir),
        LsTool(root_dir=root_dir),
    ]
    cfg = get_config()
    apply_patch_enabled = cfg.get("tools", {}).get("exec", {}).get("apply_patch", {}).get("enabled", False)
    tools.extend(get_apply_patch_tool(root_dir, enabled=bool(apply_patch_enabled)))
    return tools
