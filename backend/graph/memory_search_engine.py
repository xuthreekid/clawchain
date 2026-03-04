"""记忆搜索引擎 — SQLite FTS5 全文检索 + 可选向量 hybrid

- SQLite FTS5 分词索引
- 文件变更自动更新（watchdog）
- 段落级分块
- vector.enabled=false: 仅 FTS5
- vector.enabled=true: hybrid（vectorWeight + textWeight），需 sentence-transformers
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_HAS_JIEBA = False
try:
    import jieba
    _HAS_JIEBA = True
except ImportError:
    pass

_HAS_WATCHDOG = False
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _HAS_WATCHDOG = True
except ImportError:
    pass

_HAS_SENTENCE_TRANSFORMERS = False
try:
    from sentence_transformers import SentenceTransformer
    _HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    pass


def _tokenize_for_fts(text: str) -> str:
    """将文本转为空格分隔的 token 序列（FTS5 用）"""
    text_lower = text.lower()
    if _HAS_JIEBA:
        words = jieba.cut_for_search(text_lower)
        return " ".join(w.strip() for w in words if w.strip() and len(w.strip()) > 1)
    tokens = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9_]+", text_lower)
    return " ".join(t for t in tokens if len(t) > 1)


def _resolve_memory_search_config(agent_id: str) -> dict[str, Any]:
    """解析 agents.defaults.memorySearch 配置"""
    from config import get_config
    cfg = get_config()
    defaults = (cfg.get("agents") or {}).get("defaults") or {}
    ms = defaults.get("memorySearch") or {}
    store = ms.get("store") or {}
    vector = store.get("vector") or {}
    query = ms.get("query") or {}
    hybrid = query.get("hybrid") or {}
    remote = ms.get("remote") or {}
    provider = (ms.get("provider") or "local").lower()
    model = (ms.get("model") or "text-embedding-3-small").strip()
    base_url = (remote.get("baseUrl") or "").strip()
    api_key = (remote.get("apiKey") or "").strip()
    import os
    if api_key.startswith("${") and api_key.endswith("}"):
        env_key = api_key[2:-1].strip()
        api_key = os.getenv(env_key, "")
    if not api_key and provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
    has_remote = bool(base_url or api_key)
    return {
        "vector_enabled": bool(vector.get("enabled", False)),
        "hybrid_enabled": bool(hybrid.get("enabled", False)),
        "vector_weight": float(hybrid.get("vectorWeight", 0.5)),
        "text_weight": float(hybrid.get("textWeight", 0.5)),
        "provider": provider,
        "model": model or "text-embedding-3-small",
        "remote_base_url": base_url or "https://api.openai.com/v1",
        "remote_api_key": api_key,
        "use_remote": has_remote or provider in ("openai", "gemini", "voyage", "mistral"),
    }


class MemorySearchEngine:
    """基于 SQLite FTS5 的记忆搜索引擎，可选 vector/hybrid"""

    def __init__(self, agent_dir: str, agent_id: str = "main"):
        self.agent_dir = Path(agent_dir)
        self.agent_id = agent_id
        self.workspace_dir = self.agent_dir / "workspace"
        self.memory_dir = self.workspace_dir / "memory"  # memory 在 workspace 内
        self.db_path = self.agent_dir / "storage" / "memory_index" / "memory.db"
        self._lock = threading.Lock()
        self._observer = None
        self._file_hashes: dict[str, str] = {}
        self._ms_config = _resolve_memory_search_config(agent_id)
        self._vector_enabled = self._ms_config["vector_enabled"]
        self._hybrid_enabled = self._ms_config["hybrid_enabled"]
        self._embedding_model: Any = None
        self._vector_available = False
        self._use_remote = bool(self._ms_config.get("use_remote"))

        if self._vector_enabled:
            if self._use_remote:
                base_url = self._ms_config.get("remote_base_url") or "https://api.openai.com/v1"
                api_key = self._ms_config.get("remote_api_key") or ""
                if api_key:
                    self._embedding_model = {
                        "type": "remote",
                        "base_url": base_url.rstrip("/"),
                        "api_key": api_key,
                        "model": self._ms_config.get("model") or "text-embedding-3-small",
                    }
                    self._vector_available = True
                    logger.info(f"Memory vector (remote) enabled for agent {agent_id}")
                else:
                    logger.warning(f"memorySearch.remote configured but apiKey empty for {agent_id}, falling back to FTS5")
            elif _HAS_SENTENCE_TRANSFORMERS:
                try:
                    self._embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
                    self._vector_available = True
                    logger.info(f"Memory vector (local) enabled for agent {agent_id}")
                except Exception as e:
                    logger.warning(f"Memory vector init failed for {agent_id}: {e}, falling back to FTS5")
            else:
                logger.warning(
                    "memorySearch.store.vector.enabled=true but sentence-transformers not installed. "
                    "pip install sentence-transformers 或配置 memorySearch.remote 以启用向量检索。回退到 FTS5。"
                )
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                        content, source,
                        content='chunks',
                        content_rowid='id',
                        tokenize='unicode61'
                    )
                """)
            except sqlite3.OperationalError:
                pass
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source)
            """)
            if self._vector_available:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS chunks_embeddings (
                        chunk_id INTEGER PRIMARY KEY,
                        embedding BLOB NOT NULL,
                        FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
                    )
                """)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def rebuild_index(self) -> None:
        """完全重建索引"""
        with self._lock:
            md_files = self._collect_md_files()
            with self._get_conn() as conn:
                conn.execute("DELETE FROM chunks")
                if self._vector_available:
                    conn.execute("DELETE FROM chunks_embeddings")
                try:
                    conn.execute("DELETE FROM chunks_fts")
                except sqlite3.OperationalError:
                    pass
                for fp in md_files:
                    self._index_file(conn, fp)

    def update_file(self, filepath: Path) -> None:
        """增量更新单个文件"""
        if not filepath.exists() or filepath.suffix != ".md":
            return

        file_hash = self._hash_file(filepath)
        rel_path = self._rel_path(filepath)

        if self._file_hashes.get(rel_path) == file_hash:
            return

        with self._lock:
            with self._get_conn() as conn:
                if self._vector_available:
                    conn.execute(
                        "DELETE FROM chunks_embeddings WHERE chunk_id IN (SELECT id FROM chunks WHERE source = ?)",
                        (rel_path,),
                    )
                conn.execute("DELETE FROM chunks WHERE source = ?", (rel_path,))
                try:
                    conn.execute(
                        "DELETE FROM chunks_fts WHERE source = ?", (rel_path,)
                    )
                except sqlite3.OperationalError:
                    pass
                self._index_file(conn, filepath)
            self._file_hashes[rel_path] = file_hash

    def remove_file(self, filepath: Path) -> None:
        """从索引中移除文件"""
        rel_path = self._rel_path(filepath)
        with self._lock:
            with self._get_conn() as conn:
                if self._vector_available:
                    conn.execute(
                        "DELETE FROM chunks_embeddings WHERE chunk_id IN (SELECT id FROM chunks WHERE source = ?)",
                        (rel_path,),
                    )
                conn.execute("DELETE FROM chunks WHERE source = ?", (rel_path,))
                try:
                    conn.execute(
                        "DELETE FROM chunks_fts WHERE source = ?", (rel_path,)
                    )
                except sqlite3.OperationalError:
                    pass
        self._file_hashes.pop(rel_path, None)

    def search(
        self,
        query: str,
        max_results: int = 10,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        搜索：vector.enabled=false 时仅 FTS5；true 时 hybrid（vectorWeight + textWeight）。
        返回 [{source, content, start_line, end_line, score}]
        """
        if self._vector_available and (self._hybrid_enabled or not self._hybrid_enabled):
            return self._search_hybrid_or_vector(query, max_results, min_score)
        return self._search_fts_only(query, max_results, min_score)

    def _search_fts_only(
        self, query: str, max_results: int, min_score: float
    ) -> list[dict[str, Any]]:
        """仅 FTS5 搜索（vector.enabled=false 或回退）"""
        query_tokens = _tokenize_for_fts(query)
        if not query_tokens:
            return self._fallback_search(query, max_results)

        results = []
        with self._get_conn() as conn:
            try:
                rows = conn.execute("""
                    SELECT c.source, c.content, c.start_line, c.end_line,
                           rank AS fts_rank
                    FROM chunks_fts f
                    JOIN chunks c ON f.rowid = c.id
                    WHERE chunks_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (query_tokens, max_results * 2)).fetchall()

                for row in rows:
                    score = -row["fts_rank"] if row["fts_rank"] else 0
                    results.append({
                        "source": row["source"],
                        "content": row["content"],
                        "start_line": row["start_line"],
                        "end_line": row["end_line"],
                        "score": round(score, 4),
                    })
            except sqlite3.OperationalError:
                return self._fallback_search(query, max_results)

        if not results:
            return self._fallback_search(query, max_results)

        results.sort(key=lambda x: -x["score"])
        if min_score > 0:
            results = [r for r in results if r["score"] >= min_score]
        return results[:max_results]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """统一 embedding 接口：支持本地 SentenceTransformer 与远程 API"""
        if not texts:
            return []
        if isinstance(self._embedding_model, dict) and self._embedding_model.get("type") == "remote":
            return self._embed_via_remote(texts)
        if hasattr(self._embedding_model, "encode"):
            arr = self._embedding_model.encode(texts, normalize_embeddings=True)
            if hasattr(arr, "tolist"):
                return [arr[i].tolist() if hasattr(arr[i], "tolist") else list(arr[i]) for i in range(len(texts))]
            return [list(v) for v in arr]
        return []

    def _embed_via_remote(self, texts: list[str]) -> list[list[float]]:
        """调用远程 OpenAI 兼容 /embeddings API"""
        cfg = self._embedding_model
        url = f"{cfg['base_url']}/embeddings"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
        }
        body = {"model": cfg["model"], "input": texts[0] if len(texts) == 1 else texts}
        try:
            import httpx
            with httpx.Client(timeout=60.0) as client:
                r = client.post(url, json=body, headers=headers)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            logger.warning(f"Remote embedding failed: {e}")
            return []
        out = []
        for item in data.get("data", []):
            emb = item.get("embedding")
            if emb is not None:
                out.append(list(emb))
        return out

    def _search_hybrid_or_vector(
        self, query: str, max_results: int, min_score: float
    ) -> list[dict[str, Any]]:
        """vector 可用时：hybrid 合并 FTS+vector，或仅 vector。无向量数据时回退 FTS。"""
        vw = self._ms_config["vector_weight"]
        tw = self._ms_config["text_weight"]
        fts_results = []
        if self._hybrid_enabled:
            fts_results = self._search_fts_only(query, max_results * 2, 0.0)
        vecs = self._embed([query])
        query_vec = vecs[0] if vecs else None
        if query_vec is None:
            return self._search_fts_only(query, max_results, min_score)
        vec_results = self._search_vector(query_vec, max_results * 2)
        if not vec_results and not self._hybrid_enabled:
            return self._search_fts_only(query, max_results, min_score)
        if not self._hybrid_enabled:
            for r in vec_results:
                r["score"] = round(r["score"], 4)
            if min_score > 0:
                vec_results = [r for r in vec_results if r["score"] >= min_score]
            return vec_results[:max_results]
        if not vec_results:
            if min_score > 0:
                fts_results = [r for r in fts_results if r["score"] >= min_score]
            return fts_results[:max_results]
        merged = self._merge_hybrid(fts_results, vec_results, vw, tw)
        if min_score > 0:
            merged = [r for r in merged if r["score"] >= min_score]
        return merged[:max_results]

    def _search_vector(
        self, query_vec: list[float], limit: int
    ) -> list[dict[str, Any]]:
        """向量相似度搜索（余弦相似度）"""
        results = []
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT chunk_id, embedding FROM chunks_embeddings"
            ).fetchall()
        for row in rows:
            emb = json.loads(row["embedding"])
            qv = query_vec if isinstance(query_vec, list) else query_vec.tolist()
            sim = sum(a * b for a, b in zip(qv, emb))
            if sim > 0:
                with self._get_conn() as conn:
                    c = conn.execute(
                        "SELECT source, content, start_line, end_line FROM chunks WHERE id = ?",
                        (row["chunk_id"],),
                    ).fetchone()
                if c:
                    results.append({
                        "source": c["source"],
                        "content": c["content"],
                        "start_line": c["start_line"],
                        "end_line": c["end_line"],
                        "score": round(sim, 4),
                    })
        results.sort(key=lambda x: -x["score"])
        return results[:limit]

    def _merge_hybrid(
        self,
        fts_results: list[dict],
        vec_results: list[dict],
        vector_weight: float,
        text_weight: float,
    ) -> list[dict[str, Any]]:
        """合并 FTS 与 vector 结果（按 chunk 标识去重，加权得分）"""
        def key(r):
            return (r["source"], r["start_line"], r["end_line"])

        scores: dict[tuple, float] = {}
        fts_max = max((r["score"] for r in fts_results), default=1.0) or 1.0
        vec_max = max((r["score"] for r in vec_results), default=1.0) or 1.0
        for r in fts_results:
            k = key(r)
            norm = r["score"] / fts_max if fts_max else 0
            scores[k] = scores.get(k, 0) + text_weight * norm
        for r in vec_results:
            k = key(r)
            norm = r["score"] / vec_max if vec_max else 0
            scores[k] = scores.get(k, 0) + vector_weight * norm
        seen = set()
        merged = []
        for r in fts_results + vec_results:
            k = key(r)
            if k in seen:
                continue
            seen.add(k)
            merged.append({
                **r,
                "score": round(scores.get(k, 0), 4),
            })
        merged.sort(key=lambda x: -x["score"])
        return merged

    def _fallback_search(
        self, query: str, max_results: int
    ) -> list[dict[str, Any]]:
        """关键词回退搜索"""
        query_lower = query.lower()
        query_words = set(re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9_]+", query_lower))
        if not query_words:
            return []

        results = []
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT source, content, start_line, end_line FROM chunks"
            ).fetchall()

        for row in rows:
            content_lower = row["content"].lower()
            matches = sum(1 for w in query_words if w in content_lower)
            if matches > 0:
                score = matches / len(query_words)
                results.append({
                    "source": row["source"],
                    "content": row["content"],
                    "start_line": row["start_line"],
                    "end_line": row["end_line"],
                    "score": round(score, 4),
                })

        results.sort(key=lambda x: -x["score"])
        return results[:max_results]

    def _index_file(self, conn: sqlite3.Connection, filepath: Path) -> None:
        try:
            text = filepath.read_text(encoding="utf-8")
        except Exception:
            return

        rel_path = self._rel_path(filepath)
        import time
        now = time.time()

        chunks = self._split_paragraphs(text)
        # 批量 embedding：一次性调用 _embed，减少远程 API 请求次数
        vecs: list[list[float]] = []
        if self._vector_available and self._embedding_model and chunks:
            try:
                texts = [c["text"] for c in chunks]
                vecs = self._embed(texts) or []
            except Exception as e:
                logger.debug(f"Batch embedding failed: {e}")
        for i, chunk in enumerate(chunks):
            content_hash = hashlib.md5(chunk["text"].encode()).hexdigest()
            cursor = conn.execute(
                """INSERT INTO chunks (source, start_line, end_line, content, content_hash, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (rel_path, chunk["start_line"], chunk["end_line"],
                 chunk["text"], content_hash, now),
            )
            row_id = cursor.lastrowid
            tokenized = _tokenize_for_fts(chunk["text"])
            if tokenized:
                try:
                    conn.execute(
                        "INSERT INTO chunks_fts(rowid, content, source) VALUES (?, ?, ?)",
                        (row_id, tokenized, rel_path),
                    )
                except sqlite3.OperationalError:
                    pass
            if self._vector_available and vecs and i < len(vecs):
                try:
                    conn.execute(
                        "INSERT INTO chunks_embeddings (chunk_id, embedding) VALUES (?, ?)",
                        (row_id, json.dumps(vecs[i])),
                    )
                except Exception as e:
                    logger.debug(f"Embedding write failed for chunk: {e}")

        self._file_hashes[rel_path] = self._hash_file(filepath)

    def _split_paragraphs(self, text: str) -> list[dict[str, Any]]:
        chunks = []
        lines = text.splitlines()
        current: list[str] = []
        chunk_start = 1

        for i, line in enumerate(lines, 1):
            if line.strip() == "" and current:
                chunk_text = "\n".join(current)
                if chunk_text.strip():
                    chunks.append({
                        "text": chunk_text.strip(),
                        "start_line": chunk_start,
                        "end_line": i - 1,
                    })
                current = []
                chunk_start = i + 1
            else:
                if not current:
                    chunk_start = i
                current.append(line)

        if current:
            chunk_text = "\n".join(current)
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text.strip(),
                    "start_line": chunk_start,
                    "end_line": chunk_start + len(current) - 1,
                })

        return chunks

    def _collect_md_files(self) -> list[Path]:
        files = []
        memory_md = self.workspace_dir / "MEMORY.md"
        if memory_md.exists():
            files.append(memory_md)
        if self.memory_dir.exists():
            files.extend(sorted(self.memory_dir.rglob("*.md"), reverse=True))
        return files

    def _rel_path(self, filepath: Path) -> str:
        try:
            return str(filepath.relative_to(self.agent_dir))
        except ValueError:
            return str(filepath)

    @staticmethod
    def _hash_file(filepath: Path) -> str:
        try:
            return hashlib.md5(filepath.read_bytes()).hexdigest()
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # 文件监听 (watchdog)
    # ------------------------------------------------------------------

    def start_watching(self) -> None:
        if not _HAS_WATCHDOG:
            logger.debug("watchdog not installed, skipping file watch")
            return

        handler = _MemoryFileHandler(self)
        self._observer = Observer()

        for watch_dir in [self.memory_dir, self.workspace_dir]:
            if watch_dir.exists():
                self._observer.schedule(handler, str(watch_dir), recursive=True)

        self._observer.daemon = True
        self._observer.start()
        logger.info(f"Memory file watcher started for {self.agent_dir}")

    def stop_watching(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None


if _HAS_WATCHDOG:
    class _MemoryFileHandler(FileSystemEventHandler):
        def __init__(self, engine: MemorySearchEngine):
            self.engine = engine

        def on_modified(self, event):
            if event.is_directory:
                return
            fp = Path(event.src_path)
            if fp.suffix == ".md":
                self.engine.update_file(fp)

        def on_created(self, event):
            if event.is_directory:
                return
            fp = Path(event.src_path)
            if fp.suffix == ".md":
                self.engine.update_file(fp)

        def on_deleted(self, event):
            if event.is_directory:
                return
            fp = Path(event.src_path)
            if fp.suffix == ".md":
                self.engine.remove_file(fp)
