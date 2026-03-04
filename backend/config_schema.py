"""配置 Schema 校验 — Pydantic v2 模型

覆盖: agents / models / tools / session / cron / memorySearch / compaction / contextPruning
提供: validate_config(), sanitize_config_for_client()
"""

import copy
import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Models 配置
# ---------------------------------------------------------------------------

class ModelEntry(BaseModel):
    id: str
    name: Optional[str] = None
    reasoning: bool = False
    input: List[str] = Field(default_factory=lambda: ["text"])
    context_window: Optional[int] = Field(default=None, alias="contextWindow")
    max_tokens: Optional[int] = Field(default=None, alias="maxTokens")
    cost: Optional[Dict[str, Any]] = None

    model_config = {"populate_by_name": True}


class ProviderConfig(BaseModel):
    baseUrl: Optional[str] = None
    apiKey: Optional[str] = None
    api: Optional[str] = None
    models: List[ModelEntry] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "extra": "allow"}


class ModelsConfig(BaseModel):
    providers: Dict[str, ProviderConfig] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Heartbeat 配置
# ---------------------------------------------------------------------------

class ActiveHoursConfig(BaseModel):
    start: str = "08:00"
    end: str = "24:00"


class HeartbeatConfig(BaseModel):
    enabled: bool = True
    every: str = "30m"
    prompt: Optional[str] = None
    ackMaxChars: int = 300
    activeHours: Optional[ActiveHoursConfig] = None
    target: str = "webchat"

    @field_validator("every")
    @classmethod
    def validate_every(cls, v: str) -> str:
        if not v or not v.strip():
            return "30m"
        s = v.strip().lower()
        if s in ("0", "0m", "0h", "disabled", "off"):
            return s
        if not re.match(r"^\d+\s*(m|min|h|hr|s)?$", s):
            raise ValueError(f"Invalid heartbeat interval: {v}")
        return s


# ---------------------------------------------------------------------------
# Compaction 配置
# ---------------------------------------------------------------------------

class CompactionConfig(BaseModel):
    enabled: bool = True
    threshold: float = 0.8
    reserveTokens: int = 20000
    keepRecentTokens: int = 8000
    maxHistoryShare: float = 0.5
    memoryFlush: bool = True
    softThresholdTokens: int = 4000


# ---------------------------------------------------------------------------
# Context Pruning 配置
# ---------------------------------------------------------------------------

class ContextPruningConfig(BaseModel):
    softTrim: bool = True
    toolOutputMaxChars: int = 3000
    recentPreserve: int = 4


# ---------------------------------------------------------------------------
# Subagents 配置
# ---------------------------------------------------------------------------

class SubagentsConfig(BaseModel):
    allow_agents: List[str] = Field(default_factory=lambda: ["*"])
    max_spawn_depth: int = 2
    max_children_per_agent: int = 5
    archive_after_minutes: int = 60
    recent_minutes: int = 30
    run_timeout_seconds: int = 0  # 0 = 无超时


class ChatConfig(BaseModel):
    timeoutSeconds: int = 120  # 0 = 无超时


# ---------------------------------------------------------------------------
# Memory Search 配置
# ---------------------------------------------------------------------------

class VectorStoreConfig(BaseModel):
    enabled: bool = False


class StoreConfig(BaseModel):
    vector: VectorStoreConfig = Field(default_factory=VectorStoreConfig)


class HybridQueryConfig(BaseModel):
    enabled: bool = False
    vectorWeight: float = 0.5
    textWeight: float = 0.5


class QueryConfig(BaseModel):
    hybrid: HybridQueryConfig = Field(default_factory=HybridQueryConfig)


class RemoteConfig(BaseModel):
    baseUrl: str = ""
    apiKey: str = ""


class MemorySearchConfig(BaseModel):
    store: StoreConfig = Field(default_factory=StoreConfig)
    query: QueryConfig = Field(default_factory=QueryConfig)
    provider: str = "local"
    model: str = "text-embedding-3-small"
    remote: RemoteConfig = Field(default_factory=RemoteConfig)


# ---------------------------------------------------------------------------
# Tools Policy
# ---------------------------------------------------------------------------

class ToolsPolicyConfig(BaseModel):
    allow: Optional[List[str]] = None
    deny: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Agent Defaults
# ---------------------------------------------------------------------------

