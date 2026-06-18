"""Admin role HTTP API (ported from OlcRTC-AdminVPS).

Auth: stateless session token in the ``X-Token`` header (CSRF-safe). Login is
rate-limited per client IP. The push receiver, login and external /api/v1 are
unauthenticated by password (authenticated by the node api_key / panel api_key).
"""

import json
import sqlite3
import time
import urllib.parse

from fastapi import APIRouter, Request, Response

from ..core import crypto, security

router = APIRouter(tags=["admin"])

_NODE_ACTIONS = {
    "get-user": "get_user", "set-user": "set_user", "create-user": "create_user",
    "start-user": "start_user", "stop-user": "stop_user", "delete-user": "delete_user",
    "start-all": "start_all", "stop-all": "stop_all", "restart-all": "restart_all",
}


def _mgr(request: Request):
    return request.app.state.manager


def _client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("X-Real-IP", "")
    if xri:
        return xri.strip()
    return request.client.host if request.client else "?"


def _authed(request: Request) -> bool:
    pw = _mgr(request).cfg.get("panel_password", "")
    if not pw:
        return True
    token = request.headers.get("X-Token", "").strip()
    return bool(token) and security.valid_session(token)


def _ok(data, code: int = 200) -> Response:
    return Response(json.dumps(data, ensure_ascii=False), status_code=code,
                    media_type="application/json")


def _unauth() -> Response:
    return _ok({"error": "Unauthorized"}, 401)


async def _json_body(request: Request) -> dict:
    return json.loads(await request.body())


# ── login ───────────────────────────────────────────────────────────────────--
@router.post("/api/login")
async def login(request: Request) -> Response:
    mgr = _mgr(request)
    pw_cfg = mgr.cfg.get("panel_password", "")
    if not pw_cfg:
        return _ok({"ok": True, "token": ""})
    ip = _client_ip(request)
    if security.login_blocked(ip):
        return _ok({"error": "Слишком много попыток. Попробуйте позже."}, 429)
    try:
        given = str((await _json_body(request)).get("password", ""))
    except Exception:
        return _ok({"error": "Invalid request"}, 400)
    if security.verify_password(given, pw_cfg):
        security.login_reset(ip)
        return _ok({"ok": True, "token": security.new_session()})
    security.login_record_fail(ip)
    return _ok({"error": "Неверный пароль"}, 401)


# ── dashboard data ────────────────────────────────────────────────────────────
@router.get("/api/data")
async def api_data(request: Request) -> Response:
    if not _authed(request):
        return _unauth()
    return _ok(_mgr(request).build_data())


# ── push receiver ─────────────────────────────────────────────────────────────
@router.post("/push/v1/{sid}")
async def handle_push(sid: str, request: Request) -> Response:
    mgr = _mgr(request)
    try:
        sid_i = int(sid)
    except ValueError:
        return Response("Bad server id", status_code=400, media_type="text/plain")
    srv = mgr.db.server_by_id(sid_i)
    if not srv:
        return Response("Unknown server", status_code=404, media_type="text/plain")
    raw = (await request.body()).decode(errors="ignore")
    try:
        payload = json.loads(crypto.decrypt(srv["api_key"], raw))
    except Exception:
        return Response("Bad request", status_code=400, media_type="text/plain")
    if abs(time.time() - payload.get("ts", 0)) > 60:
        return Response("Timestamp expired", status_code=400, media_type="text/plain")

    if payload.get("type") == "error":
        carrier = (payload.get("carrier") or "").capitalize()
        transport = (payload.get("transport") or "").capitalize()
        user_id = payload.get("user_id") or "?"
        error = payload.get("error") or "unknown error"
        ct = f"{carrier}-{transport}" if carrier else "Unknown"
        mgr.send_tg_alert_bg(f"{srv['name']}\n{ct}\nИнстанс {user_id} упал с ошибкой: {error}")
        return Response("ok", media_type="text/plain")

    mgr.cache_set(sid_i, {
        "online": True,
        "stats": payload.get("server", {}),
        "users": payload.get("users", []),
        "last_seen": time.time(),
        "last_push_at": time.time(),
        "masterdnsvpn": payload.get("masterdnsvpn"),
        "jitsi_domains": payload.get("jitsi_domains", ""),
    })
    return Response("ok", media_type="text/plain")


