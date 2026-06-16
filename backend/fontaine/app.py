"""FastAPI application factory.

Mounts routers and background workers according to the configured role so a
single codebase serves both the node and the admin panel.
"""

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Role, get_settings


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = get_settings()
    if settings.role is Role.node:
        from .node.manager import NodeManager
        from .node import push, workers

        mgr = NodeManager(settings)
        push.register(mgr)
        app.state.manager = mgr

        stop = threading.Event()
        app.state.worker_stop = stop
        threads = [
            threading.Thread(target=workers.watchdog, args=(mgr, stop), daemon=True),
            threading.Thread(target=workers.traffic_monitor, args=(mgr, stop), daemon=True),
            threading.Thread(target=push.push_worker, args=(mgr, stop), daemon=True),
        ]
        for t in threads:
            t.start()
        mgr.recover()  # respawn instances that were running before restart
        try:
            yield
        finally:
            stop.set()
            mgr.push_event.set()  # unblock push worker
            with mgr.lock:
                for uid in list(mgr.procs):
                    mgr._stop_proc_locked(uid)
    else:
        from .admin.manager import AdminManager

        mgr = AdminManager(settings)
        app.state.manager = mgr

        stop = threading.Event()
        app.state.worker_stop = stop
        poller = threading.Thread(target=mgr.poll_loop, args=(stop,), daemon=True)
        poller.start()
        try:
            yield
        finally:
            stop.set()
            mgr.db.checkpoint()


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
