"""模型配置系统 — 仅从 config.json 的 models.providers 加载

- 模型全部来自 config.models.providers，无内置、无环境变量回退
- 未在 config 中配置的 Provider 不存在，未配置则无模型
- 每个 Provider 需在 config 中显式设置 baseUrl、apiKey、models
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 支持的 API 协议
# ---------------------------------------------------------------------------

SUPPORTED_API_PROTOCOLS = frozenset({
    "openai-completions",
    "anthropic-messages",
    "ollama",
})

# ---------------------------------------------------------------------------
# 数据类型
# ---------------------------------------------------------------------------

@dataclass
class ModelRef:
    """模型引用: provider/model"""
    provider: str
    model: str

    def __str__(self) -> str:
        return f"{self.provider}/{self.model}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ModelRef):
            return NotImplemented
        return self.provider == other.provider and self.model == other.model

    def __hash__(self) -> int:
        return hash((self.provider, self.model))


@dataclass
class ModelDefinition:
    """模型完整定义"""
    id: str
    name: str
    api: str | None = None
    reasoning: bool = False
    input: list[str] = field(default_factory=lambda: ["text"])
    context_window: int = 128000
    max_tokens: int = 8192
    cost: dict[str, float] = field(default_factory=dict)
    compat: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class ProviderConfig:
    """Provider 完整配置"""
    id: str
    base_url: str
    api_key: str = ""
    auth: str = "api-key"
    api: str = "openai-completions"
    headers: dict[str, str] = field(default_factory=dict)
    models: list[ModelDefinition] = field(default_factory=list)


@dataclass
class ModelCatalogEntry:
    """模型目录条目（轻量级，用于列表展示）"""
    id: str
    name: str
    provider: str
    context_window: int | None = None
    reasoning: bool | None = None
    input: list[str] | None = None


# ---------------------------------------------------------------------------
# Provider ID 规范化
# ---------------------------------------------------------------------------

_PROVIDER_ALIASES: dict[str, str] = {
    "z.ai": "zai",
    "z-ai": "zai",
    "aws-bedrock": "amazon-bedrock",
    "bedrock": "amazon-bedrock",
    "bytedance": "volcengine",
    "doubao": "volcengine",
    "qwen": "qwen-portal",
}


def normalize_provider_id(provider: str) -> str:
    normalized = provider.strip().lower()
    return _PROVIDER_ALIASES.get(normalized, normalized)


# ---------------------------------------------------------------------------
# 解析配置 — 仅使用 config 中的值，无环境变量回退
# ---------------------------------------------------------------------------

def _parse_model_definition(raw: dict[str, Any]) -> ModelDefinition:
    return ModelDefinition(
        id=raw.get("id", ""),
        name=raw.get("name", raw.get("id", "")),
        api=raw.get("api"),
        reasoning=raw.get("reasoning", False),
        input=raw.get("input", ["text"]),
        context_window=raw.get("contextWindow", 128000),
        max_tokens=raw.get("maxTokens", 8192),
        cost=raw.get("cost", {}),
        compat=raw.get("compat", {}),
        headers=raw.get("headers", {}),
    )


def _parse_provider_config(provider_id: str, raw: dict[str, Any]) -> ProviderConfig | None:
    """解析 Provider 配置。baseUrl 和 apiKey 必须来自 config，无 env 回退。"""
    base_url = (raw.get("baseUrl") or "").strip()
    api_key = (raw.get("apiKey") or "").strip()

    # baseUrl 必填，否则跳过该 Provider
    if not base_url:
        logger.warning(f"Provider '{provider_id}' 缺少 baseUrl，已跳过。请在 config.json 的 models.providers 中配置。")
        return None

    models = [_parse_model_definition(m) for m in raw.get("models", [])]
    if not models:
        logger.warning(f"Provider '{provider_id}' 无 models 定义，已跳过。")
        return None

    return ProviderConfig(
        id=provider_id,
        base_url=base_url,
        api_key=api_key,
        auth=raw.get("auth", "api-key"),
        api=raw.get("api", "openai-completions"),
        headers=raw.get("headers", {}),
        models=models,
    )


# ---------------------------------------------------------------------------
# ModelsConfigManager — 单例，仅从 config 加载
# ---------------------------------------------------------------------------

class ModelsConfigManager:
    """管理 Provider/Model 配置。仅从 config.json 的 models.providers 加载，无内置、无 env。"""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderConfig] = {}
        self._initialized = False

    def initialize(self, models_config: dict[str, Any] | None = None) -> None:
        """仅从 config 的 models.providers 加载，无内置 Provider、无环境变量回退"""
        self._providers.clear()

        explicit_providers: dict[str, dict[str, Any]] = {}
        if models_config and "providers" in models_config:
            explicit_providers = models_config["providers"]

        for provider_id, raw in explicit_providers.items():
            pid = normalize_provider_id(provider_id)
            parsed = _parse_provider_config(pid, raw)
            if parsed:
                self._providers[pid] = parsed

        self._initialized = True
        provider_names = list(self._providers.keys())
        model_count = sum(len(p.models) for p in self._providers.values())
        logger.info(f"Models config: {len(provider_names)} providers, {model_count} models ({provider_names})")

    def reload(self, models_config: dict[str, Any] | None = None) -> None:
        self.initialize(models_config)

    def get_provider(self, provider_id: str) -> ProviderConfig | None:
        pid = normalize_provider_id(provider_id)
        return self._providers.get(pid)

    def get_model(self, ref: ModelRef) -> ModelDefinition | None:
        provider = self.get_provider(ref.provider)
        if not provider:
            return None
        model_id = ref.model.strip().lower()
        for m in provider.models:
            if m.id.lower() == model_id:
                return m
        return None

    def find_model_by_id(self, model_id: str) -> tuple[ProviderConfig, ModelDefinition] | None:
        mid = model_id.strip().lower()
        for provider in self._providers.values():
            for m in provider.models:
                if m.id.lower() == mid:
                    return (provider, m)
        return None

    def resolve_model_ref(self, raw: str, default_provider: str = "") -> ModelRef | None:
        return parse_model_ref(raw, default_provider)

    def list_providers(self) -> list[ProviderConfig]:
        return list(self._providers.values())

    def list_all_models(self) -> list[ModelCatalogEntry]:
        result: list[ModelCatalogEntry] = []
        for provider in self._providers.values():
            for m in provider.models:
                result.append(ModelCatalogEntry(
                    id=m.id,
                    name=m.name,
                    provider=provider.id,
                    context_window=m.context_window,
                    reasoning=m.reasoning,
                    input=m.input,
                ))
        return result

    def model_supports_vision(self, ref: ModelRef) -> bool:
        model = self.get_model(ref)
        return model and "image" in (model.input or [])

    def model_supports_reasoning(self, ref: ModelRef) -> bool:
        model = self.get_model(ref)
        return bool(model and model.reasoning)

    def resolve_context_window(self, ref: ModelRef) -> int:
        model = self.get_model(ref)
        return model.context_window if model else 128000

    def resolve_max_tokens(self, ref: ModelRef) -> int:
        model = self.get_model(ref)
        return model.max_tokens if model else 8192

    def resolve_api_protocol(self, ref: ModelRef) -> str:
        model = self.get_model(ref)
        provider = self.get_provider(ref.provider)
        if model and model.api:
            return model.api
        if provider:
            return provider.api
        return "openai-completions"


# ---------------------------------------------------------------------------
# 全局函数
# ---------------------------------------------------------------------------

DEFAULT_CONTEXT_TOKENS = 200_000


def parse_model_ref(raw: str, default_provider: str = "") -> ModelRef | None:
    trimmed = raw.strip()
    if not trimmed:
        return None

    slash = trimmed.find("/")
    if slash != -1:
        provider = trimmed[:slash].strip()
        model = trimmed[slash + 1:].strip()
        if not provider or not model:
            return None
        return ModelRef(provider=normalize_provider_id(provider), model=model)

    if default_provider:
        return ModelRef(provider=normalize_provider_id(default_provider), model=trimmed)

    return ModelRef(provider="", model=trimmed)


def normalize_anthropic_base_url(base_url: str) -> str:
    import re
    return re.sub(r"/v1/?$", "", base_url)


models_config = ModelsConfigManager()
