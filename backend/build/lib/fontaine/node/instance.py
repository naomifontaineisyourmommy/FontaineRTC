"""Instance data model + projections (ported from OlcRTC-VPS).

An "instance" is one olcrtc process config (formerly a user in users.json).
It is a plain dict so the threaded manager can mutate transient fields cheaply;
persistence stores it as a JSON blob keyed by uid.

Projections:
  public(u)  -> dashboard/push view (includes built URI, transient runtime state)
  options()  -> dynamic carrier/transport/domain variants for UI dropdowns
  full(u)    -> external management API view (editable + options + read-only status)
"""

import secrets
import time

from ..core import compat
from ..core.uri import build_uri

# Transport parameter defaults — single source of truth for the template + projections.
TRANSPORT_PARAM_DEFAULTS: dict[str, str] = {
    "vp8_fps": "60", "vp8_batch": "64",
    "fps": "60", "batch": "64", "frag": "900", "ack_ms": "2000",
    "video_codec": "qrcode",
    "video_w": "1080", "video_h": "1080",
    "video_fps": "60", "video_bitrate": "5000k",
    "video_hw": "none",
    "video_qr_recovery": "low", "video_qr_size": "0",
    "video_tile_module": "4", "video_tile_rs": "20",
}

_IGNORE_ROOM = {"direct", "data", "srv", "cnc", "any", "none", ""}


def new_instance(uid: str, carrier: str = "jitsi", transport: str = "datachannel") -> dict:
    """Build a fresh instance dict (ported from _user_template)."""
    return {
        "id": uid,
        "key": secrets.token_hex(32),
        "preferred_carrier": carrier,
        "preferred_transport": transport,
        "carrier": carrier,
        "transport": transport,
        "running": False,
        "custom_room_id": "",      # user-configured; empty => domain-generated
        "current_room_id": "",     # actual room_id passed to YAML; set on each start
        "live_room_id": None,      # detected from logs at runtime (transient)
        "wb_token": "",            # WB Stream bearer-token; set => owner-mode (node-local)
        "peers_count": 0,          # transient, from srv logs
        "peers_devices": [],       # transient, from srv logs
        "traffic_rx": 0,
        "traffic_tx": 0,
        "created_at": time.time(),
        "start_time": None,
        "auto_restart": True,
        **dict(TRANSPORT_PARAM_DEFAULTS),
        "max_session_duration": "",
        "jitsi_chosen_domain": "",
    }


def public(u: dict) -> dict:
    """Dashboard / push projection with built URI (ported from _user_public)."""
    uid = u["id"]
    carrier = u.get("carrier", "wbstream")
    transport = u.get("transport", "datachannel")
    key = u.get("key", "")
    live_room_id = u.get("live_room_id") or ""
    current_room_id = u.get("current_room_id") or ""
    custom_room_id = u.get("custom_room_id") or ""
    display_room = live_room_id or current_room_id or "any"
    uri = build_uri(carrier, transport, display_room, key, u)
    out = {
        "id": uid,
        "key": key,
        "carrier": carrier,
        "transport": transport,
        "preferred_carrier": u.get("preferred_carrier", carrier),
        "preferred_transport": u.get("preferred_transport", transport),
        "running": u.get("running", False),
        "custom_room_id": custom_room_id,
        "current_room_id": current_room_id,
        "live_room_id": live_room_id,
        "wb_token": u.get("wb_token", ""),   # stripped from external `list`
        "peers_count": u.get("peers_count", 0),
        "peers_devices": u.get("peers_devices", []),
        "uri": uri,
        "uri_live": bool(live_room_id),
        "uptime": int(time.time() - u["start_time"]) if u.get("start_time") else 0,
        "traffic_rx": u.get("traffic_rx", 0),
        "traffic_tx": u.get("traffic_tx", 0),
        "created_at": u.get("created_at", 0),
        "auto_restart": u.get("auto_restart", True),
        "max_session_duration": u.get("max_session_duration", ""),
        "jitsi_chosen_domain": u.get("jitsi_chosen_domain", ""),
    }
    for field, default in TRANSPORT_PARAM_DEFAULTS.items():
        out[field] = u.get(field, default)
    return out


def options(jitsi_domains: str = "") -> dict:
    """Dynamic UI variants (ported from _user_options)."""
    domains = [d.strip() for d in jitsi_domains.split("\n") if d.strip()]
    cmap = compat.compat_map()
    carriers = [c for c in compat.CARRIERS if cmap.get(c)]
    return {
        "carriers": carriers,
        "compat": {c: cmap[c] for c in carriers},
        "jitsi_domains": domains,
    }


def full(u: dict, jitsi_domains: str = "") -> dict:
    """External management API view (ported from _user_full)."""
    pub = public(u)
    out = {
        "id": pub["id"],
        "carrier": pub["carrier"],
        "transport": pub["transport"],
        "room_id": pub["custom_room_id"],
        "jitsi_domain": pub["jitsi_chosen_domain"],
        "auto_restart": pub["auto_restart"],
        "options": options(jitsi_domains),
        "status": {
            "running": pub["running"],
            "uri": pub["uri"],
            "uri_live": pub["uri_live"],
            "uptime": pub["uptime"],
            "traffic_rx": pub["traffic_rx"],
            "traffic_tx": pub["traffic_tx"],
            "peers_count": pub["peers_count"],
            "created_at": pub["created_at"],
        },
    }
    for field in TRANSPORT_PARAM_DEFAULTS:
        out[field] = pub[field]
    return out
