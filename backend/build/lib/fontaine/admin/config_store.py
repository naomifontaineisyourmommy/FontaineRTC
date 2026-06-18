"""Admin scalar config (data_dir/config.json) — ported from OlcRTC-AdminVPS.

Servers and groups live in SQLite (db.py); this holds only scalar settings.
Password is hashed via core.security; api_key generated on first run.
"""

import json
import threading

from ..config import Settings
from ..core import crypto, security

_DEFAULTS = {
    "panel_password": "",
    "api_key": "",
    "poll_interval": 30,
    "panel_url": "",        # public URL announced to nodes for push registration
    "tg_bot_token": "",
    "tg_recipients": "",    # newline-separated chat ids
}


class AdminConfig:
    def __init__(self, settings: Settings):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self._path = settings.data_dir / "config.json"
        self._lock = threading.RLock()
        self._data = dict(_DEFAULTS)
        self._data.update({
            "poll_interval": settings.poll_interval,
            "panel_url": settings.panel_url,
            "tg_bot_token": settings.tg_bot_token,
            "tg_recipients": settings.tg_recipients,
            "panel_password": settings.panel_password,
            "api_key": settings.api_key,
        })
        self._load()
        self._ensure_secrets()

    def _load(self) -> None:
        try:
            loaded = json.loads(self._path.read_text(encoding="utf-8"))
            loaded.pop("servers", None)   # legacy keys now in SQLite
            loaded.pop("groups", None)
            self._data.update(loaded)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _ensure_secrets(self) -> None:
        changed = False
        if not crypto.valid_api_key(self._data.get("api_key", "")):
            self._data["api_key"] = crypto.new_api_key()
            changed = True
        pw = self._data.get("panel_password", "")
        if pw and not security.is_hashed(pw):
            self._data["panel_password"] = security.hash_password(pw)
            changed = True
        if changed:
            self.save()

    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)

    def set(self, key, value) -> None:
        with self._lock:
            self._data[key] = value
            self.save()

    def save(self) -> None:
        with self._lock:
            tmp = self._path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            tmp.replace(self._path)
