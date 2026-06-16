"""Admin role end-to-end tests via TestClient."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from fontaine.config import get_settings
from fontaine.core import crypto

SRV_KEY = "a" * 64


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FONTAINE_ROLE", "admin")
    monkeypatch.setenv("FONTAINE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    from fontaine.app import create_app
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def _add_server(c) -> int:
    g = c.post("/api/groups/add", json={"name": "EU"}).json()
    c.post("/api/servers/add", json={
        "ip": "10.0.0.9:8080", "api_key": SRV_KEY,
        "country": "Germany", "name": "DE-01", "group_id": g["id"],
    })
    return c.get("/api/data").json()["servers"][0]["id"]


def test_health_role(client):
    assert client.get("/healthz").json()["role"] == "admin"


def test_group_and_server_crud(client):
    sid = _add_server(client)
    data = client.get("/api/data").json()
    assert data["servers"][0]["name"] == "DE-01"
    assert "img" in data["servers"][0]["flag"]
    assert data["servers"][0]["online"] is False
    # duplicate server rejected
    g = data["groups"][0]["id"]
    dup = client.post("/api/servers/add", json={
        "ip": "10.0.0.9:8080", "api_key": SRV_KEY,
        "country": "Germany", "name": "x", "group_id": g}).json()
    assert "already exists" in dup["error"]
    # group with servers cannot be deleted
    assert client.post("/api/groups/delete", json={"group_id": g}).json()["error"]


def test_state_push_updates_cache(client):
    sid = _add_server(client)
    push = {
        "ts": int(time.time()),
        "server": {"cpu_percent": 12.3, "mem_percent": 45.6},
        "users": [{"id": "u1", "uri": "olcrtc://jitsi?datachannel@r#k",
                   "running": True, "uri_live": True, "carrier": "jitsi",
                   "transport": "datachannel", "peers_count": 3}],
        "masterdnsvpn": {"domain": "vpn.x", "key": "mdk"},
    }
    body = crypto.encrypt(SRV_KEY, json.dumps(push).encode())
    r = client.post(f"/push/v1/{sid}", content=body, headers={"Content-Type": "text/plain"})
    assert r.status_code == 200
    t = client.get("/api/data").json()["servers"][0]
    assert t["online"] and t["active_users"] == 1 and t["clients_online"] == 3
    assert t["push_active"] is True


def test_push_bad_key_and_unknown_server(client):
    sid = _add_server(client)
    bad = crypto.encrypt("b" * 64, json.dumps({"ts": int(time.time())}).encode())
    assert client.post(f"/push/v1/{sid}", content=bad,
                       headers={"Content-Type": "text/plain"}).status_code == 400
    good = crypto.encrypt(SRV_KEY, json.dumps({"ts": int(time.time())}).encode())
    assert client.post("/push/v1/999", content=good,
                       headers={"Content-Type": "text/plain"}).status_code == 404


def test_external_api_v1_list(client):
    sid = _add_server(client)
    push = {"ts": int(time.time()), "server": {}, "users": [
        {"id": "u1", "uri": "x", "running": True, "uri_live": True, "peers_count": 2}]}
    client.post(f"/push/v1/{sid}",
                content=crypto.encrypt(SRV_KEY, json.dumps(push).encode()),
                headers={"Content-Type": "text/plain"})
    ak = client.app.state.manager.cfg.get("api_key")
    eb = crypto.encrypt(ak, json.dumps({"action": "list", "ts": int(time.time())}).encode())
    er = client.post("/api/v1", content=eb, headers={"Content-Type": "text/plain"})
    ext = json.loads(crypto.decrypt(ak, er.text))
    assert len(ext["users"]) == 1 and ext["users"][0]["status"] == "active"