# ── external encrypted API ─────────────────────────────────────────────────────
@router.post("/api/v1")
async def api_v1(request: Request) -> Response:
    mgr = _mgr(request)
    key = mgr.cfg.get("api_key", "")
    if not key:
        return Response("API key not configured", status_code=503, media_type="text/plain")
    raw = (await request.body()).decode(errors="ignore")
    try:
        payload = json.loads(crypto.decrypt(key, raw))
    except Exception:
        return Response("Bad request", status_code=400, media_type="text/plain")
    if abs(time.time() - payload.get("ts", 0)) > 60:
        return Response("Timestamp expired", status_code=400, media_type="text/plain")
    if payload.get("action") == "list":
        result = mgr.api_v1_list()
    else:
        result = {"error": "unknown action"}
    return Response(crypto.encrypt(key, json.dumps(result).encode()), media_type="text/plain")


# ── settings ──────────────────────────────────────────────────────────────────
@router.post("/api/update")
async def self_update(request: Request) -> Response:
    if not _authed(request):
        return _unauth()
    from .. import updater
    if updater.is_up_to_date():
        return _ok({"ok": True, "up_to_date": True, "message": "Последняя версия уже установлена"})
    ok, msg = updater.start_update(updater.install_dir(), fetch_binary=False)
    return _ok({"ok": ok, "up_to_date": False, "message": msg})


@router.get("/api/updating")
async def updating(request: Request) -> Response:
    from .. import updater
    return _ok(updater.update_status())


@router.get("/api/version")
async def version(request: Request) -> Response:
    from .. import updater
    return _ok(updater.version_info())


@router.post("/api/poll-interval")
async def set_poll_interval(request: Request) -> Response:
    if not _authed(request):
        return _unauth()
    try:
        val = int((await _json_body(request)).get("seconds", 0))
    except Exception:
        return _ok({"error": "Invalid JSON"}, 400)
    if not (5 <= val <= 300):
        return _ok({"error": "Interval must be between 5 and 300 seconds"}, 400)
    _mgr(request).cfg.set("poll_interval", val)
    return _ok({"ok": True, "poll_interval": val})


@router.post("/api/tg-settings")
async def set_tg_settings(request: Request) -> Response:
    if not _authed(request):
        return _unauth()
    try:
        d = await _json_body(request)
    except Exception:
        return _ok({"error": "Invalid JSON"}, 400)
    mgr = _mgr(request)
    mgr.cfg.set("tg_bot_token", str(d.get("tg_bot_token", "")).strip())
    mgr.cfg.set("tg_recipients", str(d.get("tg_recipients", "")).strip())
    return _ok({"ok": True})


@router.post("/api/tg-updates")
async def get_tg_updates(request: Request) -> Response:
    if not _authed(request):
        return _unauth()
    try:
        token = str((await _json_body(request)).get("tg_bot_token", "")).strip()
    except Exception:
        return _ok({"error": "Invalid JSON"}, 400)
    if not token:
        return _ok({"error": "Bot token is required"}, 400)
    try:
        return _ok(_mgr(request).get_tg_updates(token))
    except Exception as e:
        return _ok({"error": str(e)}, 502)


# ── groups ────────────────────────────────────────────────────────────────────
@router.post("/api/groups/add")
async def add_group(request: Request) -> Response:
    if not _authed(request):
        return _unauth()
    try:
        name = (await _json_body(request)).get("name", "").strip()
    except Exception:
        return _ok({"error": "Invalid JSON"}, 400)
    if not name:
        return _ok({"error": "Group name is required"}, 400)
    try:
        new_id = _mgr(request).db.add_group(name)
        return _ok({"ok": True, "id": new_id, "name": name})
    except sqlite3.IntegrityError:
        return _ok({"error": "Group with this name already exists"}, 409)


