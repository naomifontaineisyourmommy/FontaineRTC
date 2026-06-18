"""WDTT user (password) CRUD — isolated against a temp config dir."""

import pytest

from fontaine.node.wdtt import manager, store


@pytest.fixture
def wdtt_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "WDTT_DIR", tmp_path)
    monkeypatch.setattr(store, "PASSWORDS_JSON", tmp_path / "passwords.json")
    monkeypatch.setattr(store, "SERVER_LOG", tmp_path / "server.log")
    monkeypatch.setattr(store, "META_JSON", tmp_path / "fontaine-meta.json")
    return tmp_path


def test_user_crud(wdtt_dir):
    m = manager.WdttManager()
    assert m.list_users() == []

    res = m.add_user(days=30, password="TestPass12345678", host="1.2.3.4")
    assert res["password"] == "TestPass12345678"
    assert res["expires_at"] > 0

    users = m.list_users()
    assert len(users) == 1 and users[0]["status"] == "active"

    assert m.set_deactivated("TestPass12345678", True)
    assert m.list_users()[0]["status"] == "deactivated"

    assert m.del_user("TestPass12345678") is True
    assert m.del_user("missing") is False
    assert m.list_users() == []


def test_perpetual_and_uri(wdtt_dir):
    m = manager.WdttManager()
    res = m.add_user(days=0, host="1.2.3.4", vk_hash="abcdefghijklmnop")
    assert res["expires_at"] == 0
    assert res["uri"] == "wdtt://1.2.3.4:56000:56001:9000:" + res["password"] + ":abcdefghijklmnop"
    # the stored VK-hash lets list_users rebuild the same wdtt:// link
    u = m.list_users()[0]
    assert u["vk_hash"] == "abcdefghijklmnop" and u["uri"] == res["uri"]
    # a user without a VK-hash has no link, only the password
    m.add_user(days=0, password="NoHashPass123456", host="1.2.3.4")
    nohash = next(x for x in m.list_users() if x["password"] == "NoHashPass123456")
    assert nohash["uri"] == ""


def test_password_validation(wdtt_dir):
    with pytest.raises(ValueError):
        manager.WdttManager().add_user(password="bad:pass", host="1.2.3.4")


def test_generated_password(wdtt_dir):
    res = manager.WdttManager().add_user(host="1.2.3.4")
    assert len(res["password"]) == 16 and ":" not in res["password"]
