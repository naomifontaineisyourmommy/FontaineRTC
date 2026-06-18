"""olcrtc:// URI building (ported 1:1 from OlcRTC-VPS).

Format:
    olcrtc://<carrier>?<transport><payload>@<roomID>#<key>

<payload> is a <key=value&...> block present for vp8channel / seichannel /
videochannel; absent for datachannel. Keys match CLI flags without the leading
hyphen (internal hyphens preserved).
"""

from typing import Mapping

# Per-transport URI parameter spec: list of (uri_key, instance_field, default).
_PARAM_SPEC: dict[str, list[tuple[str, str, str]]] = {
    "vp8channel": [
        ("vp8-fps", "vp8_fps", "60"),
        ("vp8-batch", "vp8_batch", "64"),
    ],
    "seichannel": [
        ("fps", "fps", "60"),
        ("batch", "batch", "64"),
        ("frag", "frag", "900"),
        ("ack-ms", "ack_ms", "2000"),
    ],
    "videochannel": [
        ("video-w", "video_w", "1080"),
        ("video-h", "video_h", "1080"),
        ("video-fps", "video_fps", "60"),
        ("video-bitrate", "video_bitrate", "5000k"),
        ("video-hw", "video_hw", "none"),
        ("video-codec", "video_codec", "qrcode"),
        ("video-qr-size", "video_qr_size", "0"),
        ("video-qr-recovery", "video_qr_recovery", "low"),
        ("video-tile-module", "video_tile_module", "4"),
        ("video-tile-rs", "video_tile_rs", "20"),
    ],
}


def uri_payload(transport: str, params: Mapping[str, object]) -> str:
    """Build the <key=value&...> payload block. datachannel -> empty string."""
    spec = _PARAM_SPEC.get(transport)
    if not spec:
        return ""
    parts = [f"{uri_key}={params.get(field, default)}" for uri_key, field, default in spec]
    return "<" + "&".join(parts) + ">"


def build_uri(carrier: str, transport: str, room_id: str, key: str,
              params: Mapping[str, object]) -> str:
    """Assemble the full olcrtc:// client URI. room_id falls back to 'any'."""
    payload = uri_payload(transport, params)
    return f"olcrtc://{carrier}?{transport}{payload}@{room_id or 'any'}#{key}"