@router.post("/api/groups/edit")
async def edit_group(request: Request) -> Response:
    if not _authed(request):
        return _unauth()
    mgr = _mgr(request)
    try:
        d = await _json_body(request)
    except Exception:
        return _ok({"error": "Invalid JSON"}, 400)
    gid, name = d.get("group_id"), d.get("name", "").strip()
    if not gid or not name:
        return _ok({"error": "Missing group_id or name"}, 400)
    if not mgr.db.group_by_id(gid):
        return _ok({"error": "Group not found"}, 404)
    try:
        mgr.db.edit_group(gid, name)
        return _ok({"ok": True})
    except sqlite3.IntegrityError:
        return _ok({"error": "Group with this name already exists"}, 409)


@router.post("/api/groups/delete")
async def del_group(request: Request) -> Response:
    if not _authed(request):
        return _unauth()
    mgr = _mgr(request)
    try:
        gid = (await _json_body(request))["group_id"]
    except Exception:
        return _ok({"error": "Invalid request"}, 400)
    if not mgr.db.group_by_id(gid):
        return _ok({"error": "Group not found"}, 404)
    if mgr.db.group_server_count(gid):
        return _ok({"error": "Cannot delete group that has servers"}, 409)
    mgr.db.del_group(gid)
    return _ok({"ok": True})


