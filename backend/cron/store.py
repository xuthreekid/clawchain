"""Cron store — JSON 持久化"""

from __future__ import annotations

import json
import os
from pathlib import Path

from config import DATA_DIR

from .types import CronJob, CronStore


def resolve_cron_store_path(override: str | None = None) -> Path:
    """解析 cron store 路径"""
    if override and str(override).strip():
        return Path(override).resolve()
    return DATA_DIR / "cron" / "jobs.json"


def load_cron_store(path: Path | None = None) -> CronStore:
    """加载 cron store"""
    p = path or resolve_cron_store_path()
    if not p.exists():
        return CronStore()
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return CronStore()
    if not isinstance(data, dict):
        return CronStore()
    jobs_raw = data.get("jobs")
    jobs: list[CronJob] = []
    if isinstance(jobs_raw, list):
        for j in jobs_raw:
            if isinstance(j, dict) and j.get("id"):
                jobs.append(CronJob.from_dict(j))
    return CronStore(version=int(data.get("version", 1)), jobs=jobs)


def save_cron_store(store: CronStore, path: Path | None = None) -> None:
    """持久化 cron store"""
    p = path or resolve_cron_store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": store.version,
        "jobs": [j.to_dict() for j in store.jobs],
    }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
