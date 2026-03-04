"""Memory tools: memory_search, memory_get

memory_search: Use SQLite FTS5 to search MEMORY.md and memory/*.md
memory_get: Safely read specified lines from memory files
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# memory_search — FTS5 full-text search for memory files
# ---------------------------------------------------------------------------

class MemorySearchInput(BaseModel):
    query: str = Field(description="搜索查询")
    max_results: int = Field(default=6, description="最多返回结果数（默认 6）")
    min_score: float = Field(default=0.0, description="最低相关度阈值（默认 0）")


class MemorySearchTool(BaseTool):
    name: str = "memory_search"
    description: str = (
        "记忆召回核心步骤：在 MEMORY.md 和 memory/*.md 中搜索。"
        "使用 SQLite FTS5 全文搜索引擎。"
        "返回带路径和行号的相关片段。回答关于过往工作、决策、偏好等问题前必须先使用。"
    )
    args_schema: type[BaseModel] = MemorySearchInput
    agent_dir: str = ""

    def _run(self, query: str, max_results: int = 6, min_score: float = 0.0) -> str:
        try:
            from graph.agent import agent_manager
            engine = agent_manager.memory_search_engines.get(
                self._resolve_agent_id()
            )
        except Exception:
            engine = None

        if engine:
            return self._search_with_engine(engine, query, max_results, min_score)

        return self._search_fallback(query, max_results, min_score)

    def _resolve_agent_id(self) -> str:
        agent_root = Path(self.agent_dir)
        return agent_root.name if agent_root.parent.name == "agents" else "main"

    def _search_with_engine(self, engine, query: str, max_results: int, min_score: float) -> str:
        results = engine.search(query, max_results=max_results, min_score=min_score)
        from config import get_config
        locale = get_config().get("app", {}).get("locale", "zh-CN")
        if not results:
            return f"未找到与 '{query}' 相关的记忆。" if locale == "zh-CN" else f"No memories found related to '{query}'."

        lines_out = []
        for r in results:
            source_label = "来源" if locale == "zh-CN" else "Source"
            score_label = "相关度" if locale == "zh-CN" else "Relevance"
            lines_out.append(
                f"--- {source_label}: {r['source']}#L{r['start_line']}-L{r['end_line']} "
                f"({score_label}: {r['score']:.2f}) ---"
            )
            preview = r["content"][:500]
            if len(r["content"]) > 500:
                preview += "..."
            lines_out.append(preview)
            lines_out.append("")
        return "\n".join(lines_out)

    def _search_fallback(self, query: str, max_results: int, min_score: float) -> str:
        """Fallback search when search engine is unavailable"""
        import re

        agent_root = Path(self.agent_dir)
        workspace_dir = agent_root / "workspace"
        memory_dir = workspace_dir / "memory"  # memory 在 workspace 内

        md_files: list[Path] = []
        workspace_memory = workspace_dir / "MEMORY.md"
        if workspace_memory.exists():
            md_files.append(workspace_memory)
        if memory_dir.exists():
            md_files.extend(sorted(memory_dir.rglob("*.md"), reverse=True))

        from config import get_config
        locale = get_config().get("app", {}).get("locale", "zh-CN")
        if not md_files:
            return (
                "未找到记忆文件。请先创建 memory/ 目录和 MEMORY.md。" 
                if locale == "zh-CN" else 
                "No memory files found. Please create the memory/ directory and MEMORY.md first."
            )

        query_lower = query.lower()
        query_words = set(re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9_]+", query_lower))
        if not query_words:
            return (
                f"查询 '{query}' 无法分词。请使用更具体的关键词。"
                if locale == "zh-CN" else 
                f"Query '{query}' could not be tokenized. Please use more specific keywords."
            )

        results: list[tuple[float, str, str, int]] = []

        for fp in md_files:
            try:
                text = fp.read_text(encoding="utf-8")
            except Exception:
                continue

            if fp == workspace_memory:
                rel_path = "MEMORY.md"
            else:
                try:
                    rel_path = str(fp.relative_to(agent_root))
                except ValueError:
                    rel_path = str(fp)

            paragraphs = text.split("\n\n")
            line = 1
            for para in paragraphs:
                if para.strip():
                    para_lower = para.lower()
                    matches = sum(1 for w in query_words if w in para_lower)
                    if matches > 0:
                        score = matches / len(query_words)
                        if score >= min_score:
                            results.append((score, rel_path, para.strip(), line))
                line += para.count("\n") + 2

        results.sort(key=lambda x: -x[0])
        results = results[:max_results]

        if not results:
            return f"未找到与 '{query}' 相关的记忆。" if locale == "zh-CN" else f"No memories found related to '{query}'."

        lines_out = []
        for score, source, text, start in results:
            source_label = "来源" if locale == "zh-CN" else "Source"
            score_label = "相关度" if locale == "zh-CN" else "Relevance"
            lines_out.append(f"--- {source_label}: {source}#L{start} ({score_label}: {score:.2f}) ---")
            preview = text[:500]
            if len(text) > 500:
                preview += "..."
            lines_out.append(preview)
            lines_out.append("")
        return "\n".join(lines_out)


# ---------------------------------------------------------------------------
# memory_get — Read specified lines from memory files
# ---------------------------------------------------------------------------

class MemoryGetInput(BaseModel):
    path: str = Field(description="记忆文件路径（如 'memory/MEMORY.md' 或 'memory/2026-02-27.md'）")
    start_line: int = Field(default=1, description="起始行号（1-based，默认 1）")
    end_line: int = Field(default=0, description="结束行号（0 表示到文件末尾）")


class MemoryGetTool(BaseTool):
    name: str = "memory_get"
    description: str = (
        "安全读取 MEMORY.md 或 memory/*.md 的指定行范围。"
        "用于 memory_search 后获取完整内容。"
        "文件不存在时返回空文本而非报错。"
    )
    args_schema: type[BaseModel] = MemoryGetInput
    agent_dir: str = ""

    def _run(self, path: str, start_line: int = 1, end_line: int = 0) -> str:
        agent_root = Path(self.agent_dir).resolve()

        workspace_dir = agent_root / "workspace"
        if path in ("MEMORY.md", "workspace/MEMORY.md"):
            target = workspace_dir / "MEMORY.md"
        elif path.startswith("memory/"):
            target = (workspace_dir / path).resolve()
        else:
            target = (agent_root / path).resolve()

        from config import get_config
        locale = get_config().get("app", {}).get("locale", "zh-CN")
        try:
            target.relative_to(agent_root)
        except ValueError:
            return "错误: 路径逃逸出 Agent 目录" if locale == "zh-CN" else "Error: Path escaped agent directory"

        if not target.exists():
            return ""

        try:
            lines = target.read_text(encoding="utf-8").splitlines()
        except Exception as e:
            err_msg = "读取失败" if locale == "zh-CN" else "Read failed"
            return f"错误: {err_msg} — {e}" if locale == "zh-CN" else f"Error: {err_msg} — {e}"

        start = max(start_line - 1, 0)
        end_idx = end_line if end_line > 0 else len(lines)
        end_idx = min(end_idx, len(lines))
        selected = lines[start:end_idx]

        numbered = [f"{start + i + 1:>6}|{line}" for i, line in enumerate(selected)]
        return "\n".join(numbered) if numbered else ("(空文件)" if locale == "zh-CN" else "(Empty file)")


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------

def get_memory_tools(agent_dir: str) -> list[BaseTool]:
    """Returns memory tool instances"""
    return [
        MemorySearchTool(agent_dir=agent_dir),
        MemoryGetTool(agent_dir=agent_dir),
    ]
