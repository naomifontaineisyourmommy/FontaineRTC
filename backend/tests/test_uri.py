"""URI builder parity tests against OlcRTC-VPS examples."""

from fontaine.core import compat
from fontaine.core.uri import build_uri, uri_payload


def test_datachannel_has_no_payload():
    assert uri_payload("datachannel", {}) == ""
    assert build_uri("jitsi", "datachannel", "abc123", "key", {}) == \
        "olcrtc://jitsi?datachannel@abc123#key"


def test_vp8_defaults():
    assert build_uri("jitsi", "vp8channel", "abc123", "key", {}) == \
        "olcrtc://jitsi?vp8channel<vp8-fps=60&vp8-batch=64>@abc123#key"


def test_sei_defaults():
    assert build_uri("wbstream", "seichannel", "abc123", "key", {}) == \
        "olcrtc://wbstream?seichannel<fps=60&batch=64&frag=900&ack-ms=2000>@abc123#key"


def test_room_falls_back_to_any():
    assert build_uri("jitsi", "datachannel", "", "key", {}) == \
        "olcrtc://jitsi?datachannel@any#key"


def test_compat_matrix():
    assert compat.is_compatible("jitsi", "datachannel")
    assert not compat.is_compatible("wbstream", "datachannel")
    assert not compat.is_compatible("telemost", "seichannel")
    assert compat.compat_map()["telemost"] == ["vp8channel", "videochannel"]
