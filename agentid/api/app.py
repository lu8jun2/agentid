"""FastAPI application factory."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from agentid.api.middleware import OwnerSignatureMiddleware
from agentid.api.routes import agents, events, scores, auth, projects, network, friends, tasktree
from agentid.db.session import AsyncSessionLocal
from agentid.config import settings

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from agentid.worker.scheduler import start_scheduler as start_score_scheduler, stop_scheduler as stop_score_scheduler
    from agentid.worker.task_tree_worker import start_scheduler as start_tt_scheduler, stop_scheduler as stop_tt_scheduler
    start_score_scheduler()
    start_tt_scheduler(interval_minutes=5)
    log.info("AgentID API started — score + task_tree schedulers running")
    yield
    stop_tt_scheduler()
    stop_score_scheduler()
    log.info("AgentID API stopped — schedulers stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AgentID API",
        description="Decentralized identity and reputation for AI agents",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(OwnerSignatureMiddleware)

    app.include_router(agents.router, prefix="/v1/agents", tags=["agents"])
    app.include_router(events.router, prefix="/v1/events", tags=["events"])
    app.include_router(scores.router, prefix="/v1/scores", tags=["scores"])
    app.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
    app.include_router(projects.router, prefix="/v1/projects", tags=["projects"])
    app.include_router(network.router, prefix="/v1/network", tags=["network"])
    app.include_router(friends.router, prefix="/v1/friends", tags=["friends"])
    app.include_router(tasktree.router, prefix="/v1/tasktree", tags=["tasktree"])

    @app.get("/health")
    async def health():
        db_status = "ok"
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
        except Exception as e:
            db_status = f"error: {e}"
        return {
            "status": "ok" if db_status == "ok" else "degraded",
            "database": db_status,
            "version": "0.1.0",
        }

    return app


app = create_app()
