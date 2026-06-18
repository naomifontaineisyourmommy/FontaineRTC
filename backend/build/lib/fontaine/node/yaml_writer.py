"""Generate the per-instance YAML config consumed by the olcrtc binary.

Ported 1:1 from OlcRTC-VPS `_write_user_yaml`. The binary is invoked as
``./olcrtc-linux-amd64 <uid>.yaml`` so the field names/structure here are fixed
by the binary and must not drift.
"""

from pathlib import Path
from typing import Mapping


def render_yaml(user: Mapping[str, object], cfg: Mapping[str, object]) -> str:
    """Return the YAML document text for one instance."""
    carrier = user.get("carrier", "jitsi")
    transport = user.get("transport", "datachannel")
    room_id = user.get("current_room_id") or "any"
    wb_token = str(user.get("wb_token") or "").strip()
    # WB Stream owner-mode: token present => srv creates & owns the room, room.id omitted.
    is_wb_owner = carrier == "wbstream" and bool(wb_token)

    lines = [
        "mode: srv",
        "auth:",
        f"  provider: {carrier}",
    ]
    if is_wb_owner:
        lines.append(f'  token: "{wb_token}"')
    if not is_wb_owner:
        lines += ["room:", f'  id: "{room_id}"']
    lines += [
        "crypto:",
        f'  key: "{user["key"]}"',
        "net:",
        f"  transport: {transport}",
        f'  dns: "{cfg.get("dns", "1.1.1.1:53")}"',
        "data: data",
    ]
    if cfg.get("debug"):
        lines.append("debug: true")
    if cfg.get("socks_proxy"):
        lines += [
            "socks:",
            f'  proxy_addr: "{cfg["socks_proxy"]}"',
            f'  proxy_port: {int(cfg.get("socks_proxy_port") or 1080)}',
        ]
    if transport == "vp8channel":
        lines += [
            "vp8:",
            f'  fps: {user.get("vp8_fps", "60")}',
            f'  batch_size: {user.get("vp8_batch", "64")}',
        ]
    elif transport == "seichannel":
        lines += [
            "sei:",
            f'  fps: {user.get("fps", "60")}',
            f'  batch_size: {user.get("batch", "64")}',
            f'  fragment_size: {user.get("frag", "900")}',
            f'  ack_timeout_ms: {user.get("ack_ms", "2000")}',
        ]
    elif transport == "videochannel":
        lines += [
            "video:",
            f'  codec: {user.get("video_codec", "qrcode")}',
            f'  width: {user.get("video_w", "1080")}',
            f'  height: {user.get("video_h", "1080")}',
            f'  fps: {user.get("video_fps", "60")}',
            f'  bitrate: "{user.get("video_bitrate", "5000k")}"',
            f'  hw: {user.get("video_hw", "none")}',
            f'  qr_recovery: {user.get("video_qr_recovery", "low")}',
            f'  qr_size: {user.get("video_qr_size", "0")}',
            f'  tile_module: {user.get("video_tile_module", "4")}',
            f'  tile_rs: {user.get("video_tile_rs", "20")}',
        ]
    # liveness — always enabled
    lines += ["liveness:", "  interval: 10s", "  timeout: 5s", "  failures: 3"]
    # lifecycle — optional
    max_dur = str(user.get("max_session_duration", "")).strip()
    if max_dur:
        lines += ["lifecycle:", f"  max_session_duration: {max_dur}"]
    return "\n".join(lines) + "\n"


def write_yaml(user: Mapping[str, object], cfg: Mapping[str, object], data_dir: Path) -> Path:
    """Write <uid>.yaml into data_dir and return its path."""
    path = data_dir / f"{user['id']}.yaml"
    path.write_text(render_yaml(user, cfg), encoding="utf-8")
    return path
