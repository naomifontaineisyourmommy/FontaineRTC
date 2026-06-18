"""NodeManager — process lifecycle, log parsing and persistence.

Synchronous, guarded by a single RLock, mirroring OlcRTC-VPS. Background workers
(watchdog, traffic monitor, push) live in their own modules and operate on the
shared manager instance; they are wired up in app lifespan (migration phase 2b).
"""

import collections
import re
import secrets
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from ..config import Settings
from . import instance as inst
from . import sysinfo
from .store import InstanceStore, NodeConfig
from .yaml_writer import write_yaml

# ── log parsing regexes (ported 1:1) ───────────────────────────────────────────
_ROOM_RE = re.compile(
    r"(?:To connect client use:\s+-id|room\s+created:|"
    r"Created and connected to WB Stream room id:)\s+([a-zA-Z0-9_\-]{6,})", re.I)
_JITSI_LIVE_RE = re.compile(r"\[xmpp.*\].*<-.*ready='true'", re.I)
_LINKED_RE = re.compile(r"Link connected", re.I)
_PEERS_RE = re.compile(r"Current peers count:\s*(\d+)(?:,\s*Devices:\s*\[([^\]]*)\])?", re.I)
_WB_TOKEN_ERR_RE = re.compile(r"livekit reconnect failed", re.I)
_IGNORE_ROOM = inst._IGNORE_ROOM

class NodeManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.data_dir = settings.data_dir
        self.binary = settings.binary_path
        self.cfg = NodeConfig(settings)
        self.store = InstanceStore(settings)

        self.lock = threading.RLock()
        self.users: dict[str, dict] = {}
        self.procs: dict[str, subprocess.Popen] = {}
        self.log_bufs: dict[str, collections.deque] = {}
        self.subs: dict[str, list[collections.deque]] = {}
        self.prev_io: dict[str, tuple[int, int]] = {}
        self.wd_fails: dict[str, int] = {}
        self.proc_start: dict[str, float] = {}
        self.wb_alerted: set[str] = set()
        self.panel_log_buf: collections.deque = collections.deque(maxlen=500)

        # push hooks (registered by push.py)
        self.push_event = threading.Event()
        self.on_error_push: Optional[Callable[..., None]] = None

        self.users = self.store.load_all()
        # all processes are gone after a restart; recovery happens in recover()
        for u in self.users.values():
            u["peers_count"] = 0
            u["peers_devices"] = []

    # ── helpers ────────────────────────────────────────────────────────────────
    def panel_log(self, msg: str) -> None:
        self.panel_log_buf.append(f'[{time.strftime("%H:%M:%S")}] {msg}')

    def save(self) -> None:
        with self.lock:
            self.store.save_all(self.users)

    def notify_push(self) -> None:
        self.push_event.set()

    def _yaml_path(self, uid: str) -> Path:
        return self.data_dir / f"{uid}.yaml"

    def _log_path(self, uid: str) -> Path:
        return self.data_dir / f"{uid}.log"

    # ── on-disk full log (only when full_logs enabled) ──────────────────────────
    def _log_file_write(self, uid: str, line: str, *, reset: bool = False) -> None:
        if not self.cfg.get("full_logs"):
            if reset:
                self._log_path(uid).unlink(missing_ok=True)
            return
        try:
            mode = "w" if reset else "a"
            with open(self._log_path(uid), mode, encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            self.panel_log(f"[LOG] file write failed uid={uid[:8]}: {e}")

    def read_log_for_download(self, uid: str, full: bool, snapshot: list) -> bytes:
        if full:
            try:
                return self._log_path(uid).read_bytes()
            except FileNotFoundError:
                pass
        if not snapshot:
            return b""
        return ("\n".join(snapshot) + "\n").encode("utf-8")

    def log_tail_since(self, uid: str, seconds: int = 60) -> list:
        """Lines from the last `seconds`. Call with lock held."""
        lines = list(self.log_bufs.get(uid, []))
        if not lines:
            return []
        now = time.time()
        cutoff = now - seconds
        ls = time.localtime(now)
        midnight = now - (ls.tm_hour * 3600 + ls.tm_min * 60 + ls.tm_sec)
        result = []
        for line in lines:
            try:
                ts = midnight + int(line[1:3]) * 3600 + int(line[4:6]) * 60 + int(line[7:9])
                if ts > now + 1:
                    ts -= 86400
                if ts >= cutoff:
                    result.append(line)
            except Exception:
                pass
        return result

    # ── log reader thread ───────────────────────────────────────────────────────
    def _log_reader(self, uid: str, proc: subprocess.Popen) -> None:
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            entry = f'[{time.strftime("%H:%M:%S")}] {line}'
            with self.lock:
                if uid not in self.log_bufs or self.procs.get(uid) is not proc:
                    break
                self._log_file_write(uid, entry)
                self.log_bufs[uid].append(entry)
                for q in self.subs.get(uid, []):
                    q.append(entry)
                if uid not in self.users:
                    continue
                u = self.users[uid]
                carrier = u.get("carrier", "")
                # Case 1: wbstream announces auto-created room id
                if carrier == "wbstream":
                    m = _ROOM_RE.search(line)
                    if m and m.group(1).lower() not in _IGNORE_ROOM:
                        u["live_room_id"] = m.group(1)
                        self.save()
                        self.notify_push()
                # Case 2: pre-configured room confirmed live
                trigger = (_JITSI_LIVE_RE.search(line) if carrier == "jitsi"
                           else _LINKED_RE.search(line))
                if trigger:
                    cfg_room = u.get("current_room_id", "")
                    if cfg_room and cfg_room.lower() not in _IGNORE_ROOM:
                        u["live_room_id"] = cfg_room
                        self.save()
                        self.notify_push()
                # Case 3: connected-clients counter + devices
                mp = _PEERS_RE.search(line)
                if mp:
                    new_count = int(mp.group(1))
                    dev_str = mp.group(2)
                    new_devs = [d.strip() for d in dev_str.split(",") if d.strip()] if dev_str else []
                    if new_count != u.get("peers_count") or new_devs != u.get("peers_devices"):
                        u["peers_count"] = new_count
                        u["peers_devices"] = new_devs
                        self.notify_push()
                # Case 4: WB token degradation — alert once per run
                if (carrier == "wbstream" and _WB_TOKEN_ERR_RE.search(line)
                        and uid not in self.wb_alerted):
                    self.wb_alerted.add(uid)
                    tail = self.log_tail_since(uid, 60)
                    self._fire_error_push(
                        uid, carrier, u.get("transport", ""),
                        "WB Stream: токен недействителен или reconnect не удался — нужен новый токен",
                        tail)

    def _fire_error_push(self, uid, carrier, transport, error, tail) -> None:
        if self.on_error_push:
            threading.Thread(
                target=self.on_error_push,
                args=(uid, carrier, transport, error, tail),
                daemon=True,
            ).start()

    # ── process lifecycle (call _start/_stop with lock held) ────────────────────
    def _start_proc(self, uid: str) -> tuple[bool, str]:
        user = self.users.get(uid)
        if not user:
            return False, "user not found"
        carrier = user.get("carrier", "jitsi")
        custom_room = (user.get("custom_room_id") or "").strip()
        domain = (user.get("jitsi_chosen_domain") or "").strip()
        wb_token = (user.get("wb_token") or "").strip()

        if carrier == "wbstream":
            current_room = "" if wb_token else "any"
        elif custom_room:
            current_room = custom_room
        elif carrier == "jitsi" and domain:
            current_room = domain.rstrip("/") + "/" + secrets.token_hex(6)
            self.panel_log(f"[START] uid={uid[:8]} jitsi generated room={current_room}")
        else:
            return False, f"Room ID обязателен для {carrier} — укажите URL или выберите домен"

        user["current_room_id"] = current_room
        user["peers_count"] = 0
        user["peers_devices"] = []
        self.wb_alerted.discard(uid)
        self.proc_start[uid] = time.time()
        self._stop_proc_locked(uid)

        self.log_bufs[uid] = collections.deque(maxlen=1000)
        for q in self.subs.get(uid, []):
            q.append("__CLEAR__")

        yaml_path = write_yaml(user, self.cfg.as_dict(), self.data_dir)
        cmd = [str(self.binary), str(yaml_path)]
        cmd_str = " ".join(cmd)
        self.panel_log(f"[START] uid={uid[:8]} {cmd_str}")
        cmd_entry = f'[{time.strftime("%H:%M:%S")}] [CMD] {cmd_str}'
        self.log_bufs[uid].append(cmd_entry)
        self._log_file_write(uid, cmd_entry, reset=True)
        for q in self.subs.get(uid, []):
            q.append(cmd_entry)
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, cwd=str(self.data_dir),
            )
        except Exception as e:
            return False, str(e)
        self.procs[uid] = proc
        user["running"] = True
        user["start_time"] = time.time()
        user["live_room_id"] = None
        threading.Thread(target=self._log_reader, args=(uid, proc), daemon=True).start()
        self.save()
        self.notify_push()
        return True, "started"

    def _stop_proc_locked(self, uid: str) -> None:
        proc = self.procs.pop(uid, None)
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                threading.Timer(5, lambda: proc.kill() if proc.poll() is None else None).start()
            except Exception:
                pass
        if uid in self.users:
            u = self.users[uid]
            u["running"] = False
            u["start_time"] = None
            u["live_room_id"] = None
            u["peers_count"] = 0
            u["peers_devices"] = []
        self.notify_push()

    # ── public ops (acquire lock) ───────────────────────────────────────────────
    def start_user(self, uid: str) -> tuple[bool, str]:
        with self.lock:
            self.wd_fails.pop(uid, None)
            return self._start_proc(uid)

    def stop_user(self, uid: str) -> None:
        with self.lock:
            self._stop_proc_locked(uid)
            self.save()

    def create_user(self, carrier: str = "jitsi", transport: str = "datachannel") -> dict:
        uid = secrets.token_hex(8)
        with self.lock:
            self.users[uid] = inst.new_instance(uid, carrier, transport)
            self.save()
            created = dict(self.users[uid])
        self.notify_push()
        return created

    def delete_user(self, uid: str) -> bool:
        with self.lock:
            if uid not in self.users:
                return False
            self._stop_proc_locked(uid)
            del self.users[uid]
            self.log_bufs.pop(uid, None)
            self.subs.pop(uid, None)
            self.prev_io.pop(uid, None)
            self.wd_fails.pop(uid, None)
            self.proc_start.pop(uid, None)
            self.wb_alerted.discard(uid)
            self.store.delete(uid)
            self.save()
        self._yaml_path(uid).unlink(missing_ok=True)
        self._log_path(uid).unlink(missing_ok=True)
        self.notify_push()
        return True

    def start_all(self) -> dict:
        with self.lock:
            uids = [uid for uid, u in self.users.items() if not u.get("running")]
        started, errors = 0, {}
        for uid in uids:
            ok, msg = self.start_user(uid)
            if ok:
                started += 1
            else:
                errors[uid] = msg
        return {"started": started, "failed": len(errors), "errors": errors}

    def stop_all(self) -> dict:
        with self.lock:
            uids = [uid for uid, u in self.users.items() if u.get("running")]
        for uid in uids:
            self.stop_user(uid)
        return {"stopped": len(uids)}

    def restart_all(self) -> dict:
        with self.lock:
            uids = [uid for uid, u in self.users.items() if u.get("running")]
        restarted, errors = 0, {}
        for uid in uids:
            ok, msg = self.start_user(uid)
            if ok:
                restarted += 1
            else:
                errors[uid] = msg
        return {"restarted": restarted, "failed": len(errors), "errors": errors}

    def recover(self) -> None:
        """After (re)start: respawn instances that were running with auto_restart."""
        with self.lock:
            to_start = [uid for uid, u in self.users.items()
                        if u.get("running") and u.get("auto_restart", True)]
            for u in self.users.values():
                u["running"] = False  # reset; _start_proc will set it true
        for uid in to_start:
            ok, msg = self.start_user(uid)
            self.panel_log(f"[RECOVER] uid={uid[:8]} {'ok' if ok else msg}")

    # ── projections / push payload ──────────────────────────────────────────────
    def build_push_payload(self) -> dict:
        """Full per-instance state so the admin panel needs no extra get_user call."""
        with self.lock:
            users = [inst.public(u) for u in self.users.values()]
        payload = {
            "ts": int(time.time()),
            "server": sysinfo.server_stats(),
            "users": users,
            "jitsi_domains": self.cfg.get("jitsi_domains", ""),
            "masterdnsvpn": sysinfo.masterdnsvpn_config(),
        }
        try:
            from .wdtt.manager import WdttManager
            from .wdtt import installer as _wi
            wm = WdttManager()
            st = wm.status()
            payload["wdtt"] = {
                "installed": st["installed"], "active": st["active"],
                "main_password": st.get("main_password", ""),
                "version": _wi.installed_version(), "users": wm.list_users(),
            }
        except Exception:
            payload["wdtt"] = {"installed": False, "users": []}
        return payload
