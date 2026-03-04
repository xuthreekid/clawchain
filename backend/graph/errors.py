"""错误分类与检测

用于模型 fallback、瞬时 HTTP 重试、压缩失败、会话重置等决策。
"""

from __future__ import annotations

import re
from typing import Literal

# FailoverReason 类型
FailoverReason = Literal[
    "model_not_found",
    "timeout",
    "rate_limit",
    "billing",
    "auth",
    "auth_permanent",
    "format",
]

# 瞬时 HTTP 状态码（502/503 等）
TRANSIENT_HTTP_CODES = frozenset({500, 502, 503, 504, 521, 522, 523, 524, 529})

# 正则
CONTEXT_WINDOW_TOO_SMALL_RE = re.compile(
    r"context window.*(too small|minimum is)", re.I
)
CONTEXT_OVERFLOW_HINT_RE = re.compile(
    r"context.*overflow|context window.*(too (?:large|long)|exceed|over|limit|max(?:imum)?|requested|sent|tokens)|"
    r"prompt.*(too (?:large|long)|exceed|over|limit|max(?:imum)?)|"
    r"(?:request|input).*(?:context|window|length|token).*(too (?:large|long)|exceed|over|limit|max(?:imum)?)",
    re.I,
)
RATE_LIMIT_HINT_RE = re.compile(
    r"rate limit|too many requests|requests per (?:minute|hour|day)|quota|throttl|429\b",
    re.I,
)
HTTP_STATUS_CODE_PREFIX_RE = re.compile(r"^(?:http\s*)?(\d{3})(?:\s+([\s\S]*))?$")
BILLING_ERROR_HARD_402_RE = re.compile(
    r'["\']?(?:status|code)["\']?\s*[:=]\s*402\b|\bhttp\s*402\b|'
    r"\berror(?:\s+code)?\s*[:=]?\s*402\b|^\s*402\s+payment",
    re.I,
)

# 错误模式
RATE_LIMIT_PATTERNS = [
    r"rate[_ ]limit|too many requests|429",
    "model_cooldown",
    "cooling down",
    "exceeded your current quota",
    "resource has been exhausted",
    "quota exceeded",
    "resource_exhausted",
    "usage limit",
    "tpm",
    "tokens per minute",
]
OVERLOADED_PATTERNS = [
    r"overloaded_error",
    r'"type"\s*:\s*"overloaded_error"',
    "overloaded",
    "service unavailable",
    "high demand",
]
TIMEOUT_PATTERNS = [
    "timeout",
    "timed out",
    "deadline exceeded",
    "context deadline exceeded",
    r"without sending (?:any )?chunks?",
    r"\bstop reason:\s*abort\b",
    r"\breason:\s*abort\b",
    r"\bunhandled stop reason:\s*abort\b",
]
BILLING_PATTERNS = [
    r'["\']?(?:status|code)["\']?\s*[:=]\s*402\b',
    r"\bhttp\s*402\b",
    "payment required",
    "insufficient credits",
    "credit balance",
    "plans & billing",
    "insufficient balance",
]
AUTH_PERMANENT_PATTERNS = [
    r"api[_ ]?key[_ ]?(?:revoked|invalid|deactivated|deleted)",
    "invalid_api_key",
    "key has been disabled",
    "key has been revoked",
    "account has been deactivated",
    r"could not (?:authenticate|validate).*(?:api[_ ]?key|credentials)",
]
AUTH_PATTERNS = [
    r"invalid[_ ]?api[_ ]?key",
    "incorrect api key",
    "invalid token",
    "authentication",
    "re-authenticate",
    "oauth token refresh failed",
    "unauthorized",
    "forbidden",
    "access denied",
    "insufficient permissions",
    "insufficient permission",
    r"missing scopes?:",
    "expired",
    "token has expired",
    r"\b401\b",
    r"\b403\b",
    "no credentials found",
    "no api key found",
]
FORMAT_PATTERNS = [
    "string should match pattern",
    "tool_use.id",
    "tool_use_id",
    "messages.1.content.1.tool_use.id",
    "invalid request format",
    r"tool call id was.*must be",
]
BILLING_ERROR_HEAD_RE = re.compile(
    r"^(?:error[:\s-]+)?billing(?:\s+error)?(?:[:\s-]+|$)|"
    r"^(?:error[:\s-]+)?(?:credit balance|insufficient credits?|payment required|http\s*402\b)",
    re.I,
)

BILLING_ERROR_MAX_LENGTH = 512


def _matches_patterns(raw: str, patterns: list[str]) -> bool:
    if not raw:
        return False
    lower = raw.lower()
    for p in patterns:
        try:
            if re.search(p, raw, re.I):
                return True
        except re.error:
            pass
        if p in lower:
            return True
    return False