# ── servers ───────────────────────────────────────────────────────────────────
def _parse_ip(raw_url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(raw_url if "://" in raw_url else "http://" + raw_url)
    host = parsed.hostname or ""
    port = parsed.port or 8080
    return host, f"{host}:{port}"


@router.post("/api/servers/add")
async def add_server(request: Request) -> Response:
    if not _authed(request):
        return _unauth()
    mgr = _mgr(request)
    try:
        d = await _json_body(request)
    except Exception:
        return _ok({"error": "Invalid JSON"}, 400)
    api_key = d.get("api_key", "").strip()
    country = d.get("country", "").strip()
    name = d.get("name", "").strip()
    group_id = d.get("group_id")
    if not mgr.db.groups():
        return _ok({"error": "Create a group first"}, 400)
    if not group_id or not mgr.db.group_by_id(group_id):
        return _ok({"error": "Valid group_id is required"}, 400)
    try:
        host, ip = _parse_ip(d.get("ip", "").strip())
    except Exception:
        return _ok({"error": "Invalid API link"}, 400)
    if not all([host, api_key, country, name]):
        return _ok({"error": "Missing fields"}, 400)
    if not crypto.valid_api_key(api_key):
        return _ok({"error": "API key must be exactly 64 hex characters"}, 400)
    try:
        new_id = mgr.db.add_server(ip, api_key, country, name, group_id)
    except sqlite3.IntegrityError:
        return _ok({"error": "Server with this IP already exists"}, 409)
    new_srv = mgr.db.server_by_id(new_id)
    if new_srv:
        mgr.register_push_bg(new_srv)
    return _ok({"ok": True})


@router.post("/api/servers/edit")
async def edit_server(request: Request) -> Response:
    if not _authed(request):
        return _unauth()
    mgr = _mgr(request)
    try:
        d = await _json_body(request)
    except Exception:
        return _ok({"error": "Invalid JSON"}, 400)
    sid = d.get("server_id")
    api_key = d.get("api_key", "").strip()
    country = d.get("country", "").strip()
    name = d.get("name", "").strip()
    group_id = d.get("group_id")
    if not sid:
        return _ok({"error": "Missing server_id"}, 400)
    if group_id is not None and not mgr.db.group_by_id(group_id):
        return _ok({"error": "Invalid group_id"}, 400)
    srv = mgr.db.server_by_id(sid)
    if not srv:
        return _ok({"error": "Server not found"}, 404)
    try:
        host, ip = _parse_ip(d.get("ip", "").strip())
    except Exception:
        return _ok({"error": "Invalid API link"}, 400)
    if not all([host, country, name]):
        return _ok({"error": "Missing fields"}, 400)
    if api_key and not crypto.valid_api_key(api_key):
        return _ok({"error": "API key must be exactly 64 hex characters"}, 400)
    new_key = api_key or srv["api_key"]
    new_gid = group_id if group_id is not None else srv["group_id"]
    try:
        mgr.db.edit_server(sid, ip, new_key, country, name, new_gid)
    except sqlite3.IntegrityError:
        return _ok({"error": "Another server with this IP already exists"}, 409)
    updated = mgr.db.server_by_id(sid)
    if updated:
        mgr.register_push_bg(updated)
    return _ok({"ok": True})


@router.post("/api/servers/delete")
async def del_server(request: Request) -> Response:
    if not _authed(request):
        return _unauth()
    mgr = _mgr(request)
    try:
        sid = (await _json_body(request))["server_id"]
    except Exception:
        return _ok({"error": "Invalid request"}, 400)
    srv = mgr.db.server_by_id(sid)
    if not srv:
        return _ok({"error": "Server not found"}, 404)
    mgr.clear_push_bg(srv)
    mgr.db.del_server(sid)
    mgr.cache_drop(sid)
    return _ok({"ok": True})


@router.post("/api/servers/update")
async def update_server(request: Request) -> Response:
    if not _authed(request):
        return _unauth()
    mgr = _mgr(request)
    try:
        d = await _json_body(request)
        sid = d["server_id"]
        url = d.get("url", "").strip()
    except Exception:
        return _ok({"error": "Invalid request"}, 400)
    srv = mgr.db.server_by_id(sid)
    if not srv:
        return _ok({"error": "Server not found"}, 404)
    try:
        res = mgr.vps_call(srv["ip"], srv["api_key"], {"action": "update_panel", "url": url}, timeout=120)
    except Exception as e:
        return _ok({"error": str(e)}, 502)
    return _ok({"ok": True, "name": srv["name"], "message": res.get("message", ""),
                "up_to_date": bool(res.get("up_to_date"))})


@router.post("/api/servers/update-all")
async def update_all_servers(request: Request) -> Response:
    if not _authed(request):
        return _unauth()
    try:
        url = (await _json_body(request)).get("url", "").strip()
    except Exception:
        return _ok({"error": "Invalid request"}, 400)
    results = _mgr(request).update_all_servers(url)
    return _ok({"ok": True, "count": len(results), "results": results})


@router.post("/api/jitsi-domains/broadcast")
async def jitsi_broadcast(request: Request) -> Response:
    if not _authed(request):
        return _unauth()
    try:
        domains = (await _json_body(request)).get("domains", [])
    except Exception:
        return _ok({"error": "Invalid JSON"}, 400)
    if not isinstance(domains, list):
        return _ok({"error": "domains must be a list"}, 400)
    sent, errors = _mgr(request).broadcast_jitsi_domains(domains)
    return _ok({"ok": True, "sent": sent, "errors": errors})


# ── node proxy ────────────────────────────────────────────────────────────────
@router.post("/api/node/{action}")
async def node_proxy(action: str, request: Request) -> Response:
    if not _authed(request):
        return _unauth()
    node_action = _NODE_ACTIONS.get(action)
    if not node_action:
        return _ok({"error": "Not found"}, 404)
    mgr = _mgr(request)
    try:
        d = await _json_body(request)
    except Exception:
        return _ok({"error": "Invalid JSON"}, 400)
    sid = d.get("server_id")
    if not sid:
        return _ok({"error": "Missing server_id"}, 400)
    try:
        sid = int(sid)
    except (ValueError, TypeError):
        return _ok({"error": "Invalid server_id"}, 400)
    srv = mgr.db.server_by_id(sid)
    if not srv:
        return _ok({"error": "Server not found"}, 404)
    payload = {k: v for k, v in d.items() if k != "server_id"}
    payload["action"] = node_action
    try:
        res = mgr.vps_call(srv["ip"], srv["api_key"], payload, timeout=15)
    except Exception as e:
        return _ok({"error": f"Node unreachable: {e}"}, 502)
    return _ok(res)
