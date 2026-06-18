"""Carrier x transport compatibility matrix (ported 1:1 from OlcRTC-VPS)."""

CARRIERS = ["jitsi", "wbstream", "telemost"]
TRANSPORTS = ["datachannel", "vp8channel", "seichannel", "videochannel"]

# Valid (carrier, transport) combinations.
COMPAT_SET = {
    ("wbstream", "vp8channel"), ("wbstream", "seichannel"), ("wbstream", "videochannel"),
    ("jitsi", "datachannel"), ("jitsi", "vp8channel"),
    ("jitsi", "seichannel"), ("jitsi", "videochannel"),
    ("telemost", "vp8channel"), ("telemost", "videochannel"),
}


def is_compatible(carrier: str, transport: str) -> bool:
    return (carrier, transport) in COMPAT_SET


def compat_map() -> dict[str, list[str]]:
    """carrier -> [allowed transports], for UI dropdowns / get_user options."""
    out: dict[str, list[str]] = {c: [] for c in CARRIERS}
    for carrier, transport in COMPAT_SET:
        out.setdefault(carrier, []).append(transport)
    # keep a stable transport ordering
    for c in out:
        out[c] = [t for t in TRANSPORTS if t in out[c]]
    return out
