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


def server_stats() -> dict:
    """Latest snapshot from server.log (active/total/down_gb/up_gb/uptime/…)."""
    try:
        return json.loads(SERVER_LOG.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