class AgentDefaultsConfig(BaseModel):
    model: Optional[str] = None
    user_timezone: str = "Asia/Shanghai"
    bootstrap_max_chars: int = 20000
    bootstrap_total_max_chars: int = 80000
    recursion_limit: int = 50
    contextTokens: int = 200000
    thinkingDefault: str = "off"
    compaction: CompactionConfig = Field(default_factory=CompactionConfig)
    contextPruning: ContextPruningConfig = Field(default_factory=ContextPruningConfig)
    subagents: SubagentsConfig = Field(default_factory=SubagentsConfig)
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)
    memorySearch: MemorySearchConfig = Field(default_factory=MemorySearchConfig)
    tools: Optional[ToolsPolicyConfig] = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Agent Entry
# ---------------------------------------------------------------------------

class AgentEntryConfig(BaseModel):
    id: str
    name: str = ""
    description: str = ""
    model: Optional[str] = None
    subagents: Optional[SubagentsConfig] = None
    heartbeat: Optional[HeartbeatConfig] = None
    tools: Optional[ToolsPolicyConfig] = None

    model_config = {"extra": "allow"}

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Agent ID cannot be empty")
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(f"Agent ID must be alphanumeric/dash/underscore: {v}")
        return v.strip()


# ---------------------------------------------------------------------------
# Agents 配置
# ---------------------------------------------------------------------------

