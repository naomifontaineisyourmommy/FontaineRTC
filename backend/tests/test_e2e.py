"""End-to-end node <-> admin over the real encrypted protocol.

Both apps run in-process via TestClient; the admin's vps_call is routed into the
node's TestClient so the actual /api/v1 (Hash-CTR + HMAC) handler is exercised on
both sides — registration, polling, action proxying and the external list.
"""

import json
import time

from fastapi.testclient import TestClient

from fontaine.config import get_settings
from fontaine.core import crypto


def test_admin_node_e2e(tmp_path, monkeypatch):
    # ── node app ──
    monkeypatch.setenv("FONTAINE_ROLE", "node")
    monkeypatch.setenv("FONTAINE_DATA_DIR", str(tmp_path / "node"))
    get_settings.cache_clear()
    from fontaine.app import create_app

    node_app = create_app()
    with TestClient(node_app) as node_client:
        node_key = node_app.state.manager.cfg.get("api_key")

        # ── admin app ──
        monkeypatch.setenv("FONTAINE_ROLE", "admin")
        monkeypatch.setenv("FONTAINE_DATA_DIR", str(tmp_path / "admin"))
        get_settings.cache_clear()
        admin_app = create_app()
        with TestClient(admin_app) as admin_client:
            mgr = admin_app.state.manager

            # route admin's encrypted client into the node's TestClient
            def via(ip, key, payload, timeout=10):
                body = crypto.encrypt(key, json.dumps({**payload, "ts": int(time.time())}).encode())
                r = node_client.post("/api/v1", content=body, headers={"Content-Type": "text/plain"})
                return json.loads(crypto.decrypt(key, r.text))

            mgr.vps_call = via

            g = admin_client.post("/api/groups/add", json={"name": "EU"}).json()
            assert admin_client.post("/api/servers/add", json={
                "ip": "node:8080", "api_key": node_key,
                "country": "Germany", "name": "DE-01", "group_id": g["id"],
            }).json()["ok"]

            # poll the node -> it should come online
            mgr.do_poll()
            tile = admin_client.get("/api/data").json()["servers"][0]
            assert tile["online"] is True and tile["total_users"] == 0
            sid = tile["id"]

            # create an instance on the node, proxied through the admin
            cr = admin_client.post("/api/node/create-user",
                                   json={"server_id": sid, "carrier": "jitsi",
                                         "transport": "vp8channel"}).json()
            assert cr["id"]

            mgr.do_poll()
            tile2 = admin_client.get("/api/data").json()["servers"][0]
            assert tile2["total_users"] == 1
            u = tile2["users"][0]
            assert u["carrier"] == "jitsi" and u["transport"] == "vp8channel"
            assert "wb_token" in u and "peers_devices" in u   # full config inline

            # external encrypted API list
            ak = mgr.cfg.get("api_key")
            body = crypto.encrypt(ak, json.dumps({"action": "list", "ts": int(time.time())}).encode())
            er = admin_client.post("/api/v1", content=body, headers={"Content-Type": "text/plain"})
            ext = json.loads(crypto.decrypt(ak, er.text))
            assert len(ext["users"]) == 1
            assert ext["users"][0]["server_name"] == "DE-01"
            assert "peers_devices" in ext["users"][0]

            # delete it back through the proxy
            assert admin_client.post("/api/node/delete-user",
                                     json={"server_id": sid, "id": cr["id"]}).json()["ok"]

    get_settings.cache_clear()
