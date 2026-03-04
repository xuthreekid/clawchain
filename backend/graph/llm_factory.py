"""LLM 工厂 — 根据 Provider 配置动态创建 LangChain LLM 实例

- openai-completions → ChatOpenAI（兼容大多数 Provider）
- anthropic-messages → ChatAnthropic（Anthropic Claude）
- ollama → ChatOllama（本地模型）

每种协议有不同的兼容性处理（baseUrl 规范化、请求头、max_tokens 字段名等）
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from graph.models_config import (
    ModelRef,
    ModelDefinition,
    ProviderConfig,
    models_config,
    normalize_anthropic_base_url,
)

logger = logging.getLogger(__name__)


def create_llm(
    ref: ModelRef,
    *,
    temperature: float = 0.7,
    streaming: bool = True,
    max_tokens_override: int | None = None,
    extra_kwargs: dict[str, Any] | None = None,
) -> BaseChatModel:
    """根据 ModelRef 创建对应的 LangChain LLM 实例

    查找 Provider 和 Model 配置，按 API 协议选择正确的客户端类。
    """
    provider = models_config.get_provider(ref.provider)
    model_def = models_config.get_model(ref)

    if not provider:
        raise ValueError(
            f"Provider '{ref.provider}' not configured. "
            f"Available: {[p.id for p in models_config.list_providers()]}"
        )

    api_protocol = models_config.resolve_api_protocol(ref)
    max_tokens = max_tokens_override or (model_def.max_tokens if model_def else 8192)

    logger.info(
        f"Creating LLM: {ref} via {api_protocol} "
        f"(base_url={provider.base_url}, max_tokens={max_tokens})"
    )

    if api_protocol == "anthropic-messages":
        return _create_anthropic(ref, provider, model_def, temperature, streaming, max_tokens, extra_kwargs)
    elif api_protocol == "ollama":
        return _create_ollama(ref, provider, model_def, temperature, streaming, max_tokens, extra_kwargs)
    else:
        return _create_openai(ref, provider, model_def, temperature, streaming, max_tokens, extra_kwargs)


# ---------------------------------------------------------------------------
# OpenAI Completions（默认，兼容大多数 Provider）
# ---------------------------------------------------------------------------

def _create_openai(
    ref: ModelRef,
    provider: ProviderConfig,
    model_def: ModelDefinition | None,
    temperature: float,
    streaming: bool,
    max_tokens: int,
    extra_kwargs: dict[str, Any] | None,
) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    compat = model_def.compat if model_def else {}
    max_tokens_field = compat.get("maxTokensField", "max_tokens")

    kwargs: dict[str, Any] = {
        "api_key": provider.api_key,
        "model": ref.model,
        "temperature": temperature,
        "streaming": streaming,
    }

    if provider.base_url:
        kwargs["base_url"] = provider.base_url

    if max_tokens_field == "max_completion_tokens":
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens

    headers = {**provider.headers}
    if model_def and model_def.headers:
        headers.update(model_def.headers)
    if headers:
        kwargs["default_headers"] = headers

    if extra_kwargs:
        kwargs.update(extra_kwargs)

    return ChatOpenAI(**kwargs)


# ---------------------------------------------------------------------------
# Anthropic Messages
# ---------------------------------------------------------------------------

def _create_anthropic(
    ref: ModelRef,
    provider: ProviderConfig,
    model_def: ModelDefinition | None,
    temperature: float,
    streaming: bool,
    max_tokens: int,
    extra_kwargs: dict[str, Any] | None,
) -> BaseChatModel:
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        raise ImportError(
            "langchain-anthropic is required for Anthropic models. "
            "Install it with: pip install langchain-anthropic"
        )

    base_url = normalize_anthropic_base_url(provider.base_url) if provider.base_url else None

    kwargs: dict[str, Any] = {
        "api_key": provider.api_key,
        "model": ref.model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "streaming": streaming,
    }

    if base_url:
        kwargs["base_url"] = base_url

    headers = {**provider.headers}
    if model_def and model_def.headers:
        headers.update(model_def.headers)
    if headers:
        kwargs["default_headers"] = headers

    if extra_kwargs:
        kwargs.update(extra_kwargs)

    return ChatAnthropic(**kwargs)


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

def _create_ollama(
    ref: ModelRef,
    provider: ProviderConfig,
    model_def: ModelDefinition | None,
    temperature: float,
    streaming: bool,
    max_tokens: int,
    extra_kwargs: dict[str, Any] | None,
) -> BaseChatModel:
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        raise ImportError(
            "langchain-ollama is required for Ollama models. "
            "Install it with: pip install langchain-ollama"
        )

    kwargs: dict[str, Any] = {
        "model": ref.model,
        "temperature": temperature,
        "num_predict": max_tokens,
    }

    if provider.base_url:
        kwargs["base_url"] = provider.base_url

    if extra_kwargs:
        kwargs.update(extra_kwargs)

    return ChatOllama(**kwargs)


# ---------------------------------------------------------------------------
# LLM 缓存管理
# ---------------------------------------------------------------------------

class LLMCache:
    """Per-Agent LLM 实例缓存"""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[ModelRef, BaseChatModel]] = {}

    def get_or_create(self, agent_id: str, ref: ModelRef, **kwargs: Any) -> BaseChatModel:
        cached = self._cache.get(agent_id)
        if cached:
            cached_ref, cached_llm = cached
            if cached_ref == ref:
                return cached_llm

        llm = create_llm(ref, **kwargs)
        self._cache[agent_id] = (ref, llm)
        logger.info(f"LLM created for agent '{agent_id}': {ref}")
        return llm

    def invalidate(self, agent_id: str) -> None:
        self._cache.pop(agent_id, None)

    def invalidate_all(self) -> None:
        self._cache.clear()

    def get_current_ref(self, agent_id: str) -> ModelRef | None:
        cached = self._cache.get(agent_id)
        return cached[0] if cached else None


llm_cache = LLMCache()
