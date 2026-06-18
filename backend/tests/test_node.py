"""Node role encrypted API tests via TestClient."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from fontaine.config import get_settings
from fontaine.core import crypto


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FONTAINE_ROLE", "node")
    monkeypatch.setenv("FONTAINE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    from fontaine.app import create_app
    with TestClient(create_app()) as c:
        yield c, c.app.state.manager.cfg.get("api_key")
    get_settings.cache_clear()


def _call(c, ak, d):
    d["ts"] = int(time.time())
    body = crypto.encrypt(ak, json.dumps(d).encode())
    r = c.post("/api/v1", content=body, headers={"Content-Type": "text/plain"})
    return json.loads(crypto.decrypt(ak, r.text))


def test_crud_flow(env):
    c, ak = env
    assert _call(c, ak, {"action": "list"})["users"] == []
    created = _call(c, ak, {"action": "create_user", "carrier": "jitsi", "transport": "vp8channel"})
    uid = created["id"]
    assert _call(c, ak, {"action": "get_user", "id": uid})["transport"] == "vp8channel"
    assert _call(c, ak, {"action": "set_user", "id": uid, "vp8_fps": "30"})["ok"]
    assert _call(c, ak, {"action": "get_user", "id": uid})["vp8_fps"] == "30"
    lst = _call(c, ak, {"action": "list"})
    assert len(lst["users"]) == 1
    assert lst["users"][0]["uri"].startswith("olcrtc://jitsi?vp8channel<vp8-fps=30")
    # admin needs full config inline (no get_user round trip)
    assert "wb_token" in lst["users"][0]
    assert "custom_room_id" in lst["users"][0]
    assert "jitsi_domains" in lst
    # admin's poller reads these straight from list (push isn't guaranteed)
    assert "masterdnsvpn" in lst        # {domain,key} or null when not installed
    assert "wdtt" in lst
    assert _call(c, ak, {"action": "delete_user", "id": uid})["ok"]


def test_incompatible_rejected(env):
    c, ak = env
    res = _call(c, ak, {"action": "create_user", "carrier": "wbstream", "transport": "datachannel"})
    assert res["error"] == "incompatible carrier/transport"


def test_replay_guard(env):
    c, ak = env
    body = crypto.encrypt(ak, json.dumps({"action": "list", "ts": 0}).encode())
    r = c.post("/api/v1", content=body, headers={"Content-Type": "text/plain"})
    assert json.loads(crypto.decrypt(ak, r.text))["error"] == "timestamp out of range"


def test_bad_key_rejected(env):
    c, _ = env
    body = crypto.encrypt("f" * 64, json.dumps({"action": "list", "ts": int(time.time())}).encode())
    r = c.post("/api/v1", content=body, headers={"Content-Type": "text/plain"})
    assert r.status_code == 403