def _extract_leading_http_status(raw: str) -> tuple[int, str] | None:
    m = HTTP_STATUS_CODE_PREFIX_RE.match(raw.strip())
    if not m:
        return None
    code = int(m.group(1))
    if not (100 <= code < 600):
        return None
    rest = (m.group(2) or "").strip()
    return (code, rest)


# ---------------------------------------------------------------------------
# Context overflow
# ---------------------------------------------------------------------------


def _is_reasoning_constraint_message(raw: str) -> bool:
    lower = raw.lower()
    return (
        "reasoning is mandatory" in lower
        or "reasoning is required" in lower
        or "requires reasoning" in lower
        or ("reasoning" in lower and "cannot be disabled" in lower)
    )


def is_context_overflow_error(error_message: str | None) -> bool:
    """严格 overflow 判断"""
    if not error_message:
        return False
    lower = error_message.lower()
    if "tpm" in lower or "tokens per minute" in lower:
        return False
    if _is_reasoning_constraint_message(error_message):
        return False

    has_request_size = "request size exceeds" in lower
    has_context_window = (
        "context window" in lower
        or "context length" in lower
        or "maximum context length" in lower
    )
    return (
        "request_too_large" in lower
        or "request exceeds the maximum size" in lower
        or "context length exceeded" in lower
        or "maximum context length" in lower
        or "prompt is too long" in lower
        or "exceeds model context window" in lower
        or "model token limit" in lower
        or (has_request_size and has_context_window)
        or "context overflow:" in lower
        or "exceed context limit" in lower
        or "exceeds the model's maximum context" in lower
        or ("max_tokens" in lower and "exceed" in lower and "context" in lower)
        or ("input length" in lower and "exceed" in lower and "context" in lower)
        or ("413" in lower and "too large" in lower)
        or "上下文过长" in error_message
        or "上下文超出" in error_message
        or "上下文长度超" in error_message
        or "超出最大上下文" in error_message
        or "请压缩上下文" in error_message
    )


def is_likely_context_overflow_error(error_message: str | None) -> bool:
    """宽松 overflow 判断，用于 model fallback 时直接 rethrow"""
    if not error_message:
        return False
    lower = error_message.lower()
    if "tpm" in lower or "tokens per minute" in lower:
        return False
    if _is_reasoning_constraint_message(error_message):
        return False
    if CONTEXT_WINDOW_TOO_SMALL_RE.search(error_message):
        return False
    if is_rate_limit_error_message(error_message):
        return False
    if is_context_overflow_error(error_message):
        return True
    if RATE_LIMIT_HINT_RE.search(error_message):
        return False
    return bool(CONTEXT_OVERFLOW_HINT_RE.search(error_message))


# ---------------------------------------------------------------------------
# Compaction failure
# ---------------------------------------------------------------------------


def is_compaction_failure_error(error_message: str | None) -> bool:
    """压缩失败检测（含 summarization failed、auto-compaction 等）"""
    if not error_message:
        return False
    lower = error_message.lower()
    has_compaction = (
        "summarization failed" in lower
        or "auto-compaction" in lower
        or "compaction failed" in lower
        or "compaction" in lower
    )
    if not has_compaction:
        return False
    if is_likely_context_overflow_error(error_message):
        return True
    return "context overflow" in lower


# ---------------------------------------------------------------------------
# Transient HTTP
# ---------------------------------------------------------------------------


def is_transient_http_error(raw: str | None) -> bool:
    """瞬时 HTTP 错误（502/503 等），用于 2.5s 后重试"""
    if not raw or not raw.strip():
        return False
    status = _extract_leading_http_status(raw)
    if not status:
        return False
    code, _ = status
    return code in TRANSIENT_HTTP_CODES


# ---------------------------------------------------------------------------
# Rate limit / Timeout / Billing / Auth / Format
# ---------------------------------------------------------------------------


def is_rate_limit_error_message(raw: str) -> bool:
    return _matches_patterns(raw, RATE_LIMIT_PATTERNS)


def is_overloaded_error_message(raw: str) -> bool:
    return _matches_patterns(raw, OVERLOADED_PATTERNS)


def is_timeout_error_message(raw: str) -> bool:
    return _matches_patterns(raw, TIMEOUT_PATTERNS)


def is_billing_error_message(raw: str) -> bool:
    lower = raw.lower()
    if not lower:
        return False
    if len(raw) > BILLING_ERROR_MAX_LENGTH:
        return bool(BILLING_ERROR_HARD_402_RE.search(lower))
    if _matches_patterns(lower, BILLING_PATTERNS):
        return True
    if not BILLING_ERROR_HEAD_RE.search(raw):
        return False
    return (
        "upgrade" in lower
        or "credits" in lower
        or "payment" in lower
        or "plan" in lower
    )


