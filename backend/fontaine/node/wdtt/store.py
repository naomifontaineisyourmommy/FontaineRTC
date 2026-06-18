"""Access to the WDTT password database (/etc/wdtt/passwords.json).

The wdtt-server reads this file only at start and keeps it in memory, so writers
must stop/restart the service around edits (handled by the manager). The schema:

    {
      "main_password": "...",
      "admin_id": "", "bot_token": "",
      "passwords": { "<password>": {device_id, expires_at, down_bytes,
                                    up_bytes, is_deactivated} },
      "devices":   { "<device_id>": {device_id, ip, priv_key, pub_key} }
    }
"""

import json
import os
from pathlib import Path

WDTT_DIR = Path(os.environ.get("FONTAINE_WDTT_DIR", "/etc/wdtt"))
PASSWORDS_JSON = WDTT_DIR / "passwords.json"
SERVER_LOG = WDTT_DIR / "server.log"
# FontaineRTC-only sidecar: extra per-password metadata the wdtt-server neither
# needs nor preserves (it rewrites passwords.json on its own). Keeps the VK-hash
# (and host) so the "wdtt://" invite link can be rebuilt for the users table.
META_JSON = WDTT_DIR / "fontaine-meta.json"

def load() -> dict:
    try:
        data = json.loads(PASSWORDS_JSON.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"passwords": {}, "devices": {}}   # fresh dicts — never shared/mutated
    data.setdefault("passwords", {})
    data.setdefault("devices", {})
    return data


def save(data: dict) -> None:
    """Atomic write with 0600 perms (file holds secrets)."""
    WDTT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = PASSWORDS_JSON.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(PASSWORDS_JSON)


def load_meta() -> dict:
    """{ "<password>": {"vk_hash": "...", "host": "..."} } — fresh dict always."""
    try:
        data = json.loads(META_JSON.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_meta(data: dict) -> None:
    WDTT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = META_JSON.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(META_JSON)


def server_stats() -> dict:
    """Latest snapshot from server.log (active/total/down_gb/up_gb/uptime/…)."""
    try:
        return json.loads(SERVER_LOG.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
