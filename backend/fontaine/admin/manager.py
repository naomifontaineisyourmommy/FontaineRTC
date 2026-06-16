"""AdminManager — node client, state cache, poller, Telegram, aggregation.

Ported from OlcRTC-AdminVPS. Synchronous (urllib + sqlite3) so it runs cleanly
in the background poller thread; the FastAPI handlers call into it directly.
"""

import json
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from ..config import Settings
from ..core import crypto
from .config_store import AdminConfig
from .db import AdminDB
from .flags import flag

_EMPTY_CACHE = {
    "online": False, "stats": {}, "users": [],
    "last_seen": 0, "last_push_at": 0, "masterdnsvpn": None, "jitsi_domains": "",
}


class AdminManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cfg = AdminConfig(settings)
        self.db = AdminDB(settings)
        self._cache: dict[int, dict] = {}
        self._cache_lock = threading.Lock()
        self._push_register_times: dict[int, float] = {}

    # ── node API client ──────────────────────────────────────────────────────--
    def vps_call(self, ip: str, api_key: str, payload: dict, timeout: int = 10) -> dict:
        payload = {**payload, "ts": int(time.time())}
        body = crypto.encrypt(api_key, json.dumps(payload).encode()).encode()
        req = urllib.request.Request(
            f"http://{ip}/api/v1", data=body,
            headers={"Content-Type": "text/plain"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
        return json.loads(crypto.decrypt(api_key, raw))

    def vps_list(self, ip: str, key: str) -> dict:
        return self.vps_call(ip, key, {"action": "list"})

    def register_push(self, srv: dict) -> None:
        base = self.cfg.get("panel_url", "").rstrip("/")
        if not base:
            print(f"[push] panel_url not set — skip push registration for {srv['name']}")
            return
        endpoint = f"{base}/push/v1/{srv['id']}"
        try:
            self.vps_call(srv["ip"], srv["api_key"],
                          {"action": "set_push_target", "url": endpoint})
            print(f"[push] registered {srv['name']} -> {endpoint}")
        except Exception as e:
            print(f"[push] could not register {srv['name']}: {e}")

    def clear_push(self, srv: dict) -> None:
        try:
            self.vps_call(srv["ip"], srv["api_key"],
                          {"action": "set_push_target", "url": ""})
        except Exception as e:
            print(f"[push] could not clear {srv['name']}: {e}")

    def register_push_bg(self, srv: dict) -> None:
        threading.Thread(target=self.register_push, args=(dict(srv),), daemon=True).start()

    def clear_push_bg(self, srv: dict) -> None:
        threading.Thread(target=self.clear_push, args=(dict(srv),), daemon=True).start()

    # ── cache ────────────────────────────────────────────────────────────────--
    def cache_get(self, sid: int) -> dict:
        with self._cache_lock:
            return dict(self._cache.get(sid, _EMPTY_CACHE))

    def cache_set(self, sid: int, data: dict) -> None:
        with self._cache_lock:
            self._cache[sid] = data

    def cache_drop(self, sid: int) -> None:
        with self._cache_lock:
            self._cache.pop(sid, None)

    def push_stale_after(self) -> float:
        return max(60.0, self.cfg.get("poll_interval", 30) * 2)

    # ── poller ───────────────────────────────────────────────────────────────--
    def poll_loop(self, stop: threading.Event) -> None:
        if stop.wait(3):
            return
        while not stop.is_set():
            try:
                self.do_poll()
            except Exception as e:
                print(f"[poll] {e}")
            stop.wait(self.cfg.get("poll_interval", 30))

    def do_poll(self) -> None:
        stale_after = self.push_stale_after()
        reregister_every = max(300.0, self.cfg.get("poll_interval", 30) * 10)
        now = time.time()
        for srv in self.db.servers():
            sid = srv["id"]
            c = self.cache_get(sid)
            last_push = c.get("last_push_at", 0)
            if last_push > 0 and (now - last_push) < stale_after:
                continue   # push fresh — skip polling
            try:
                res = self.vps_list(srv["ip"], srv["api_key"])
                self.cache_set(sid, {
                    "online": True,
                    "stats": res.get("server", {}),
                    "users": res.get("users", []),
                    "last_seen": now,
                    "last_push_at": last_push,
                    "masterdnsvpn": res.get("masterdnsvpn", c.get("masterdnsvpn")),
                    "jitsi_domains": res.get("jitsi_domains", c.get("jitsi_domains", "")),
                })
                if now - self._push_register_times.get(sid, 0) > reregister_every:
                    self._push_register_times[sid] = now
                    self.register_push_bg(srv)
            except Exception as e:
                self.cache_set(sid, {
                    "online": False, "stats": {}, "users": [],
                    "last_seen": c.get("last_seen", 0), "last_push_at": last_push,
                })
                print(f"[offline] {srv['name']} ({srv['ip']}): {e}")

    # ── Telegram ─────────────────────────────────────────────────────────────--
    def send_tg_alert(self, text: str) -> None:
        token = self.cfg.get("tg_bot_token", "").strip()
        recipients = self.cfg.get("tg_recipients", "").strip()
        if not token or not recipients:
            return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        for line in recipients.splitlines():
            chat_id = line.strip()
            if not chat_id:
                continue
            try:
                data = json.dumps({"chat_id": chat_id, "text": text}).encode()
                req = urllib.request.Request(
                    url, data=data, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=10) as r:
                    r.read()
            except Exception as e:
                print(f"[tg] failed to send to {chat_id}: {e}")

    def send_tg_alert_bg(self, text: str) -> None:
        threading.Thread(target=self.send_tg_alert, args=(text,), daemon=True).start()

    def get_tg_updates(self, token: str) -> dict:
        url = f"https://api.telegram.org/bot{token}/getUpdates?limit=100"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        if not data.get("ok"):
            return {"ok": False, "error": data.get("description", "Telegram error")}
        seen: dict[int, str] = {}
        for upd in data.get("result", []):
            msg = upd.get("message") or upd.get("edited_message") or upd.get("channel_post") or {}
            frm = msg.get("from") or msg.get("sender_chat") or {}
            cid = frm.get("id")
            if not cid:
                continue
            name = " ".join(filter(None, [frm.get("first_name", ""), frm.get("last_name", "")]))
            uname = frm.get("username", "")
            if uname:
                name = f"{name} (@{uname})" if name else f"@{uname}"
            seen[cid] = name or str(cid)
        return {"ok": True, "users": [{"id": cid, "name": n} for cid, n in seen.items()]}

    # ── aggregation ──────────────────────────────────────────────────────────--
    def build_data(self) -> dict:
        groups = self.db.groups()
        grp_map = {g["id"]: g for g in groups}
        stale_after = self.push_stale_after()
        now = time.time()
        result = {"servers": [], "groups": [{"id": g["id"], "name": g["name"]} for g in groups]}
        for srv in self.db.servers():
            sid = srv["id"]
            gid = srv.get("group_id")
            c = self.cache_get(sid)
            active = sum(1 for vu in c["users"] if vu.get("running"))
            clients_online = sum(int(vu.get("peers_count", 0) or 0) for vu in c["users"])
            tile = {
                "id": sid, "name": srv["name"], "ip": srv["ip"],
                "country": srv["country"], "flag": flag(srv["country"]),
                "group_id": gid, "group_name": grp_map.get(gid, {}).get("name", ""),
                "online": c["online"],
                "cpu": round(c["stats"].get("cpu_percent", 0), 1),
                "ram": round(c["stats"].get("mem_percent", 0), 1),
                "active_users": active, "total_users": len(c["users"]),
                "clients_online": clients_online,
                "push_active": (c.get("last_push_at", 0) > 0
                                and now - c.get("last_push_at", 0) < stale_after),
                "masterdnsvpn": c.get("masterdnsvpn") if c["online"] else None,
                "jitsi_domains": c.get("jitsi_domains", ""),
                # forward the full instance objects (node already sends everything the
                # editor needs) + a client_id alias the frontend uses
                "users": [{**vu, "client_id": vu.get("id", ""),
                           "peers_count": int(vu.get("peers_count", 0) or 0)}
                          for vu in c["users"]],
            }
            result["servers"].append(tile)
        result["poll_interval"] = self.cfg.get("poll_interval", 30)
        result["tg_bot_token"] = self.cfg.get("tg_bot_token", "")
        result["tg_recipients"] = self.cfg.get("tg_recipients", "")
        return result

    def api_v1_list(self) -> dict:
        users_out, mdns_out = [], []
        for srv in self.db.servers():
            c = self.cache_get(srv["id"])
            for vu in c.get("users", []):
                active = vu.get("running", False) and vu.get("uri_live", False)
                users_out.append({
                    "client_id": vu.get("id", ""), "uri": vu.get("uri", ""),
                    "status": "active" if active else "inactive",
                    "peers_count": int(vu.get("peers_count", 0) or 0),
                    "peers_devices": vu.get("peers_devices", []),
                    "server_name": srv["name"], "server_country": srv["country"],
                    "group_id": srv.get("group_id"),
                })
            mdns = c.get("masterdnsvpn") if c.get("online") else None
            if mdns:
                mdns_out.append({"domain": mdns.get("domain", ""), "key": mdns.get("key", "")})
        return {"users": users_out, "masterdnsvpn": mdns_out}

    def update_all_servers(self, url: str) -> list[dict]:
        servers = self.db.servers()

        def _one(srv):
            try:
                res = self.vps_call(srv["ip"], srv["api_key"],
                                    {"action": "update_panel", "url": url}, timeout=120)
                return {"name": srv["name"], "ok": True, "message": res.get("message", "")}
            except Exception as e:
                return {"name": srv["name"], "ok": False, "error": str(e)}

        if not servers:
            return []
        with ThreadPoolExecutor(max_workers=min(16, len(servers))) as ex:
            return list(ex.map(_one, servers))

    def broadcast_jitsi_domains(self, domains: list) -> tuple[int, int]:
        servers = self.db.servers()

        def _one(srv):
            try:
                self.vps_call(srv["ip"], srv["api_key"],
                              {"action": "set_jitsi_domains", "domains": domains})
                return True
            except Exception as e:
                print(f"[jitsi-domains] {srv['name']}: {e}")
                return False

        if not servers:
            return 0, 0
        with ThreadPoolExecutor(max_workers=min(16, len(servers))) as ex:
            results = list(ex.map(_one, servers))
        return sum(results), len(results) - sum(results)
