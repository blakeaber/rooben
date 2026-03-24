"""FastAPI app factory for the Rooben dashboard."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env file before any env var access
load_dotenv()

try:
    import asyncpg
except ImportError:
    asyncpg = None  # type: ignore[assignment]

from fastapi import Depends, FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from rooben.dashboard.auth import get_auth_dependency  # noqa: E402
from rooben.dashboard.deps import DashboardDeps, get_deps, set_deps  # noqa: E402

logger = logging.getLogger("rooben.dashboard")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create DB pool on startup, close on shutdown."""
    from rooben.config import get_settings
    _cfg = get_settings()
    dsn = _cfg.database_url
    pool = None
    if dsn and asyncpg:
        pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
        # Apply any missing tables/columns from init.sql + migrations
        try:
            scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / "scripts"
            init_sql = scripts_dir / "init.sql"
            if init_sql.exists():
                sql = init_sql.read_text()
                async with pool.acquire() as conn:
                    await conn.execute(sql)
                # Apply incremental migrations
                migrations_dir = scripts_dir / "migrations"
                if migrations_dir.is_dir():
                    for mig in sorted(migrations_dir.glob("*.sql")):
                        async with pool.acquire() as conn:
                            await conn.execute(mig.read_text())
        except Exception:
            logger.warning("Failed to apply schema on startup — tables may need manual migration")
    else:
        if not dsn:
            logger.warning(
                "DATABASE_URL is not set. Database features will be unavailable. "
                "Set DATABASE_URL in your .env file or environment. "
                "See .env.example for reference."
            )
        if not asyncpg:
            logger.warning("asyncpg is not installed. Install with: pip install rooben[dashboard]")
    learning_path = _cfg.rooben_learning_store_path or None

    set_deps(DashboardDeps(
        pool=pool,
        learning_store_path=learning_path,
    ))

    # Populate credential cache for env var fallback
    if pool:
        try:
            from rooben.agents.integrations import populate_credential_cache
            await populate_credential_cache(pool)
        except Exception:
            pass

    # Recover orphaned workflows stuck in non-terminal states from a prior crash
    if pool:
        try:
            result = await pool.execute(
                """UPDATE workflows SET status = 'failed', completed_at = now()
                   WHERE status IN ('planning', 'in_progress')""",
            )
            # Also mark their non-terminal tasks as cancelled
            await pool.execute(
                """UPDATE tasks SET status = 'cancelled'
                   WHERE workflow_id IN (
                       SELECT id FROM workflows WHERE status = 'failed' AND completed_at > now() - interval '5 seconds'
                   ) AND status NOT IN ('passed', 'failed', 'skipped', 'cancelled')""",
            )
            logger.info("Orphan recovery complete: %s", result)
        except Exception:
            pass

    # Run Pro extension startup if available
    from rooben.extensions.registry import run_pro_startup
    deps = get_deps()
    await run_pro_startup(pool, deps)

    yield

    # Run Pro extension shutdown if available
    from rooben.extensions.registry import run_pro_shutdown
    deps = get_deps()
    await run_pro_shutdown(pool, deps)

    if pool:
        await pool.close()


def create_app(static_dir: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Rooben Dashboard API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — allow Next.js dev server and production origins
    cors_origins = [
        "http://localhost:3000",
        "http://localhost:8420",
    ]
    from rooben.config import get_settings as _get_settings
    extra_origins = _get_settings().rooben_cors_origins
    if extra_origins:
        cors_origins.extend(o.strip() for o in extra_origins.split(",") if o.strip())

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handler — ensures unhandled errors return a proper
    # JSON response so the CORS middleware can attach headers (otherwise
    # the browser blocks the response entirely, masking the real error).
    @app.exception_handler(Exception)
    async def _global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # Auth dependency — resolved at request time so Pro can override
    from rooben.dashboard.models.user import CurrentUser

    async def _resolve_auth(request: Request) -> CurrentUser:
        return await get_auth_dependency()(request)

    auth_deps = [Depends(_resolve_auth)]

    # ── OSS routes — always available ──────────────────────────────────────
    from rooben.dashboard.routes.workflows import router as wf_router
    from rooben.dashboard.routes.tasks import router as task_router
    from rooben.dashboard.routes.agents import router as agent_router
    from rooben.dashboard.routes.events import router as events_router
    from rooben.dashboard.routes.run import router as run_router
    from rooben.dashboard.routes.refine import router as refine_router
    from rooben.dashboard.routes.integrations import router as integ_router
    from rooben.dashboard.routes.lifecycle import router as lifecycle_router
    from rooben.dashboard.routes.workspace import router as workspace_router
    from rooben.dashboard.routes.chat import router as chat_router
    from rooben.dashboard.routes.credentials import router as cred_router
    from rooben.dashboard.routes.presets import router as preset_router
    from rooben.dashboard.routes.me import router as me_router
    from rooben.dashboard.routes.community import router as community_router
    from rooben.dashboard.routes.features import router as features_router
    from rooben.dashboard.routes.extensions_api import router as extensions_router
    from rooben.dashboard.routes.hub import router as hub_router

    app.include_router(wf_router, dependencies=auth_deps)
    app.include_router(task_router, dependencies=auth_deps)
    app.include_router(agent_router, dependencies=auth_deps)
    app.include_router(events_router)  # WebSocket handles its own auth
    app.include_router(run_router, dependencies=auth_deps)
    app.include_router(refine_router, dependencies=auth_deps)
    app.include_router(integ_router, dependencies=auth_deps)
    app.include_router(lifecycle_router, dependencies=auth_deps)
    app.include_router(workspace_router, dependencies=auth_deps)
    app.include_router(chat_router, dependencies=auth_deps)
    app.include_router(cred_router, dependencies=auth_deps)
    app.include_router(preset_router, dependencies=auth_deps)
    app.include_router(me_router, dependencies=auth_deps)
    app.include_router(community_router, dependencies=auth_deps)
    app.include_router(features_router)  # Public — no auth needed
    app.include_router(extensions_router, dependencies=auth_deps)
    app.include_router(hub_router, dependencies=auth_deps)

    # ── Pro routes — loaded via extension system ───────────────────────────
    from rooben.extensions.registry import get_pro_routers
    for route_info in get_pro_routers():
        app.include_router(route_info["router"], **route_info.get("kwargs", {}))

    # ── Public routes (no auth) ────────────────────────────────────────────
    # Waitlist is OSS; invite is loaded from Pro if available
    from rooben.dashboard.routes.waitlist import router as waitlist_router
    app.include_router(waitlist_router)  # Waitlist — public, no auth

    # Health endpoint — unauthenticated (Docker healthcheck)
    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    # Serve Next.js static export in production
    resolved_static = static_dir or _get_settings().rooben_static_dir or None
    if resolved_static:
        static_path = Path(resolved_static)
        if static_path.exists():
            app.mount("/", StaticFiles(directory=str(static_path), html=True))

    return app
