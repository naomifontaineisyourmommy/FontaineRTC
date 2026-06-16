"""FastAPI application factory.

Mounts routers and background workers according to the configured role so a
single codebase serves both the node and the admin panel.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Role, get_settings


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = get_settings()
    # Per-role startup (process manager / poller) is wired up during migration.
    if settings.role is Role.node:
        pass  # TODO(phase 2): start watchdog + traffic monitor + push worker
    else:
        pass  # TODO(phase 3): start poller + telegram alerter
    yield
    # Per-role shutdown (stop workers, terminate child processes).


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"FontaineRTC ({settings.role.value})",
        version="0.1.0",
        lifespan=_lifespan,
    )

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "role": settings.role.value}

    if settings.role is Role.node:
        from .node.router import router as node_router

        app.include_router(node_router)
    else:
        from .admin.router import router as admin_router

        app.include_router(admin_router)

    # SPA is served last so API routes take precedence. Enabled once built.
    # from .web import mount_spa
    # mount_spa(app)

    return app
