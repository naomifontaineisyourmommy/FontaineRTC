"""Node role HTTP API (ported from OlcRTC-VPS).

    POST /api/v1                -> encrypted node API (Hash-CTR + HMAC, replay-guarded)
    GET  /sse/{uid}             -> live log stream (Server-Sent Events)
    GET  /logs/{uid}/download   -> per-instance log download

The dashboard SPA is served by web.py. The NodeManager lives on app.state.manager.
"""

import asyncio
import collections
import json
import time

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from ..core import crypto
from ..core.compat import COMPAT_SET
from . import instance as inst

router = APIRouter(tags=["node"])


def _mgr(request: Request):
    return request.app.state.manager


def _enc_response(api_key: str, data: dict, code: int = 200) -> Response:
    body = crypto.encrypt(api_key, json.dumps(data).encode())
    return Response(content=body, media_type="text/plain", status_code=code)


@router.post("/api/v1")
async def api_v1(request: Request) -> Response:
    mgr = _mgr(request)
    ak = mgr.cfg.get("api_key", "")
    if not ak:
        return Response(status_code=503)
    raw = (await request.body()).decode().strip()
    try:
        payload = json.loads(crypto.decrypt(ak, raw))
    except Exception:
        return Response(status_code=403)
    if abs(time.time() - payload.get("ts", 0)) > 60:
        return _enc_response(ak, {"error": "timestamp out of range"})

    action = payload.get("action")
    jd = mgr.cfg.get("jitsi_domains", "")

    if action == "list":
        with mgr.lock:
            users = [inst.public(u) for u in mgr.users.values()]
        for u in users:
            u.pop("wb_token", None)   # node-local; never leaves the node
        return _enc_response(ak, {"users": users, "server": _server_stats()})

    if action == "set_push_target":
        url = payload.get("url", "").strip()
        mgr.cfg.set("push_url", url)
        if url:
            mgr.panel_log(f"[PUSH] target set: {url}")
            mgr.notify_push()
        else:
            mgr.panel_log("[PUSH] push disabled")
        return _enc_response(ak, {"ok": True})

    if action == "get_user":
        uid = payload.get("id", "").strip()
        with mgr.lock:
            if uid not in mgr.users:
                return _enc_response(ak, {"error": "user not found"})
            return _enc_response(ak, inst.full(mgr.users[uid], jd))

    if action == "set_user":
        uid = payload.get("id", "").strip()
        with mgr.lock:
            if uid not in mgr.users:
                return _enc_response(ak, {"error": "user not found"})
            u = mgr.users[uid]
            new_carrier = payload.get("carrier", u.get("carrier"))
            new_transport = payload.get("transport", u.get("transport"))
            if (new_carrier, new_transport) not in COMPAT_SET:
                return _enc_response(ak, {"error": "incompatible carrier/transport"})
            editable = ("carrier", "transport", *inst.TRANSPORT_PARAM_DEFAULTS.keys())
            for f in editable:
                if f in payload:
                    u[f] = payload[f]
            if "room_id" in payload:
                u["custom_room_id"] = payload["room_id"]
            if "jitsi_domain" in payload:
                u["jitsi_chosen_domain"] = payload["jitsi_domain"]
            if "auto_restart" in payload:
                u["auto_restart"] = bool(payload["auto_restart"])
            mgr.save()
        return _enc_response(ak, {"ok": True})

    if action == "create_user":
        carrier = payload.get("carrier", "jitsi")
        transport = payload.get("transport", "datachannel")
        if (carrier, transport) not in COMPAT_SET:
            return _enc_response(ak, {"error": "incompatible carrier/transport"})
        user = mgr.create_user(carrier, transport)
        return _enc_response(ak, inst.full(user, jd))

    if action == "start_user":
        uid = payload.get("id", "").strip()
        if uid not in mgr.users:
            return _enc_response(ak, {"error": "user not found"})
        ok, msg = mgr.start_user(uid)
        return _enc_response(ak, {"ok": ok, "message": msg})

    if action == "stop_user":
        uid = payload.get("id", "").strip()
        if uid not in mgr.users:
            return _enc_response(ak, {"error": "user not found"})
        mgr.stop_user(uid)
        return _enc_response(ak, {"ok": True})

    if action == "delete_user":
        uid = payload.get("id", "").strip()
        if mgr.delete_user(uid):
            return _enc_response(ak, {"ok": True})
        return _enc_response(ak, {"error": "user not found"})

    if action == "start_all":
        return _enc_response(ak, {"ok": True, **mgr.start_all()})
    if action == "stop_all":
        return _enc_response(ak, {"ok": True, **mgr.stop_all()})
    if action == "restart_all":
        return _enc_response(ak, {"ok": True, **mgr.restart_all()})

    if action == "set_jitsi_domains":
        domains = payload.get("domains", "")
        if not isinstance(domains, (str, list)):
            return _enc_response(ak, {"error": "domains must be a string or list"})
        if isinstance(domains, list):
            raw_list = [str(d).strip() for d in domains if str(d).strip()]
        else:
            raw_list = [d.strip() for d in domains.split("\n") if d.strip()]
        normalized = "\n".join(
            d if d.startswith(("http://", "https://")) else "https://" + d
            for d in raw_list
        )
        mgr.cfg.set("jitsi_domains", normalized)
        return _enc_response(ak, {"ok": True})

    if action == "update_panel":
        # Self-update is replaced by the deploy pipeline in migration phase 5.
        return _enc_response(ak, {"ok": False, "message": "update_panel not yet implemented"})

    return _enc_response(ak, {"error": "unknown action"}, 400)


def _server_stats() -> dict:
    from . import sysinfo
    return sysinfo.server_stats()


@router.get("/sse/{uid}")
async def sse(uid: str, request: Request) -> StreamingResponse:
    mgr = _mgr(request)
    q: collections.deque = collections.deque()
    with mgr.lock:
        if uid not in mgr.users:
            return Response(status_code=404)
        mgr.subs.setdefault(uid, []).append(q)
        # prime with current buffer
        for line in mgr.log_bufs.get(uid, []):
            q.append(line)

    async def gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                drained = False
                while q:
                    line = q.popleft()
                    yield f"data: {json.dumps(line)}\n\n"
                    drained = True
                if not drained:
                    yield ": keepalive\n\n"
                await asyncio.sleep(0.25)
        finally:
            with mgr.lock:
                subs = mgr.subs.get(uid)
                if subs and q in subs:
                    subs.remove(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/logs/{uid}/download")
async def log_download(uid: str, request: Request, full: bool = True) -> Response:
    mgr = _mgr(request)
    with mgr.lock:
        if uid not in mgr.users:
            return Response(status_code=404)
        snapshot = list(mgr.log_bufs.get(uid, []))
    data = mgr.read_log_for_download(uid, full and bool(mgr.cfg.get("full_logs")), snapshot)
    return Response(
        content=data,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{uid}.txt"'},
    )
