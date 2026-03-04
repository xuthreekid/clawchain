"""知识库工具 x1: search_knowledge_base"""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class KnowledgeSearchInput(BaseModel):
    query: str = Field(description="搜索查询")
    top_k: int = Field(default=3, description="返回结果数量（默认 3）")


class KnowledgeSearchTool(BaseTool):
    name: str = "search_knowledge_base"
    description: str = (
        "在 knowledge/ 目录中搜索知识库文档（PDF/MD/TXT）。"
        "使用语义检索返回最相关的文档片段。"
    )
    args_schema: type[BaseModel] = KnowledgeSearchInput
    agent_dir: str = ""

    def _run(self, query: str, top_k: int = 3) -> str:
        from config import get_config
        locale = get_config().get("app", {}).get("locale", "zh-CN")
        knowledge_dir = Path(self.agent_dir) / "knowledge"
        if not knowledge_dir.exists() or not any(knowledge_dir.iterdir()):
            return (
                "知识库目录为空。请将文档放入 knowledge/ 目录。"
                if locale == "zh-CN" else
                "Knowledge base directory is empty. Please put documents in the knowledge/ directory."
            )

        results: list[tuple[float, str, str]] = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for fp in knowledge_dir.rglob("*"):
            if not fp.is_file():
                continue
            if fp.suffix.lower() not in (".md", ".txt", ".text", ".rst"):
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            chunks = self._split_into_chunks(text, chunk_size=512, overlap=64)
            rel_path = fp.relative_to(Path(self.agent_dir))

            for chunk in chunks:
                chunk_lower = chunk.lower()
                score = sum(1 for w in query_words if w in chunk_lower)
                if score > 0:
                    results.append((score, str(rel_path), chunk.strip()))

        results.sort(key=lambda x: -x[0])
        results = results[:top_k]

        if not results:
            return (
                f"未在知识库中找到与 '{query}' 相关的内容。"
                if locale == "zh-CN" else
                f"No content related to '{query}' was found in the knowledge base."
            )

        lines = []
        for score, path, chunk in results:
            source_label = "来源" if locale == "zh-CN" else "Source"
            score_label = "相关度" if locale == "zh-CN" else "Relevance"
            lines.append(f"--- {source_label}: {path} ({score_label}: {score}) ---")
            lines.append(chunk[:1000])
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _split_into_chunks(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i : i + chunk_size])
            chunks.append(chunk)
            i += chunk_size - overlap
        return chunks


def get_knowledge_tools(agent_dir: str) -> list[BaseTool]:
    return [
        KnowledgeSearchTool(agent_dir=agent_dir),
    ]
