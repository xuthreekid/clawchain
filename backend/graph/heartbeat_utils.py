"""心跳工具 — HEARTBEAT_OK 剥离、ackMaxChars、effectively empty、activeHours 检查"""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

HEARTBEAT_TOKEN = "HEARTBEAT_OK"
DEFAULT_ACK_MAX_CHARS = 300


def is_heartbeat_content_effectively_empty(content: str | None) -> bool:
    """
    若 HEARTBEAT.md 存在但内容为「仅空白/标题/空列表项」等无实质任务，返回 True，可跳过本次调用。
    文件不存在时返回 False（让 LLM 决定）。
    """
    if content is None:
        return False
    if not isinstance(content, str):
        return False
    for line in content.splitlines():
        t = line.strip()
        if not t:
            continue
        if re.match(r"^#+(\s|$)", t):
            continue
        if re.match(r"^[-*+]\s*(\[[\sXx]?\]\s*)?$", t):
            continue
        return False
    return True


def strip_heartbeat_token(
    raw: str | None,
    *,
    max_ack_chars: int = DEFAULT_ACK_MAX_CHARS,
) -> tuple[bool, str]:
    """
    在回复开头或结尾识别并剥离 HEARTBEAT_OK。
    返回 (should_skip, stripped_text)：
    - should_skip=True 仅表示「剥离 token 后为空」的纯 ack 场景
    - stripped_text 为剥离后的文本
    """
    if not raw or not raw.strip():
        return True, ""
    text = raw.strip()
    # 移除 HTML/markdown 包裹
    text = re.sub(r"<[^>]*>", " ", text)
    text = re.sub(r"&nbsp;", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"^[*`~_]+", "", text)
    text = re.sub(r"[*`~_]+$", "", text)
    text = text.strip()
    if HEARTBEAT_TOKEN.upper() not in text.upper():
        return False, text

    # 剥离开头
    pattern_start = re.compile(
        rf"^{re.escape(HEARTBEAT_TOKEN)}(?=$|\s|[.,;:!?\-])\s*",
        re.IGNORECASE,
    )
    text = pattern_start.sub("", text).strip()

    # 剥离结尾（可多次，如 "x HEARTBEAT_OK HEARTBEAT_OK"）
    pattern_end = re.compile(
        rf"\s*{re.escape(HEARTBEAT_TOKEN)}[.,;:!?\-]{{0,4}}\s*$",
        re.IGNORECASE,
    )
    while pattern_end.search(text):
        text = pattern_end.sub("", text).strip()

    if not text:
        return True, ""
    text = re.sub(r"\s+", " ", text).strip()
    # 仅在 token-only 时跳过，避免把真实短提醒误判为 ack。
    return False, text


def is_within_active_hours(
    active_hours: dict | None,
    user_timezone: str = "Asia/Shanghai",
    now: datetime | None = None,
) -> bool:
    """
    判断当前时间是否在 activeHours 窗口内。
    active_hours: { "start": "08:00", "end": "24:00" }
    若 active_hours 为空则返回 True（不限制）。
    """
    if not active_hours or not isinstance(active_hours, dict):
        return True
    start_s = active_hours.get("start", "08:00")
    end_s = active_hours.get("end", "24:00")
    if not start_s or not end_s:
        return True
    try:
        tz = ZoneInfo(user_timezone)
    except Exception:
        tz = ZoneInfo("UTC")
    dt = now or datetime.now(tz)
    try:
        sh, sm = map(int, str(start_s).split(":")[:2])
        eh, em = map(int, str(end_s).replace("24:00", "24:00").split(":")[:2])
    except Exception:
        return True
    current_min = dt.hour * 60 + dt.minute
    start_min = sh * 60 + sm
    end_min = eh * 60 + em
    if end_min == 24 * 60:
        end_min = 24 * 60
    if start_min == end_min:
        return False
    if end_min > start_min:
        return start_min <= current_min < end_min
    return current_min >= start_min or current_min < end_min
