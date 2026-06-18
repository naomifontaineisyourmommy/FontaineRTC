"""WdttManager — status + user (password) CRUD for the WDTT service.

Reimplements add/del/list-user.sh in Python: edits passwords.json with the
service stopped, then restarts it (the server reads the DB only at start).
"""

import os
import secrets
import subprocess
import time
import urllib.request
from pathlib import Path

from . import store

SERVICE = "wdtt"
BINARY = Path(os.environ.get("FONTAINE_WDTT_BINARY", "/usr/local/bin/wdtt-server"))

# Defaults; must match how deploy.sh set the service up.
DTLS_PORT = int(os.environ.get("FONTAINE_WDTT_DTLS_PORT", "56000"))
WG_PORT = int(os.environ.get("FONTAINE_WDTT_WG_PORT", "56001"))
TUN_PORT = int(os.environ.get("FONTAINE_WDTT_TUN_PORT", "9000"))

_PW_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"


def _systemctl(*args: str) -> tuple[bool, str]:
    try:
        p = subprocess.run(["systemctl", *args, SERVICE], capture_output=True, text=True)
        return p.returncode == 0, (p.stdout + p.stderr).strip()
    except Exception as e:
        return False, str(e)


def gen_password(n: int = 16) -> str:
    return "".join(secrets.choice(_PW_ALPHABET) for _ in range(n))


def detect_ip() -> str:
    for url in ("https://api.ipify.org", "https://ifconfig.me", "https://icanhazip.com"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FontaineRTC"})
            with urllib.request.urlopen(req, timeout=5) as r:
                ip = r.read().decode().strip()
            if ip:
                return ip
        except Exception:
            continue
    return ""


class WdttManager:
    # ── service state ───────────────────────────────────────────────────────---
    def installed(self) -> bool:
        return BINARY.exists()

    def active(self) -> bool:
        ok, out = _systemctl("is-active")
        return out.strip() == "active"

    def status(self) -> dict:
        data = store.load()
        return {
            "installed": self.installed(),
            "active": self.active(),
            "users": len(data.get("passwords", {})),
            "main_password": data.get("main_password", ""),
            "stats": store.server_stats(),
            "ports": {"dtls": DTLS_PORT, "wg": WG_PORT, "tun": TUN_PORT},
        }

    # ── DB edit helper (stop → edit → start) ────────────────────────────────---
    def _edit(self, mutator) -> None:
        _systemctl("stop")
        data = store.load()
        mutator(data)
        store.save(data)
        ok, _ = _systemctl("start")
        if not ok:
            _systemctl("restart")

    # ── users ───────────────────────────────────────────────────────────────--
    def list_users(self) -> list[dict]:
        data = store.load()
        devices = data.get("devices", {})
        now = int(time.time())
        out = []
        for pw, e in data.get("passwords", {}).items():
            exp = e.get("expires_at", 0) or 0
            dev = e.get("device_id", "") or ""
            if e.get("is_deactivated"):
                st = "deactivated"
            elif exp and exp < now:
                st = "expired"
            elif dev:
                st = "bound"          # active and bound to a device
            else:
                st = "active"
            out.append({
                "password": pw,
                "status": st,
                "expires_at": exp,
                "down_bytes": e.get("down_bytes", 0),
                "up_bytes": e.get("up_bytes", 0),
                "device_id": dev,
                "device_ip": devices.get(dev, {}).get("ip", "") if dev else "",
            })
        return out

    def add_user(self, days: int = 30, password: str = "", host: str = "",
                 vk_hash: str = "") -> dict:
        pw = password.strip() or gen_password()
        if any(c in pw for c in (":", ",", " ")):
            raise ValueError("Пароль не должен содержать ':', ',' или пробелы")
        exp = 0 if int(days) <= 0 else int(time.time()) + int(days) * 86400

        def mutator(data: dict) -> None:
            cur = data["passwords"].get(pw, {})
            data["passwords"][pw] = {**cur, "expires_at": exp, "is_deactivated": False}

        self._edit(mutator)
        host = host.strip() or detect_ip() or "YOUR_SERVER_IP"
        result = {"password": pw, "expires_at": exp, "days": int(days), "host": host,
                  "ports": {"dtls": DTLS_PORT, "wg": WG_PORT, "tun": TUN_PORT}}
        if vk_hash.strip():
            result["uri"] = f"wdtt://{host}:{DTLS_PORT}:{WG_PORT}:{TUN_PORT}:{pw}:{vk_hash.strip()}"
        return result

    def del_user(self, password: str) -> bool:
        data = store.load()
        if password not in data.get("passwords", {}):
            return False
        devid = data["passwords"][password].get("device_id", "")

        def mutator(d: dict) -> None:
            d["passwords"].pop(password, None)
            if devid:
                d.get("devices", {}).pop(devid, None)

        self._edit(mutator)
        return True

    def set_deactivated(self, password: str, value: bool) -> bool:
        data = store.load()
        if password not in data.get("passwords", {}):
            return False

        def mutator(d: dict) -> None:
            d["passwords"][password]["is_deactivated"] = bool(value)

        self._edit(mutator)
        return True
