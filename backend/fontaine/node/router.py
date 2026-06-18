"""Node role HTTP API (ported from OlcRTC-VPS).

Two surfaces:
  - Password-authed web API (X-Token header; ?token= for EventSource/downloads),
    consumed by the FontaineRTC SPA: login, status, instance CRUD, config, logs.
  - Encrypted /api/v1 (Hash-CTR + HMAC, replay-guarded) for the admin panel.

The NodeManager lives on app.state.manager.
"""

import asyncio
import collections
import io
import json
import secrets
import time
import zipfile

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from .. import updater
from ..core import crypto, security
from ..core.compat import COMPAT_SET
from . import instance as inst
from . import sysinfo
from .wdtt import installer as wdtt_installer
from .wdtt.manager import WdttManager

router = APIRouter(tags=["node"])
_wdtt = WdttManager()


def _node_up_to_date() -> bool:
    """Up to date only when FontaineRTC, olcrtc AND (if present) WDTT are current."""
    if not updater.is_up_to_date(check_binary=True):
        return False
    if wdtt_installer.is_installed() and not wdtt_installer.is_up_to_date():
        return False
    return True


def _wdtt_block() -> dict:
    """WDTT state for the admin feed (list + push): status + users."""
    st = _wdtt.status()
    return {
        "installed": st["installed"], "active": st["active"],
        "main_password": st.get("main_password", ""),
        "version": wdtt_installer.installed_version(),
        "users": _wdtt.list_users(),
    }


def _node_update_extra():
    """Extra update step run before restart — refresh WDTT only if a newer WDTT
    release exists. If WDTT is already current, leave it untouched."""
    if wdtt_installer.is_installed() and not wdtt_installer.is_up_to_date():
        return wdtt_installer.reinstall_latest
    return None

# config keys the settings UI may change
_CONFIG_EDITABLE = {
    "dns", "debug", "full_logs", "socks_proxy", "socks_proxy_port", "jitsi_domains",
}


def _mgr(request: Request):
    return request.app.state.manager


def _ok(data, code: int = 200) -> Response:
    return Response(json.dumps(data, ensure_ascii=False), status_code=code,
                    media_type="application/json")


def _client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


def _token(request: Request) -> str:
    return (request.headers.get("X-Token", "")
            or request.query_params.get("token", "")).strip()


def _authed(request: Request) -> bool:
    pw = _mgr(request).cfg.get("panel_password", "")
    if not pw:
        return True
    tok = _token(request)
    return bool(tok) and security.valid_session(tok)


async def _json_body(request: Request) -> dict:
    raw = await request.body()
    return json.loads(raw) if raw else {}


# ── password-authed web API ─────────────────────────────────────────────────---
@router.post("/api/login")
async def login(request: Request) -> Response:
    mgr = _mgr(request)
    pw = mgr.cfg.get("panel_password", "")
    if not pw:
        return _ok({"ok": True, "token": ""})
    ip = _client_ip(request)
    if security.login_blocked(ip):
        return _ok({"error": "Слишком много попыток. Попробуйте позже."}, 429)
    try:
        given = str((await _json_body(request)).get("password", ""))
    except Exception:
        return _ok({"error": "Invalid request"}, 400)
    if security.verify_password(given, pw):
        security.login_reset(ip)
        return _ok({"ok": True, "token": security.new_session()})
    security.login_record_fail(ip)
    return _ok({"error": "Неверный пароль"}, 401)


