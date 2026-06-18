"""Background workers for the node role (ported from OlcRTC-VPS).

- traffic_monitor: every 5s, accumulate per-instance RX/TX from /proc/<pid>/io.
- watchdog: every 10s, restart dead processes when auto_restart is on, with the
  anti-crash-loop guard (5 consecutive failures each living <30s disables it).

Both run as daemon threads operating on a shared NodeManager.
"""

import threading
import time

from . import sysinfo


def traffic_monitor(mgr, stop: threading.Event) -> None:
    while not stop.is_set():
        time.sleep(5)
        with mgr.lock:
            for uid, proc in list(mgr.procs.items()):
                if proc.poll() is not None:
                    continue
                rc, wc = sysinfo.read_proc_io(proc.pid)
                prev = mgr.prev_io.get(uid)
                if prev:
                    pr, pw = prev
                    u = mgr.users[uid]
                    u["traffic_rx"] = u.get("traffic_rx", 0) + max(0, rc - pr)
                    u["traffic_tx"] = u.get("traffic_tx", 0) + max(0, wc - pw)
                mgr.prev_io[uid] = (rc, wc)


def watchdog(mgr, stop: threading.Event) -> None:
    while not stop.is_set():
        time.sleep(10)
        with mgr.lock:
            for uid, user in list(mgr.users.items()):
                if not user.get("running"):
                    continue
                proc = mgr.procs.get(uid)
                if proc and proc.poll() is None:
                    continue
                rc = proc.returncode if proc else "?"
                mgr.panel_log(f"[WD] uid={uid[:8]} died (rc={rc})")
                mgr.prev_io.pop(uid, None)
                user["running"] = False
                user["live_room_id"] = None
                user["start_time"] = None
                user["peers_count"] = 0
                user["peers_devices"] = []
                mgr.save()
                mgr.notify_push()
                tail = mgr.log_tail_since(uid, 60)
                mgr._fire_error_push(uid, user.get("carrier", ""),
                                     user.get("transport", ""),
                                     f"process exited with code {rc}", tail)
                if user.get("auto_restart", True):
                    lived = time.time() - mgr.proc_start.get(uid, 0)
                    if lived >= 30:
                        mgr.wd_fails.pop(uid, None)
                    fails = mgr.wd_fails.get(uid, 0) + 1
                    mgr.wd_fails[uid] = fails
                    if fails >= 5:
                        mgr.wd_fails.pop(uid, None)
                        user["auto_restart"] = False
                        mgr.save()
                        mgr.panel_log(f"[WD] uid={uid[:8]} auto_restart disabled after 5 failures")
                    else:
                        mgr.panel_log(f"[WD] uid={uid[:8]} restarting "
                                      f"(attempt {fails}/5, lived {lived:.0f}s)")
                        ok, msg = mgr._start_proc(uid)
                        if not ok:
                            mgr.panel_log(f"[WD] uid={uid[:8]} spawn failed: {msg} — retry next tick")
                            user["running"] = True
