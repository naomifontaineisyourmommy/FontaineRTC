"""Groups + servers persistence (SQLite, ported 1:1 from OlcRTC-AdminVPS data.db).

Synchronous stdlib sqlite3 with a lock — matches the original and is safe to call
from both the async request handlers and the background poller thread (queries
are tiny). WAL is enabled; checkpoint on shutdown is done in app lifespan.
"""

import sqlite3
import threading
import time

from ..config import Settings


class AdminDB:
    def __init__(self, settings: Settings):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self._path = settings.data_dir / "data.db"
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(self._path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS groups (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT    NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS servers (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ip        TEXT    NOT NULL UNIQUE,
                api_key   TEXT    NOT NULL,
                country   TEXT    NOT NULL,
                name      TEXT    NOT NULL,
                group_id  INTEGER NOT NULL REFERENCES groups(id),
                added_at  REAL    NOT NULL
            );
            """
        )
        # Seed a first group on a fresh install so a server can be added right
        # away without having to create a group first.
        if self._db.execute("SELECT COUNT(*) FROM groups").fetchone()[0] == 0:
            self._db.execute("INSERT INTO groups (name) VALUES (?)", ("SP-01",))
        self._db.commit()

    def checkpoint(self) -> None:
        with self._lock:
            try:
                self._db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self._db.close()
            except Exception:
                pass

    # ── groups ───────────────────────────────────────────────────────────────--
    def groups(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT id, name FROM groups ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def group_by_id(self, gid: int) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT id, name FROM groups WHERE id=?", (gid,)).fetchone()
        return dict(row) if row else None

    def add_group(self, name: str) -> int:
        with self._lock:
            cur = self._db.execute("INSERT INTO groups (name) VALUES (?)", (name,))
            self._db.commit()
            return cur.lastrowid

    def edit_group(self, gid: int, name: str) -> None:
        with self._lock:
            self._db.execute("UPDATE groups SET name=? WHERE id=?", (name, gid))
            self._db.commit()

    def group_server_count(self, gid: int) -> int:
        with self._lock:
            return self._db.execute(
                "SELECT COUNT(*) FROM servers WHERE group_id=?", (gid,)).fetchone()[0]

    def del_group(self, gid: int) -> None:
        with self._lock:
            self._db.execute("DELETE FROM groups WHERE id=?", (gid,))
            self._db.commit()

    # ── servers ─────────────────────────────────────────────────────────────---
    def servers(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM servers ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def server_by_id(self, sid: int) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM servers WHERE id=?", (sid,)).fetchone()
        return dict(row) if row else None

    def add_server(self, ip, api_key, country, name, group_id) -> int:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO servers (ip, api_key, country, name, group_id, added_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ip, api_key, country, name, group_id, time.time()),
            )
            self._db.commit()
            return cur.lastrowid

    def edit_server(self, sid, ip, api_key, country, name, group_id) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE servers SET ip=?, api_key=?, country=?, name=?, group_id=? WHERE id=?",
                (ip, api_key, country, name, group_id, sid),
            )
            self._db.commit()

    def del_server(self, sid: int) -> None:
        with self._lock:
            self._db.execute("DELETE FROM servers WHERE id=?", (sid,))
            self._db.commit()
