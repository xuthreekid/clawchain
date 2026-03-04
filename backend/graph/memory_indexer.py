"""MEMORY.md 向量索引 — 用于 RAG 模式的语义检索"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


class MemoryIndexer:
    """
    为 memory/MEMORY.md 构建简易的关键词索引。
    生产环境中可替换为 LlamaIndex 向量索引。
    """

    def __init__(self, agent_dir: str):
        self.agent_dir = Path(agent_dir)
        self.workspace_dir = self.agent_dir / "workspace"
        self.memory_dir = self.workspace_dir / "memory"  # memory 在 workspace 内
        self._last_md5: str | None = None
        self._chunks: list[dict[str, Any]] = []

    def _compute_md5(self) -> str:
        memory_file = self.workspace_dir / "MEMORY.md"
        if not memory_file.exists():
            return ""
        content = memory_file.read_bytes()
        return hashlib.md5(content).hexdigest()

    def rebuild_index(self) -> None:
        """重建索引"""
        self._chunks = []
        md_files: list[Path] = []
        if (self.workspace_dir / "MEMORY.md").exists():
            md_files.append(self.workspace_dir / "MEMORY.md")
        if self.memory_dir.exists():
            md_files.extend(sorted(self.memory_dir.rglob("*.md"), reverse=True))

        for fp in md_files:
            try:
                text = fp.read_text(encoding="utf-8")
            except Exception:
                continue

            rel_path = str(fp.relative_to(self.agent_dir))
            paragraphs = text.split("\n\n")
            line_no = 1
            for para in paragraphs:
                if para.strip():
                    self._chunks.append({
                        "text": para.strip(),
                        "source": rel_path,
                        "line": line_no,
                    })
                line_no += para.count("\n") + 2

        self._last_md5 = self._compute_md5()

    def _maybe_rebuild(self) -> None:
        current_md5 = self._compute_md5()
        if current_md5 != self._last_md5:
            self.rebuild_index()

    def retrieve(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """基于关键词的检索（可替换为向量检索）"""
        self._maybe_rebuild()

        if not self._chunks:
            return []

        query_words = set(query.lower().split())
        scored = []
        for chunk in self._chunks:
            text_lower = chunk["text"].lower()
            score = sum(1 for w in query_words if w in text_lower)
            if score > 0:
                scored.append({
                    "text": chunk["text"],
                    "score": score,
                    "source": chunk["source"],
                    "line": chunk["line"],
                })

        scored.sort(key=lambda x: -x["score"])
        return scored[:top_k]
