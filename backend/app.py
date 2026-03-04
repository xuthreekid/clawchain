"""ClawChain 后端入口 — FastAPI + Uvicorn"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import load_config, DATA_DIR, list_agents
from tools.skills_scanner import scan_all_skills
from tools.skills_watcher import skills_watcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """启动时初始化：配置、技能扫描、Agent 引擎、Heartbeat、技能热加载"""
    load_config()

    from graph.agent import agent_manager
    scan_all_skills()
    await agent_manager.initialize(str(DATA_DIR))
    skills_watcher.start()

    from graph.heartbeat import heartbeat_runner
    agent_ids = [a["id"] for a in list_agents()]
    await heartbeat_runner.start(agent_ids)
    logger.info(f"Heartbeat started for agents: {agent_ids}")

    from graph.subagent_archive import start_subagent_archive
    start_subagent_archive()

    from config import get_config
    cfg = get_config()
    cron_cfg = cfg.get("cron") or {}
    if cron_cfg.get("enabled"):
        from cron.scheduler import CronScheduler
        from graph.heartbeat import request_heartbeat_now
        cron_scheduler = CronScheduler()
        cron_scheduler.set_request_heartbeat_now(request_heartbeat_now)
        await cron_scheduler.start()
        application.state.cron_scheduler = cron_scheduler
        logger.info("Cron scheduler started")
    else:
        application.state.cron_scheduler = None

    from graph.subagent_resume import resume_subagent_runs
    try:
        await resume_subagent_runs()
    except Exception as e:
        logger.warning(f"Subagent resume failed: {e}")

    yield

    skills_watcher.stop()
    from graph.subagent_archive import stop_subagent_archive
    stop_subagent_archive()
    if getattr(application.state, "cron_scheduler", None):
        await application.state.cron_scheduler.stop()
    await heartbeat_runner.stop()
    logger.info("Heartbeat stopped")


app = FastAPI(title="ClawChain", version="0.2.0", lifespan=lifespan)

_cors_origins_env = os.getenv("CLAWCHAIN_CORS_ORIGINS", "").strip()
if _cors_origins_env:
    _cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
else:
    _cors_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8002",
        "http://127.0.0.1:8002",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from api.chat import router as chat_router          # noqa: E402
from api.agents import router as agents_router      # noqa: E402
from api.sessions import router as sessions_router  # noqa: E402
from api.files import router as files_router        # noqa: E402
from api.compress import router as compress_router  # noqa: E402
from api.config_api import router as config_router  # noqa: E402
from api.events import router as events_router      # noqa: E402
from api.cron_api import router as cron_router      # noqa: E402
from api.approvals import router as approvals_router  # noqa: E402

app.include_router(chat_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(compress_router, prefix="/api")
app.include_router(config_router, prefix="/api")
app.include_router(events_router, prefix="/api")
app.include_router(cron_router, prefix="/api")
app.include_router(approvals_router, prefix="/api")


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Desktop sidecar liveness/readiness probe."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8002, reload=True)
