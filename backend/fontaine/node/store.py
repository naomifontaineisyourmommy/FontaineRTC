"""Node-local mutable runtime config + instance persistence.

The node mutates config at runtime (push_url on 404, jitsi_domains, dns, ffmpeg,
full_logs, ...) so — like the original — it lives in a JSON file under data_dir,
seeded from environment defaults on first run. Instances persist in SQLite
(kv table: uid -> JSON blob), replacing users.json.
"""

import json
import sqlite3
import threading
from pathlib import Path

from ..config import Settings
from ..core import crypto, security

_CONFIG_DEFAULTS = {
    "panel_password": "",
    "api_key": "",
    "dns": "1.1.1.1:53",
    "debug": True,
    "socks_proxy": "",
    "socks_proxy_port": "",
    "ffmpeg": "ffmpeg",
    "push_url": "",
    "jitsi_domains": "",
    "full_logs": False,
}


class NodeConfig:
    """Mutable, persisted node config (data_dir/config.json)."""

    def __init__(self, settings: Settings):
        self._path = settings.data_dir / "config.json"
        self._lock = threading.RLock()
        self._data = dict(_CONFIG_DEFAULTS)
        # seed from env settings where the env value is meaningful
        self._data.update({
            "dns": settings.dns,
            "debug": settings.debug,
            "socks_proxy": settings.socks_proxy,
            "socks_proxy_port": settings.socks_proxy_port,
            "ffmpeg": settings.ffmpeg,
            "push_url": settings.push_url,
            "full_logs": settings.full_logs,
            "panel_password": settings.panel_password,
            "api_key": settings.api_key,
        })
        self._load()
        self._ensure_secrets()

    def _load(self) -> None:
        try:
            self._data.update(json.loads(self._path.read_text(encoding="utf-8")))
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

    def update(self, **kw) -> None:
        with self._lock:
            self._data.update(kw)
            self.save()

    def as_dict(self) -> dict:
        with self._lock:
            return dict(self._data)

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        tmp.replace(self._path)


class InstanceStore:
    """SQLite kv persistence for instances (replaces users.json)."""

    def __init__(self, settings: Settings):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self._path = settings.data_dir / "instances.db"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS instances (uid TEXT PRIMARY KEY, data TEXT NOT NULL)"
        )
        self._conn.commit()

    def load_all(self) -> dict[str, dict]:
        with self._lock:
            rows = self._conn.execute("SELECT uid, data FROM instances").fetchall()
        return {uid: json.loads(data) for uid, data in rows}

    def save_all(self, instances: dict[str, dict]) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM instances")
            cur.executemany(
                "INSERT INTO instances (uid, data) VALUES (?, ?)",
                [(uid, json.dumps(u)) for uid, u in instances.items()],
            )
            self._conn.commit()

    def delete(self, uid: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM instances WHERE uid = ?", (uid,))
            self._conn.commit()