class AgentsConfig(BaseModel):
    defaults: AgentDefaultsConfig = Field(default_factory=AgentDefaultsConfig)
    list: List[AgentEntryConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def ensure_at_least_one_agent(self) -> "AgentsConfig":
        if not self.list:
            self.list = [AgentEntryConfig(id="main", name="主助手", description="默认通用助手")]
        return self


# ---------------------------------------------------------------------------
# Tools 配置
# ---------------------------------------------------------------------------

class FsToolsConfig(BaseModel):
    workspace_only: bool = True


class ExecToolConfig(BaseModel):
    enabled: bool = False


class ExecApprovalConfig(BaseModel):
    security: Literal["deny", "allowlist", "full"] = "allowlist"
    ask: Literal["off", "on_miss", "always"] = "on_miss"
    ask_timeout_seconds: int = 60
    allowlist: list[str] = Field(default_factory=list)


class ExecToolsConfig(BaseModel):
    apply_patch: ExecToolConfig = Field(default_factory=ExecToolConfig)
    approval: ExecApprovalConfig = Field(default_factory=ExecApprovalConfig)


class WebSearchConfig(BaseModel):
    provider: str = "duckduckgo"
    apiKey: str = ""
    baseUrl: str = ""


class WebToolsConfig(BaseModel):
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ToolsConfig(BaseModel):
    fs: FsToolsConfig = Field(default_factory=FsToolsConfig)
    exec: ExecToolsConfig = Field(default_factory=ExecToolsConfig)
    web: WebToolsConfig = Field(default_factory=WebToolsConfig)


# ---------------------------------------------------------------------------
# Session 配置
# ---------------------------------------------------------------------------

class SessionMaintenanceConfig(BaseModel):
    mode: str = "warn"
    pruneAfter: str = "30d"
    maxEntries: int = 500
    maxDiskBytes: Optional[int] = None
    highWaterBytes: Optional[int] = None


class SessionConfig(BaseModel):
    maintenance: SessionMaintenanceConfig = Field(default_factory=SessionMaintenanceConfig)


# ---------------------------------------------------------------------------
# Cron 配置
# ---------------------------------------------------------------------------

class CronConfig(BaseModel):
    enabled: bool = False
    store: Optional[str] = None


# ---------------------------------------------------------------------------
# Auto Compaction (top-level legacy)
# ---------------------------------------------------------------------------

class AutoCompactionConfig(BaseModel):
    enabled: bool = True
    threshold_tokens: int = 80000
    warning_tokens: int = 60000


# ---------------------------------------------------------------------------
# Session Pruning (top-level legacy)
# ---------------------------------------------------------------------------

class SessionPruningConfig(BaseModel):
    enabled: bool = True
    tool_output_max_chars: int = 3000
    recent_preserve: int = 4


# ---------------------------------------------------------------------------
# App Config (locale, theme, data directory, logging, proxy)
# ---------------------------------------------------------------------------

class AppConfig(BaseModel):
    locale: str = "zh-CN"
    theme: str = "system"
    dataDir: Optional[str] = None
    logLevel: str = "info"
    proxy: Optional[str] = None

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Notifications Config
# ---------------------------------------------------------------------------

class QuietHoursConfig(BaseModel):
    start: str = "23:00"
    end: str = "08:00"


class NotificationsConfig(BaseModel):
    enabled: bool = True
    sound: bool = True
    badge: bool = True
    quietHours: QuietHoursConfig = Field(default_factory=QuietHoursConfig)


# ---------------------------------------------------------------------------
# Sandbox Config
# ---------------------------------------------------------------------------

class SandboxConfig(BaseModel):
    mode: Literal["off", "soft", "strict"] = "soft"
    snapshotBeforeExec: bool = False
    undoStackSize: int = 50
    writeApproval: Literal["off", "on_overwrite", "always"] = "on_overwrite"

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Backup Config
# ---------------------------------------------------------------------------

class BackupConfig(BaseModel):
    autoBackup: bool = False
    intervalHours: int = 24
    maxSnapshots: int = 10
    backupDir: Optional[str] = None


# ---------------------------------------------------------------------------
# Runtime Config
# ---------------------------------------------------------------------------

class RuntimeConfig(BaseModel):
    maxConcurrentSessions: int = 5
    memoryLimitMB: int = 0
    processTimeoutSeconds: int = 300
    gcIdleMinutes: int = 30


# ---------------------------------------------------------------------------
# Skills Config
# ---------------------------------------------------------------------------

class SkillsGlobalConfig(BaseModel):
    autoDiscover: bool = True
    trustedSources: List[str] = Field(default_factory=list)
    updateCheck: bool = False


# ---------------------------------------------------------------------------
# Browser Config
# ---------------------------------------------------------------------------

class BrowserConfig(BaseModel):
    enabled: bool = False
    headless: bool = True
    viewport: Optional[str] = "1280x720"
    proxy: Optional[str] = None


# ---------------------------------------------------------------------------
# Root Config
# ---------------------------------------------------------------------------

class ClawChainConfig(BaseModel):
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    chat: ChatConfig = Field(default_factory=ChatConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    cron: CronConfig = Field(default_factory=CronConfig)
    rag_mode: bool = False
    auto_compaction: AutoCompactionConfig = Field(default_factory=AutoCompactionConfig)
    session_pruning: SessionPruningConfig = Field(default_factory=SessionPruningConfig)
    app: AppConfig = Field(default_factory=AppConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    backup: BackupConfig = Field(default_factory=BackupConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    skills: SkillsGlobalConfig = Field(default_factory=SkillsGlobalConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)

    model_config = {"populate_by_name": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ConfigValidationResult:
    def __init__(self, ok: bool, config: Optional[Dict[str, Any]] = None, errors: Optional[List[str]] = None):
        self.ok = ok
        self.config = config
        self.errors = errors or []


def validate_config(raw: Dict[str, Any]) -> ConfigValidationResult:
    try:
        parsed = ClawChainConfig.model_validate(raw)
        return ConfigValidationResult(ok=True, config=parsed.model_dump(by_alias=True))
    except Exception as e:
        errors = []
        if hasattr(e, "errors"):
            for err in e.errors():
                loc = ".".join(str(x) for x in err.get("loc", []))
                errors.append(f"{loc}: {err.get('msg', str(err))}")
        else:
            errors.append(str(e))
        return ConfigValidationResult(ok=False, errors=errors)


# ---------------------------------------------------------------------------
# Sanitization (remove sensitive fields for client)
# ---------------------------------------------------------------------------

SENSITIVE_KEYS = {"apiKey", "api_key", "token", "secret", "password"}


def _mask_value(v: Any) -> str:
    if not v or not isinstance(v, str):
        return ""
    if len(v) <= 8:
        return "***"
    return v[:4] + "***" + v[-4:]


def _sanitize_dict(d: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
    if depth > 10:
        return d
    result = {}
    for k, v in d.items():
        k_lower = k.lower().replace("-", "").replace("_", "")
        if any(sk.lower().replace("-", "").replace("_", "") == k_lower for sk in SENSITIVE_KEYS):
            result[k] = _mask_value(v)
        elif isinstance(v, dict):
            result[k] = _sanitize_dict(v, depth + 1)
        elif isinstance(v, list):
            result[k] = [_sanitize_dict(item, depth + 1) if isinstance(item, dict) else item for item in v]
        else:
            result[k] = v
    return result


def sanitize_config_for_client(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return _sanitize_dict(copy.deepcopy(cfg))
