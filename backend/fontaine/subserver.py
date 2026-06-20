"""olcrtc subscription server — a second HTTP listener on its own port.

Serves a plain-text subscription file (see olcrtc docs/sub.md) so client apps can
import all instances at once. Runs in the same process as the panel via a second
uvicorn server whose lifecycle (start / stop / change port) is driven at runtime
from the settings modal — no service restart needed.

- node role  : lists this node's own instances.
- admin role : lists instances aggregated from every registered node.

The endpoint is intentionally unauthenticated (clients fetch it directly); it only
serves content while the owner has explicitly enabled it.
"""

import asyncio
import time

from fastapi import FastAPI, Response
from uvicorn import Config, Server

DEFAULTS = {"enabled": False, "name": "FontaineRTC", "refresh": "10m", "port": 8081}


def sub_settings(mgr) -> dict:
    """Current subscription settings from the role's config store."""
    return {
        "enabled": bool(mgr.cfg.get("sub_enabled", DEFAULTS["enabled"])),
        "name": mgr.cfg.get("sub_name", DEFAULTS["name"]) or DEFAULTS["name"],
        "refresh": mgr.cfg.get("sub_refresh", DEFAULTS["refresh"]) or DEFAULTS["refresh"],
        "port": int(mgr.cfg.get("sub_port", DEFAULTS["port"]) or DEFAULTS["port"]),
    }


# ── subscription file rendering ─────────────────────────────────────────────────
def _header(s: dict) -> list[str]:
    return [f"#name: {s['name']}", f"#update: {int(time.time())}", f"#refresh: {s['refresh']}", ""]


def _render_node(mgr) -> str | None:
    s = sub_settings(mgr)
    if not s["enabled"]:
        return None
    from .node import instance as inst
    with mgr.lock:
        users = [inst.public(u) for u in mgr.users.values()]
    out = _header(s)
    for u in users:
        uri = u.get("uri", "")
        if not uri:
            continue
        out += [uri, f"##name: {u.get('carrier', '')}/{u.get('transport', '')}", ""]
    return "\n".join(out)


def _render_admin(mgr) -> str | None:
    s = sub_settings(mgr)
    if not s["enabled"]:
        return None
    out = _header(s)
    for srv in mgr.build_data().get("servers", []):
        for vu in srv.get("users", []):
            uri = vu.get("uri", "")
            if not uri:
                continue
            out += [uri, f"##name: {srv.get('name', '')}"]
            if srv.get("country"):
                out.append(f"##comment: {srv['country']}")
            out.append("")
    return "\n".join(out)


# ── the second HTTP server (runtime-managed lifecycle) ──────────────────────────
class SubServer:
    def __init__(self, mgr, render) -> None:
        self.mgr = mgr
        self._render = render
        self._app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

        @self._app.get("/")
        @self._app.get("/sub")
        async def _sub() -> Response:
            text = self._render(self.mgr)
            if text is None:
                return Response("Subscription disabled", status_code=404)
            return Response(text, media_type="text/plain; charset=utf-8")

        self._server: Server | None = None
        self._task: asyncio.Task | None = None
        self._port: int | None = None

    async def apply_from_cfg(self) -> None:
        s = sub_settings(self.mgr)
        await self.apply(s["enabled"], s["port"])

    async def apply(self, enabled: bool, port: int) -> None:
        if not enabled:
            await self._stop()
            return
        if self._task and not self._task.done() and self._port == port:
            return                      # already serving on this port
        await self._stop()
        await self._start(port)

    async def _start(self, port: int) -> None:
        config = Config(self._app, host="0.0.0.0", port=port,
                        log_level="warning", timeout_graceful_shutdown=3)
        server = Server(config)
        server.install_signal_handlers = lambda: None   # we're not the main server

        async def _serve() -> None:
            try:
                await server.serve()
            except Exception as e:               # e.g. port already in use
                print(f"[subserver] failed on port {port}: {e}")

        self._server = server
        self._port = port
        self._task = asyncio.create_task(_serve())

    async def _stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                self._task.cancel()
        self._server = self._task = self._port = None


# ── module singleton (so routers can re-apply after a settings change) ───────────
_instance: SubServer | None = None


def init(mgr, role) -> SubServer:
    """Create the singleton for this role (does not start it)."""
    global _instance
    from .config import Role
    render = _render_node if role is Role.node else _render_admin
    _instance = SubServer(mgr, render)
    return _instance


def save_settings(mgr, d: dict, main_port: int) -> str:
    """Persist subscription settings from a request dict. Returns '' on success
    or a human-readable error message."""
    try:
        port = int(d.get("port", DEFAULTS["port"]))
    except (TypeError, ValueError):
        return "Некорректный порт"
    if not (1 <= port <= 65535):
        return "Порт должен быть в диапазоне 1–65535"
    if port == main_port:
        return f"Порт {port} занят самой панелью"
    mgr.cfg.set("sub_enabled", bool(d.get("enabled")))
    mgr.cfg.set("sub_name", str(d.get("name", "")).strip() or DEFAULTS["name"])
    mgr.cfg.set("sub_refresh", str(d.get("refresh", "")).strip() or DEFAULTS["refresh"])
    mgr.cfg.set("sub_port", port)
    return ""


async def apply_current() -> None:
    if _instance is not None:
        await _instance.apply_from_cfg()


async def shutdown() -> None:
    global _instance
    if _instance is not None:
        await _instance._stop()
        _instance = None
