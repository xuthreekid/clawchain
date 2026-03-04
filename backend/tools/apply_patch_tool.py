"""apply_patch tool — multi-file patching"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from sandbox.fs_policy import validate_path, PathSecurityError
from tools.error_utils import format_tool_error

BEGIN_PATCH = "*** Begin Patch"
END_PATCH = "*** End Patch"
ADD_FILE = "*** Add File: "
DELETE_FILE = "*** Delete File: "
UPDATE_FILE = "*** Update File: "
MOVE_TO = "*** Move to: "
EOF_MARKER = "*** End of File"
CHANGE_CONTEXT = "@@ "
EMPTY_CONTEXT = "@@"


@dataclass
class AddHunk:
    kind: str = "add"
    path: str = ""
    contents: str = ""


@dataclass
class DeleteHunk:
    kind: str = "delete"
    path: str = ""


@dataclass
class UpdateChunk:
    change_context: str | None = None
    old_lines: list[str] = field(default_factory=list)
    new_lines: list[str] = field(default_factory=list)
    is_end_of_file: bool = False


@dataclass
class UpdateHunk:
    kind: str = "update"
    path: str = ""
    move_path: str | None = None
    chunks: list[UpdateChunk] = field(default_factory=list)


def _parse_patch(input_text: str) -> list[AddHunk | DeleteHunk | UpdateHunk]:
    lines = input_text.strip().splitlines()
    if not lines:
        raise ValueError("Patch content is empty")
    first = lines[0].strip()
    last = lines[-1].strip() if lines else ""
    if first != BEGIN_PATCH:
        raise ValueError(f"Patch must start with '{BEGIN_PATCH}'")
    if last != END_PATCH:
        raise ValueError(f"Patch must end with '{END_PATCH}'")
    inner = lines[1:-1]
    hunks: list[AddHunk | DeleteHunk | UpdateHunk] = []
    i = 0
    while i < len(inner):
        line = inner[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith(ADD_FILE):
            path = stripped[len(ADD_FILE):].strip()
            contents_lines: list[str] = []
            j = i + 1
            while j < len(inner) and inner[j].startswith("+"):
                contents_lines.append(inner[j][1:] + "\n")
                j += 1
            hunks.append(AddHunk(path=path, contents="".join(contents_lines).rstrip("\n")))
            i = j
            continue
        if stripped.startswith(DELETE_FILE):
            path = stripped[len(DELETE_FILE):].strip()
            hunks.append(DeleteHunk(path=path))
            i += 1
            continue
        if stripped.startswith(UPDATE_FILE):
            path = stripped[len(UPDATE_FILE):].strip()
            move_path: str | None = None
            j = i + 1
            if j < len(inner) and inner[j].strip().startswith(MOVE_TO):
                move_path = inner[j].strip()[len(MOVE_TO):].strip()
                j += 1
            chunks: list[UpdateChunk] = []
            while j < len(inner):
                ln = inner[j]
                ln_strip = ln.strip()
                if ln_strip.startswith("***"):
                    break
                if not ln_strip:
                    j += 1
                    continue
                chunk = UpdateChunk()
                if ln == EMPTY_CONTEXT or ln.startswith(CHANGE_CONTEXT):
                    if ln == EMPTY_CONTEXT:
                        start = 1
                    else:
                        chunk.change_context = ln[len(CHANGE_CONTEXT):].strip()
                        start = 1
                    k = j + start
                    old_l: list[str] = []
                    new_l: list[str] = []
                    while k < len(inner):
                        content = inner[k]
                        if content == EOF_MARKER:
                            chunk.is_end_of_file = True
                            k += 1
                            break
                        if not content:
                            old_l.append("")
                            new_l.append("")
                            k += 1
                            continue
                        marker = content[0] if content else ""
                        rest = content[1:]
                        if marker == " ":
                            old_l.append(rest)
                            new_l.append(rest)
                        elif marker == "+":
                            new_l.append(rest)
                        elif marker == "-":
                            old_l.append(rest)
                        else:
                            break
                        k += 1
                    chunk.old_lines = old_l
                    chunk.new_lines = new_l
                    chunks.append(chunk)
                    j = k
                else:
                    j += 1
            if not chunks:
                raise ValueError(f"Update Hunk for '{path}' is empty")
            hunks.append(UpdateHunk(path=path, move_path=move_path, chunks=chunks))
            i = j
            continue
        raise ValueError(f"Invalid hunk header: '{line}'")
    return hunks


def _seek_sequence(
    lines: list[str],
    pattern: list[str],
    start: int,
    eof: bool,
) -> int | None:
    if not pattern:
        return start
    if len(pattern) > len(lines):
        return None
    max_start = len(lines) - len(pattern)
    search_start = max_start if (eof and len(lines) >= len(pattern)) else start
    if search_start > max_start:
        return None
    for i in range(search_start, max_start + 1):
        if all(lines[i + idx] == pattern[idx] for idx in range(len(pattern))):
            return i
    for i in range(search_start, max_start + 1):
        if all(lines[i + idx].rstrip() == pattern[idx].rstrip() for idx in range(len(pattern))):
            return i
    for i in range(search_start, max_start + 1):
        if all(lines[i + idx].strip() == pattern[idx].strip() for idx in range(len(pattern))):
            return i
    return None


def _apply_update_hunk(
    file_path: Path,
    chunks: list[UpdateChunk],
    root: Path,
) -> str:
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise RuntimeError(f"Failed to read file {file_path}: {e}") from e
    original_lines = content.split("\n")
    if original_lines and original_lines[-1] == "":
        original_lines.pop()
    replacements: list[tuple[int, int, list[str]]] = []
    line_index = 0
    for chunk in chunks:
        if chunk.change_context:
            ctx_idx = _seek_sequence(original_lines, [chunk.change_context], line_index, False)
            if ctx_idx is None:
                raise ValueError(f"Context '{chunk.change_context}' not found")
            line_index = ctx_idx + 1
        if not chunk.old_lines:
            ins_idx = len(original_lines) - 1 if (
                original_lines and original_lines[-1] == ""
            ) else len(original_lines)
            replacements.append((ins_idx, 0, chunk.new_lines))
            continue
        pattern = chunk.old_lines
        new_slice = chunk.new_lines
        found = _seek_sequence(original_lines, pattern, line_index, chunk.is_end_of_file)
        if found is None and pattern and pattern[-1] == "":
            pattern = pattern[:-1]
            if new_slice and new_slice[-1] == "":
                new_slice = new_slice[:-1]
            found = _seek_sequence(original_lines, pattern, line_index, chunk.is_end_of_file)
        if found is None:
            raise ValueError("Expected lines not found:\n" + "\n".join(chunk.old_lines))
        replacements.append((found, len(pattern), new_slice))
        line_index = found + len(pattern)
    replacements.sort(key=lambda r: r[0])
    result = list(original_lines)
    for start, old_len, new_lines in reversed(replacements):
        for _ in range(old_len):
            if start < len(result):
                result.pop(start)
        for i, nl in enumerate(new_lines):
            result.insert(start + i, nl)
    out = "\n".join(result)
    if not out.endswith("\n"):
        out += "\n"
    return out


class ApplyPatchInput(BaseModel):
    input: str = Field(description="补丁内容，需包含 *** Begin Patch / *** End Patch 格式")


class ApplyPatchTool(BaseTool):
    name: str = "apply_patch"
    description: str = (
        "对多个文件应用补丁。输入需包含 *** Begin Patch 和 *** End Patch 标记。"
        "支持 *** Add File: path、*** Delete File: path、*** Update File: path。"
    )
    args_schema: type[BaseModel] = ApplyPatchInput
    root_dir: str = ""

    def _run(self, input: str = "") -> str:
        if not (input or "").strip():
            return format_tool_error("apply_patch", "Please provide patch content")
        try:
            hunks = _parse_patch(input)
        except ValueError as e:
            return format_tool_error("apply_patch", str(e))
        if not hunks:
            return format_tool_error("apply_patch", "No file operations parsed")
        root = Path(self.root_dir).resolve()
        added: list[str] = []
        modified: list[str] = []
        deleted: list[str] = []
        seen_added: set[str] = set()
        seen_modified: set[str] = set()
        seen_deleted: set[str] = set()

        for hunk in hunks:
            try:
                if isinstance(hunk, AddHunk):
                    safe = validate_path(hunk.path, self.root_dir)
                    safe.parent.mkdir(parents=True, exist_ok=True)
                    safe.write_text(hunk.contents, encoding="utf-8")
                    try:
                        disp = str(safe.relative_to(root))
                    except ValueError:
                        disp = str(safe)
                    if disp not in seen_added:
                        seen_added.add(disp)
                        added.append(disp)
                elif isinstance(hunk, DeleteHunk):
                    safe = validate_path(hunk.path, self.root_dir)
                    if safe.exists():
                        safe.unlink()
                    try:
                        disp = str(safe.relative_to(root))
                    except ValueError:
                        disp = str(safe)
                    if disp not in seen_deleted:
                        seen_deleted.add(disp)
                        deleted.append(disp)
                elif isinstance(hunk, UpdateHunk):
                    safe = validate_path(hunk.path, self.root_dir)
                    if not safe.exists():
                        return format_tool_error("apply_patch", f"Target file for update does not exist: {hunk.path}")
                    applied = _apply_update_hunk(safe, hunk.chunks, root)
                    if hunk.move_path:
                        move_safe = validate_path(hunk.move_path, self.root_dir)
                        move_safe.parent.mkdir(parents=True, exist_ok=True)
                        move_safe.write_text(applied, encoding="utf-8")
                        safe.unlink()
                        try:
                            disp = str(move_safe.relative_to(root))
                        except ValueError:
                            disp = str(move_safe)
                    else:
                        safe.write_text(applied, encoding="utf-8")
                        try:
                            disp = str(safe.relative_to(root))
                        except ValueError:
                            disp = str(safe)
                    if disp not in seen_modified:
                        seen_modified.add(disp)
                        modified.append(disp)
            except PathSecurityError as e:
                return format_tool_error("apply_patch", str(e))
            except (ValueError, RuntimeError) as e:
                return format_tool_error("apply_patch", str(e))

        lines = ["Success. Updated the following files:"]
        for f in added:
            lines.append(f"A {f}")
        for f in modified:
            lines.append(f"M {f}")
        for f in deleted:
            lines.append(f"D {f}")
        return "\n".join(lines)


def get_apply_patch_tool(root_dir: str, enabled: bool = False) -> list[BaseTool]:
    """Returns apply_patch tool if tools.exec.apply_patch.enabled is true"""
    if not enabled:
        return []
    return [ApplyPatchTool(root_dir=root_dir)]
