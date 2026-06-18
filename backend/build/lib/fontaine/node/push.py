"""Outgoing push to the admin panel (ported from OlcRTC-VPS push subsystem).

Sends an encrypted state dump on change + a heartbeat every 30s, plus one-off
error pushes when a process dies or a WB token degrades. Uses stdlib urllib so
it runs cleanly inside the manager's worker threads.
"""

import json
import threading
import time
import urllib.error
import urllib.request

from ..core import crypto

HEARTBEAT = 30


def _post(url: str, api_key: str, payload: dict, timeout: int) -> None:
    body = crypto.encrypt(api_key, json.dumps(payload).encode()).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "text/plain"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout):
        pass


def do_push(mgr) -> bool:
    """Send one state push. Disables push (and returns False) on HTTP 404."""
    ak = mgr.cfg.get("api_key", "")
    url = mgr.cfg.get("push_url", "")
    if not url or not ak:
        return True
    try:
        _post(url, ak, mgr.build_push_payload(), timeout=5)
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            mgr.panel_log("[PUSH] 404 — server unknown to admin, disabling push")
            mgr.cfg.set("push_url", "")
        else:
            mgr.panel_log(f"[PUSH] HTTP {e.code}")
        return False
    except Exception as e:
        mgr.panel_log(f"[PUSH] send failed: {e}")
        return False


def send_error_push(mgr, uid, carrier, transport, error, log_tail=None) -> None:
    """Fire-and-forget error push (runs in a daemon thread)."""
    ak = mgr.cfg.get("api_key", "")
    url = mgr.cfg.get("push_url", "")
    if not url or not ak:
        return
    error_full = error + ("\n" + "\n".join(log_tail) if log_tail else "")
    payload = {
        "ts": int(time.time()),
        "type": "error",
        "user_id": uid,
        "carrier": carrier,
        "transport": transport,
        "error": error_full,
    }
    try:
        _post(url, ak, payload, timeout=10)
        mgr.panel_log(f"[PUSH] error push sent uid={uid[:8]} ({len(log_tail or [])} lines)")
    except Exception as e:
        mgr.panel_log(f"[PUSH] error push failed: {e}")


def push_worker(mgr, stop: threading.Event) -> None:
    """Push on state change or at least every HEARTBEAT seconds."""
    while not stop.is_set():
        mgr.push_event.wait(timeout=HEARTBEAT)
        mgr.push_event.clear()
        if stop.is_set():
            break
        if mgr.cfg.get("push_url"):
            do_push(mgr)


def register(mgr) -> None:
    """Wire the manager's error-push hook to this module."""
    mgr.on_error_push = lambda uid, carrier, transport, error, tail=None: \
        send_error_push(mgr, uid, carrier, transport, error, tail)
