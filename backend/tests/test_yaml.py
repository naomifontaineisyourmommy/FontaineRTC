"""YAML writer parity tests against OlcRTC-VPS output."""

from fontaine.node import instance as inst
from fontaine.node.yaml_writer import render_yaml

CFG = {"dns": "1.1.1.1:53", "debug": True, "ffmpeg": "ffmpeg"}


def _user(**over):
    u = inst.new_instance("abc123def456", over.pop("carrier", "jitsi"),
                          over.pop("transport", "datachannel"))
    u["key"] = "KEY"
    u.update(over)
    return u


def test_jitsi_datachannel():
    out = render_yaml(_user(current_room_id="room1"), CFG)
    assert out == (
        "mode: srv\n"
        "auth:\n"
        "  provider: jitsi\n"
        "room:\n"
        '  id: "room1"\n'
        "crypto:\n"
        '  key: "KEY"\n'
        "net:\n"
        "  transport: datachannel\n"
        '  dns: "1.1.1.1:53"\n'
        "data: data\n"
        "debug: true\n"
        "liveness:\n"
        "  interval: 10s\n"
        "  timeout: 5s\n"
        "  failures: 3\n"
    )


def test_wb_owner_mode_omits_room():
    out = render_yaml(_user(carrier="wbstream", transport="vp8channel",
                            wb_token="TOK"), CFG)
    assert '  token: "TOK"' in out
    assert "room:" not in out
    assert "vp8:" in out and "  fps: 60" in out


def test_videochannel_adds_ffmpeg():
    out = render_yaml(_user(carrier="jitsi", transport="videochannel"), CFG)
    assert "video:" in out
    assert '  codec: qrcode' in out
    assert 'ffmpeg: "ffmpeg"' in out


def test_max_session_duration():
    out = render_yaml(_user(max_session_duration="6h"), CFG)
    assert "lifecycle:\n  max_session_duration: 6h" in out


def test_public_projection_uri():
    u = inst.new_instance("u1", "jitsi", "vp8channel")
    u["key"] = "K"
    u["live_room_id"] = "live99"
    pub = inst.public(u)
    assert pub["uri"] == "olcrtc://jitsi?vp8channel<vp8-fps=60&vp8-batch=64>@live99#K"
    assert pub["uri_live"] is True