@router.get("/api/status")
async def status(request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    mgr = _mgr(request)
    with mgr.lock:
        users = [inst.public(u) for u in mgr.users.values()]
    return _ok({
        "users": users,
        "server": sysinfo.server_stats(),
        "jitsi_domains": mgr.cfg.get("jitsi_domains", ""),
        "masterdnsvpn": sysinfo.masterdnsvpn_config(),
    })


@router.get("/api/config")
async def get_config(request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    cfg = _mgr(request).cfg.as_dict()
    cfg.pop("api_key", None)
    cfg.pop("panel_password", None)
    return _ok(cfg)


@router.post("/api/config/save")
async def save_config(request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    mgr = _mgr(request)
    try:
        data = await _json_body(request)
    except Exception:
        return _ok({"error": "invalid json"}, 400)
    for k, v in data.items():
        if k in _CONFIG_EDITABLE:
            mgr.cfg.set(k, v)
    return _ok({"ok": True})


@router.post("/api/update")
async def self_update(request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    if _node_up_to_date():
        return _ok({"ok": True, "up_to_date": True, "message": "Последняя версия уже установлена"})
    ok, msg = updater.start_update(updater.install_dir(), fetch_binary=True,
                                   extra=_node_update_extra())
    return _ok({"ok": ok, "up_to_date": False, "message": msg})


@router.get("/api/updating")
async def updating(request: Request) -> Response:
    from .. import updater
    return _ok(updater.update_status())


@router.get("/api/version")
async def version(request: Request) -> Response:
    info = updater.version_info(check_binary=True)
    w = wdtt_installer.version_info()
    info["wdtt"] = w
    # one update covers all three (FontaineRTC + olcrtc + WDTT), so surface any
    info["update_available"] = info["update_available"] or w["update_available"]
    return _ok(info)


@router.get("/api/genkey")
async def genkey(request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    return _ok({"key": secrets.token_hex(32)})


@router.post("/api/users/add")
async def add_user(request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    mgr = _mgr(request)
    try:
        data = await _json_body(request)
    except Exception:
        return _ok({"error": "invalid json"}, 400)
    carrier = data.get("carrier", "jitsi")
    transport = data.get("transport", "datachannel")
    if (carrier, transport) not in COMPAT_SET:
        return _ok({"error": "incompatible carrier/transport"}, 400)
    user = mgr.create_user(carrier, transport)
    return _ok(inst.public(user))


@router.post("/api/users/start-all")
async def start_all(request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    return _ok(_mgr(request).start_all())


@router.post("/api/users/stop-all")
async def stop_all(request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    return _ok(_mgr(request).stop_all())


@router.post("/api/users/restart-all")
async def restart_all(request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    return _ok(_mgr(request).restart_all())


@router.post("/api/users/start/{uid}")
async def start_one(uid: str, request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    mgr = _mgr(request)
    if uid not in mgr.users:
        return _ok({"error": "not found"}, 404)
    ok, msg = mgr.start_user(uid)
    return _ok({"ok": ok, "message": msg})


@router.post("/api/users/stop/{uid}")
async def stop_one(uid: str, request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    mgr = _mgr(request)
    if uid not in mgr.users:
        return _ok({"error": "not found"}, 404)
    mgr.stop_user(uid)
    return _ok({"ok": True})


@router.post("/api/users/delete/{uid}")
async def delete_one(uid: str, request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    if _mgr(request).delete_user(uid):
        return _ok({"ok": True})
    return _ok({"error": "not found"}, 404)


@router.post("/api/users/config/{uid}")
async def user_config(uid: str, request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    mgr = _mgr(request)
    try:
        data = await _json_body(request)
    except Exception:
        return _ok({"error": "invalid json"}, 400)
    with mgr.lock:
        if uid not in mgr.users:
            return _ok({"error": "not found"}, 404)
        u = mgr.users[uid]
        editable = ("carrier", "transport", "key", "custom_room_id", "current_room_id",
                    "preferred_carrier", "preferred_transport",
                    "max_session_duration", "jitsi_chosen_domain", "wb_token",
                    *inst.TRANSPORT_PARAM_DEFAULTS.keys())
        for f in editable:
            if f in data:
                u[f] = data[f]
        if "auto_restart" in data:
            u["auto_restart"] = bool(data["auto_restart"])
        mgr.save()
    mgr.notify_push()
    return _ok({"ok": True})


# ── encrypted external API (admin <-> node) ────────────────────────────────────
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
        return _enc(ak, {"error": "timestamp out of range"})

    action = payload.get("action")
    jd = mgr.cfg.get("jitsi_domains", "")

    if action == "list":
        with mgr.lock:
            users = [inst.public(u) for u in mgr.users.values()]
        return _enc(ak, {"users": users, "server": sysinfo.server_stats(),
                         "jitsi_domains": jd, "wdtt": _wdtt_block()})
    if action == "set_push_target":
        url = payload.get("url", "").strip()
        mgr.cfg.set("push_url", url)
        if url:
            mgr.notify_push()
        return _enc(ak, {"ok": True})
    if action == "get_user":
        uid = payload.get("id", "").strip()
        with mgr.lock:
            if uid not in mgr.users:
                return _enc(ak, {"error": "user not found"})
            return _enc(ak, inst.full(mgr.users[uid], jd))
    if action == "set_user":
        uid = payload.get("id", "").strip()
        with mgr.lock:
            if uid not in mgr.users:
                return _enc(ak, {"error": "user not found"})
            u = mgr.users[uid]
            nc = payload.get("carrier", u.get("carrier"))
            nt = payload.get("transport", u.get("transport"))
            if (nc, nt) not in COMPAT_SET:
                return _enc(ak, {"error": "incompatible carrier/transport"})
            for f in ("carrier", "transport", "wb_token", "max_session_duration",
                      *inst.TRANSPORT_PARAM_DEFAULTS.keys()):
                if f in payload:
                    u[f] = payload[f]
            if "room_id" in payload:
                u["custom_room_id"] = payload["room_id"]
            if "jitsi_domain" in payload:
                u["jitsi_chosen_domain"] = payload["jitsi_domain"]
            if "auto_restart" in payload:
                u["auto_restart"] = bool(payload["auto_restart"])
            mgr.save()
        mgr.notify_push()
        return _enc(ak, {"ok": True})
    if action == "create_user":
        carrier = payload.get("carrier", "jitsi")
        transport = payload.get("transport", "datachannel")
        if (carrier, transport) not in COMPAT_SET:
            return _enc(ak, {"error": "incompatible carrier/transport"})
        return _enc(ak, inst.full(mgr.create_user(carrier, transport), jd))
    if action == "start_user":
        uid = payload.get("id", "").strip()
        if uid not in mgr.users:
            return _enc(ak, {"error": "user not found"})
        ok, msg = mgr.start_user(uid)
        return _enc(ak, {"ok": ok, "message": msg})
    if action == "stop_user":
        uid = payload.get("id", "").strip()
        if uid not in mgr.users:
            return _enc(ak, {"error": "user not found"})
        mgr.stop_user(uid)
        return _enc(ak, {"ok": True})
    if action == "delete_user":
        uid = payload.get("id", "").strip()
        return _enc(ak, {"ok": True} if mgr.delete_user(uid) else {"error": "user not found"})
    if action == "start_all":
        return _enc(ak, {"ok": True, **mgr.start_all()})
    if action == "stop_all":
        return _enc(ak, {"ok": True, **mgr.stop_all()})
    if action == "restart_all":
        return _enc(ak, {"ok": True, **mgr.restart_all()})
    if action == "set_jitsi_domains":
        domains = payload.get("domains", "")
        if not isinstance(domains, (str, list)):
            return _enc(ak, {"error": "domains must be a string or list"})
        raw_list = ([str(d).strip() for d in domains if str(d).strip()]
                    if isinstance(domains, list)
                    else [d.strip() for d in domains.split("\n") if d.strip()])
        normalized = "\n".join(
            d if d.startswith(("http://", "https://")) else "https://" + d for d in raw_list)
        mgr.cfg.set("jitsi_domains", normalized)
        return _enc(ak, {"ok": True})
    if action == "update_panel":
        if _node_up_to_date():
            return _enc(ak, {"ok": True, "up_to_date": True,
                             "message": "Последняя версия уже установлена"})
        ok, msg = updater.start_update(updater.install_dir(), fetch_binary=True,
                                       extra=_node_update_extra())
        return _enc(ak, {"ok": ok, "up_to_date": False, "message": msg})

    # ── WDTT actions (used by the admin panel) ──
    if action == "wdtt_status":
        return _enc(ak, _wdtt_block())
    if action == "wdtt_list":
        return _enc(ak, {"users": _wdtt.list_users()})
    if action == "wdtt_add":
        try:
            res = _wdtt.add_user(days=int(payload.get("days", 30)),
                                 password=str(payload.get("password", "")),
                                 host=str(payload.get("host", "")),
                                 vk_hash=str(payload.get("vk_hash", "")))
        except ValueError as e:
            return _enc(ak, {"error": str(e)})
        mgr.notify_push()
        return _enc(ak, {"ok": True, **res})
    if action == "wdtt_del":
        ok = _wdtt.del_user(str(payload.get("password", "")))
        if ok:
            mgr.notify_push()
        return _enc(ak, {"ok": True} if ok else {"error": "not found"})
    if action == "wdtt_toggle":
        ok = _wdtt.set_deactivated(str(payload.get("password", "")), bool(payload.get("deactivated")))
        if ok:
            mgr.notify_push()
        return _enc(ak, {"ok": True} if ok else {"error": "not found"})

    return _enc(ak, {"error": "unknown action"}, 400)


def _enc(api_key: str, data: dict, code: int = 200) -> Response:
    return Response(crypto.encrypt(api_key, json.dumps(data).encode()),
                    media_type="text/plain", status_code=code)


# ── SSE log stream + downloads (token via query for EventSource/links) ─────────-
@router.get("/api/logs/stream/{uid}", response_model=None)
async def sse(uid: str, request: Request):
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    mgr = _mgr(request)
    q: collections.deque = collections.deque()
    with mgr.lock:
        if uid not in mgr.users:
            return Response(status_code=404)
        mgr.subs.setdefault(uid, []).append(q)
        for line in mgr.log_bufs.get(uid, []):
            q.append(line)

    async def gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                drained = False
                while q:
                    yield f"data: {q.popleft()}\n\n"
                    drained = True
                if not drained:
                    yield "data: :ka\n\n"
                await asyncio.sleep(0.3)
        finally:
            with mgr.lock:
                subs = mgr.subs.get(uid)
                if subs and q in subs:
                    subs.remove(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@router.get("/api/logs/download/{uid}")
async def log_download(uid: str, request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    mgr = _mgr(request)
    with mgr.lock:
        if uid not in mgr.users:
            return Response(status_code=404)
        full = bool(mgr.cfg.get("full_logs"))
        snapshot = list(mgr.log_bufs.get(uid, []))
    data = mgr.read_log_for_download(uid, full, snapshot)
    fname = f'olcrtc-{uid[:8]}-{time.strftime("%Y-%m-%d-%H-%M-%S")}.txt'
    return Response(content=data, media_type="text/plain",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.get("/api/logs/download-all")
async def log_download_all(request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    mgr = _mgr(request)
    with mgr.lock:
        full = bool(mgr.cfg.get("full_logs"))
        meta = [(uid, u.get("carrier", ""), u.get("transport", ""),
                 list(mgr.log_bufs.get(uid, [])))
                for uid, u in mgr.users.items() if u.get("running")]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for uid, carrier, transport, snapshot in meta:
            body = mgr.read_log_for_download(uid, full, snapshot)
            zf.writestr(f"olcrtc-{uid[:8]}-{carrier}-{transport}.log", body)
    fname = f'olcrtc-all-{time.strftime("%Y-%m-%d-%H-%M-%S")}.zip'
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ── WDTT subsystem (second protocol) ───────────────────────────────────────────
@router.get("/api/wdtt")
async def wdtt_overview(request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    return _ok({**_wdtt.status(), "users": _wdtt.list_users(),
                "version": wdtt_installer.installed_version()})


@router.get("/api/wdtt/installing")
async def wdtt_installing(request: Request) -> Response:
    return _ok(wdtt_installer.install_status())


@router.post("/api/wdtt/users/add")
async def wdtt_add(request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    d = await _json_body(request)
    try:
        res = _wdtt.add_user(days=int(d.get("days", 30)), password=str(d.get("password", "")),
                             host=str(d.get("host", "")), vk_hash=str(d.get("vk_hash", "")))
    except ValueError as e:
        return _ok({"error": str(e)}, 400)
    _mgr(request).notify_push()   # push fresh WDTT state to the admin immediately
    return _ok({"ok": True, **res})


@router.post("/api/wdtt/users/delete")
async def wdtt_del(request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    pw = str((await _json_body(request)).get("password", ""))
    ok = _wdtt.del_user(pw)
    if ok:
        _mgr(request).notify_push()
    return _ok({"ok": True} if ok else {"error": "not found"})


@router.post("/api/wdtt/users/toggle")
async def wdtt_toggle(request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    d = await _json_body(request)
    ok = _wdtt.set_deactivated(str(d.get("password", "")), bool(d.get("deactivated")))
    if ok:
        _mgr(request).notify_push()
    return _ok({"ok": True} if ok else {"error": "not found"})


@router.post("/api/wdtt/install")
async def wdtt_install(request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    d = await _json_body(request)
    from .wdtt.manager import gen_password
    main_pw = str(d.get("main_password", "")).strip() or gen_password()
    ok, msg = wdtt_installer.start_install(
        dtls_port=int(d.get("dtls_port", 56000)), wg_port=int(d.get("wg_port", 56001)),
        ssh_port=int(d.get("ssh_port", 22)), main_password=main_pw,
        dns=str(d.get("dns", "1.1.1.1")))
    return _ok({"ok": ok, "message": msg, "main_password": main_pw if ok else ""})


@router.post("/api/wdtt/uninstall")
async def wdtt_uninstall(request: Request) -> Response:
    if not _authed(request):
        return _ok({"error": "Unauthorized"}, 401)
    ok, msg = wdtt_installer.start_uninstall()
    return _ok({"ok": ok, "message": msg})
