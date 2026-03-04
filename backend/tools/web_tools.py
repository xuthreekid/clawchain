"""Web tools: web_search, web_fetch"""

from __future__ import annotations

import logging

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# web_search — Web search (supports multiple backends, auto-fallback)
# ---------------------------------------------------------------------------

class WebSearchInput(BaseModel):
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=5, description="最大结果数（默认 5）")


def _search_duckduckgo(query: str, max_results: int) -> list[dict] | str:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return "duckduckgo-search not installed"
    try:
        with DDGS(timeout=8) as ddgs:
            return list(ddgs.text(query, max_results=min(max_results, 10)))
    except Exception as e:
        return f"DuckDuckGo search failed: {e}"


def _search_brave(query: str, max_results: int, api_key: str) -> list[dict] | str:
    try:
        import httpx
    except ImportError:
        return "httpx not installed"
    try:
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": min(max_results, 20)},
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("web", {}).get("results", []):
            results.append({
                "title": item.get("title", ""),
                "body": item.get("description", ""),
                "href": item.get("url", ""),
            })
        return results
    except Exception as e:
        return f"Brave search failed: {e}"


def _search_searxng(query: str, max_results: int, base_url: str) -> list[dict] | str:
    try:
        import httpx
    except ImportError:
        return "httpx not installed"
    try:
        url = base_url.rstrip("/") + "/search"
        resp = httpx.get(
            url,
            params={"q": query, "format": "json", "pageno": 1},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("results", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "body": item.get("content", ""),
                "href": item.get("url", ""),
            })
        return results
    except Exception as e:
        return f"SearXNG search failed: {e}"


def _format_results(results: list[dict], query: str) -> str:
    if not results:
        return f"No search results found for '{query}'."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. **{r.get('title', 'No Title')}**")
        lines.append(f"   {r.get('body', 'No Summary')}")
        lines.append(f"   Link: {r.get('href', 'No Link')}")
        lines.append("")
    return "\n".join(lines)


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = "搜索网络，返回标题、摘要和链接。支持多种搜索后端，自动回退。"
    args_schema: type[BaseModel] = WebSearchInput

    def _run(self, query: str, max_results: int = 5) -> str:
        from config import get_config
        cfg = get_config()
        web_cfg = cfg.get("tools", {}).get("web", {}).get("search", {})
        provider = web_cfg.get("provider", "duckduckgo")
        api_key = web_cfg.get("apiKey", "")
        base_url = web_cfg.get("baseUrl", "")

        errors: list[str] = []

        if provider == "brave" and api_key:
            result = _search_brave(query, max_results, api_key)
            if isinstance(result, list):
                return _format_results(result, query)
            errors.append(result)

        elif provider == "searxng" and base_url:
            result = _search_searxng(query, max_results, base_url)
            if isinstance(result, list):
                return _format_results(result, query)
            errors.append(result)

        else:
            result = _search_duckduckgo(query, max_results)
            if isinstance(result, list):
                return _format_results(result, query)
            errors.append(result)

        # 回退: 如果主后端失败，尝试 DuckDuckGo（非 DuckDuckGo 时）
        if provider != "duckduckgo":
            logger.info(f"Primary search backend {provider} failed, falling back to DuckDuckGo")
            result = _search_duckduckgo(query, max_results)
            if isinstance(result, list):
                return _format_results(result, query)
            errors.append(result)

        return f"All search backends failed:\n" + "\n".join(f"- {e}" for e in errors)


# ---------------------------------------------------------------------------
# web_fetch — Fetch web content
# ---------------------------------------------------------------------------

class WebFetchInput(BaseModel):
    url: str = Field(description="要抓取的 URL")


class WebFetchTool(BaseTool):
    name: str = "web_fetch"
    description: str = "从指定 URL 抓取网页内容，自动将 HTML 转为 Markdown 格式。"
    args_schema: type[BaseModel] = WebFetchInput
    max_output: int = 8000

    def _run(self, url: str) -> str:
        try:
            import httpx
        except ImportError:
            return "Error: httpx not installed"

        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                resp = client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; ClawChain/1.0)"
                })
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")

                if "json" in content_type:
                    text = resp.text
                elif "html" in content_type or "text" in content_type:
                    try:
                        import html2text
                        h = html2text.HTML2Text()
                        h.ignore_links = False
                        h.ignore_images = True
                        h.body_width = 0
                        text = h.handle(resp.text)
                    except ImportError:
                        text = resp.text
                else:
                    text = resp.text

        except httpx.TimeoutException:
            return f"Request timeout (15s): {url}"
        except Exception as e:
            return f"Fetch failed: {e}"

        if len(text) > self.max_output:
            text = text[: self.max_output] + f"\n... [Content truncated, exceeded {self.max_output} chars]"
        return text


# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------

def get_web_tools() -> list[BaseTool]:
    return [
        WebSearchTool(),
        WebFetchTool(),
    ]
