"""模型选择与 Fallback

职责:
- 解析 Agent 配置的 model 字段（string 或 {primary, fallbacks}）
- 构建 Fallback 候选链
- run_with_fallback() 自动降级
- Context overflow 直接 rethrow，不换模型
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Callable, Awaitable, TypeVar

from graph.models_config import (
    ModelRef,
    models_config,
    parse_model_ref,
)
from graph.errors import is_likely_context_overflow_error, resolve_failover_reason_from_error

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Agent 模型配置解析
# ---------------------------------------------------------------------------

def _ref_exists_in_catalog(ref: ModelRef) -> bool:
    """检查 ModelRef 是否在 catalog 中存在"""
    return models_config.get_model(ref) is not None


def resolve_agent_model_primary(model_value: Any) -> str | None:
    """从 agent config 的 model 字段提取 primary model 字符串"""
    if model_value is None:
        return None
    if isinstance(model_value, str):
        return model_value.strip() or None
    if isinstance(model_value, dict):
        primary = model_value.get("primary", "")
        if isinstance(primary, str) and primary.strip():
            return primary.strip()
    return None


def resolve_agent_model_fallbacks(model_value: Any) -> list[str]:
    """从 agent config 的 model 字段提取 fallbacks 列表"""
    if not isinstance(model_value, dict):
        return []
    fallbacks = model_value.get("fallbacks", [])
    if not isinstance(fallbacks, list):
        return []
    return [f.strip() for f in fallbacks if isinstance(f, str) and f.strip()]


def resolve_default_model_ref() -> ModelRef:
    """获取系统默认模型。未在 config 中配置则无模型，抛出错误。"""
    from config import get_agent_defaults
    defaults = get_agent_defaults()
    model_value = defaults.get("model")
    primary_str = resolve_agent_model_primary(model_value)

    if primary_str:
        ref = _resolve_model_ref_with_discovery(primary_str)
        if ref and _ref_exists_in_catalog(ref):
            return ref

    raise RuntimeError(
        "未配置可用模型。请在 config.json 的 models.providers 中添加 provider（baseUrl、apiKey、models），"
        "并在 agents.defaults.model 中指定模型（如 openai/gpt-4o）。"
    )


def resolve_agent_model(agent_id: str) -> ModelRef:
    """解析指定 Agent 的 primary model，回退到 defaults。未配置则无模型，抛出错误。"""
    from config import resolve_agent_config
    cfg = resolve_agent_config(agent_id)
    model_value = cfg.get("model")

    primary_str = resolve_agent_model_primary(model_value)
    if primary_str:
        ref = _resolve_model_ref_with_discovery(primary_str)
        if ref and _ref_exists_in_catalog(ref):
            return ref

    return resolve_default_model_ref()


def _resolve_model_ref_with_discovery(raw: str) -> ModelRef | None:
    """解析模型字符串，若无 provider 前缀则在 catalog 中查找。未配置则返回 None。"""
    ref = parse_model_ref(raw)
    if not ref:
        return None

    if ref.provider:
        return ref

    # 无 provider 前缀 → 在所有 provider 中搜索
    found = models_config.find_model_by_id(ref.model)
    if found:
        provider, model_def = found
        return ModelRef(provider=provider.id, model=model_def.id)

    return None


# ---------------------------------------------------------------------------
# Fallback 候选链
# ---------------------------------------------------------------------------

def resolve_fallback_candidates(agent_id: str) -> list[ModelRef]:
    """构建 primary + fallbacks 降级链。仅包含 catalog 中存在的模型。"""
    from config import resolve_agent_config
    cfg = resolve_agent_config(agent_id)
    model_value = cfg.get("model")

    candidates: list[ModelRef] = []
    seen: set[str] = set()

    def _add(ref: ModelRef | None) -> None:
        if ref and _ref_exists_in_catalog(ref):
            key = str(ref)
            if key not in seen:
                seen.add(key)
                candidates.append(ref)

    # Primary
    try:
        primary = resolve_agent_model(agent_id)
        _add(primary)
    except RuntimeError:
        pass

    # Configured fallbacks
    for raw in resolve_agent_model_fallbacks(model_value):
        _add(_resolve_model_ref_with_discovery(raw))

    # Defaults fallbacks (if agent has no explicit fallbacks)
    if len(candidates) <= 1:
        from config import get_agent_defaults
        defaults = get_agent_defaults()
        defaults_model = defaults.get("model")
        for raw in resolve_agent_model_fallbacks(defaults_model):
            _add(_resolve_model_ref_with_discovery(raw))

    # Global default as last resort
    try:
        _add(resolve_default_model_ref())
    except RuntimeError:
        pass

    if not candidates:
        raise RuntimeError(
            "无可用模型。请在 config.json 的 models.providers 中配置 provider（baseUrl、apiKey、models）。"
        )
    return candidates


# ---------------------------------------------------------------------------
# Fallback 执行器
# ---------------------------------------------------------------------------

@dataclass
class FallbackAttempt:
    provider: str
    model: str
    error: str
    reason: str | None = None


@dataclass
class FallbackResult:
    result: Any
    provider: str
    model: str
    attempts: list[FallbackAttempt]


async def run_with_fallback(
    candidates: list[ModelRef],
    run_fn: Callable[[str, str], Awaitable[T]],
    on_error: Callable[[str, str, Exception, int, int], Awaitable[None]] | None = None,
) -> FallbackResult:
    """尝试按序运行候选模型，失败则降级到下一个。

    Context overflow 错误直接 rethrow，不换模型（换模型可能更小 context 更糟）。
    """
    attempts: list[FallbackAttempt] = []
    last_error: Exception | None = None

    for i, candidate in enumerate(candidates):
        try:
            result = await run_fn(candidate.provider, candidate.model)
            return FallbackResult(
                result=result,
                provider=candidate.provider,
                model=candidate.model,
                attempts=attempts,
            )
        except Exception as e:
            last_error = e
            error_msg = str(e)

            # Context overflow 直接 rethrow，不尝试其他模型
            if is_likely_context_overflow_error(error_msg):
                raise

            reason = resolve_failover_reason_from_error(e)
            attempts.append(FallbackAttempt(
                provider=candidate.provider,
                model=candidate.model,
                error=error_msg,
                reason=reason,
            ))
            logger.warning(
                f"Model fallback [{i+1}/{len(candidates)}]: "
                f"{candidate} failed ({reason or 'unknown'}): {error_msg[:200]}"
            )
            if on_error:
                await on_error(candidate.provider, candidate.model, e, i + 1, len(candidates))

    summary = " | ".join(
        f"{a.provider}/{a.model}: {a.error[:100]}" for a in attempts
    )
    raise RuntimeError(f"All {len(candidates)} model candidates failed: {summary}") from last_error


async def run_with_fallback_stream(
    candidates: list[ModelRef],
    run_fn: Callable[[str, str], AsyncGenerator[T, None]],
) -> AsyncGenerator[T, None]:
    """流式 Fallback：按序尝试候选模型，yield 事件，失败则换下一个。

    Context overflow 直接 rethrow。
    """
    last_error: Exception | None = None
    for i, candidate in enumerate(candidates):
        try:
            async for item in run_fn(candidate.provider, candidate.model):
                yield item
            return
        except Exception as e:
            last_error = e
            error_msg = str(e)
            if is_likely_context_overflow_error(error_msg):
                raise
            reason = resolve_failover_reason_from_error(e)
            logger.warning(
                f"Model fallback [{i+1}/{len(candidates)}]: "
                f"{candidate} failed ({reason or 'unknown'}): {error_msg[:200]}"
            )

    summary = f"All {len(candidates)} model candidates failed"
    raise RuntimeError(summary) from last_error


# ---------------------------------------------------------------------------
# 模型信息查询快捷方法
# ---------------------------------------------------------------------------

def get_model_display_name(ref: ModelRef) -> str:
    model_def = models_config.get_model(ref)
    if model_def:
        return model_def.name
    return f"{ref.provider}/{ref.model}"


def get_model_context_window(ref: ModelRef) -> int:
    return models_config.resolve_context_window(ref)


def get_model_max_tokens(ref: ModelRef) -> int:
    return models_config.resolve_max_tokens(ref)