def is_auth_permanent_error_message(raw: str) -> bool:
    return _matches_patterns(raw, AUTH_PERMANENT_PATTERNS)


def is_auth_error_message(raw: str) -> bool:
    return _matches_patterns(raw, AUTH_PATTERNS)


def _is_cloud_code_assist_format_error(raw: str) -> bool:
    return _matches_patterns(raw, FORMAT_PATTERNS)


def _is_image_dimension_error_message(raw: str) -> bool:
    return "image dimensions exceed max allowed size" in raw.lower()


def _is_image_size_error(raw: str) -> bool:
    return "image exceeds" in raw.lower() and "mb" in raw.lower()


def _is_model_not_found_error_message(raw: str) -> bool:
    lower = raw.lower()
    if (
        "unknown model" in lower
        or "model not found" in lower
        or "model_not_found" in lower
        or "not_found_error" in lower
        or ("does not exist" in lower and "model" in lower)
        or ("invalid model" in lower and "invalid model reference" not in lower)
    ):
        return True
    if re.search(r"models/[^\s]+ is not found", raw, re.I):
        return True
    if re.search(r"\b404\b", raw) and re.search(r"not[-_ ]?found", raw, re.I):
        return True
    return False


def _is_json_api_internal_server_error(raw: str) -> bool:
    lower = raw.lower()
    return '"type":"api_error"' in lower and "internal server error" in lower


# ---------------------------------------------------------------------------
# classify_failover_reason
# ---------------------------------------------------------------------------


def classify_failover_reason(raw: str | None) -> FailoverReason | None:
    """从错误消息文本分类 FailoverReason"""
    if not raw:
        return None
    if _is_image_dimension_error_message(raw):
        return None
    if _is_image_size_error(raw):
        return None
    if _is_model_not_found_error_message(raw):
        return "model_not_found"
    if is_transient_http_error(raw):
        return "timeout"
    if _is_json_api_internal_server_error(raw):
        return "timeout"
    if is_rate_limit_error_message(raw):
        return "rate_limit"
    if is_overloaded_error_message(raw):
        return "rate_limit"
    if _is_cloud_code_assist_format_error(raw):
        return "format"
    if is_billing_error_message(raw):
        return "billing"
    if is_timeout_error_message(raw):
        return "timeout"
    if is_auth_permanent_error_message(raw):
        return "auth_permanent"
    if is_auth_error_message(raw):
        return "auth"
    return None


# ---------------------------------------------------------------------------
# resolve_failover_reason_from_error
# ---------------------------------------------------------------------------


def _get_status_code(err: BaseException) -> int | None:
    """从异常中提取 HTTP 状态码"""
    if hasattr(err, "status_code"):
        return getattr(err, "status_code", None)
    if hasattr(err, "response") and err.response is not None:
        resp = err.response
        if hasattr(resp, "status_code"):
            return resp.status_code
    if hasattr(err, "status"):
        return getattr(err, "status", None)
    return None


def _get_error_code(err: BaseException) -> str | None:
    """从异常中提取错误码（如 ETIMEDOUT）"""
    if hasattr(err, "errno"):
        return str(getattr(err, "errno", ""))
    if hasattr(err, "code"):
        return str(getattr(err, "code", ""))
    return None


def resolve_failover_reason_from_error(err: BaseException) -> FailoverReason | None:
    """从异常/HTTP 推断 FailoverReason"""
    msg = str(err)
    classified = classify_failover_reason(msg)
    if classified:
        return classified

    status = _get_status_code(err)
    if status == 402:
        return "billing"
    if status == 429:
        return "rate_limit"
    if status in (401, 403):
        if is_auth_permanent_error_message(msg):
            return "auth_permanent"
        return "auth"
    if status == 408:
        return "timeout"
    if status in (502, 503, 504):
        return "timeout"
    if status == 400:
        return "format"

    code = (_get_error_code(err) or "").upper()
    if code in ("ETIMEDOUT", "ESOCKETTIMEDOUT", "ECONNRESET", "ECONNABORTED"):
        return "timeout"

    return None


# ---------------------------------------------------------------------------
# Session-level error detection
# ---------------------------------------------------------------------------


def is_role_ordering_error(message: str | None) -> bool:
    """Role ordering 冲突（incorrect role information | roles must alternate）"""
    if not message:
        return False
    return bool(
        re.search(
            r"incorrect role information|roles must alternate",
            message,
            re.I,
        )
    )


def is_session_corruption_error(message: str | None) -> bool:
    """Gemini session 损坏（function call turn comes immediately after）"""
    if not message:
        return False
    return "function call turn comes immediately after" in message.lower()
