"""Subscription settings validation + sub.md rendering (no real port binding)."""

from fontaine import subserver


class FakeCfg:
    def __init__(self, d=None):
        self.d = dict(d or {})

    def get(self, k, default=None):
        return self.d.get(k, default)

    def set(self, k, v):
        self.d[k] = v


class FakeAdmin:
    def __init__(self, cfg, data):
        self.cfg = cfg
        self._data = data

    def build_data(self):
        return self._data


def test_sub_settings_defaults():
    s = subserver.sub_settings(FakeAdmin(FakeCfg(), {}))
    assert s == {"enabled": False, "name": "FontaineRTC", "refresh": "10m", "port": 8081}


def test_save_settings_rejects_bad_and_clashing_port():
    mgr = FakeAdmin(FakeCfg(), {})
    assert subserver.save_settings(mgr, {"port": 0}, 8080)
    assert subserver.save_settings(mgr, {"port": 99999}, 8080)
    assert "панелью" in subserver.save_settings(mgr, {"port": 8080}, 8080)
    assert subserver.save_settings(mgr, {"port": "abc"}, 8080)
    # nothing persisted on failure paths beyond what set() wrote — enabled stays unset
    assert mgr.cfg.get("sub_port") is None


def test_save_settings_persists_on_success():
    mgr = FakeAdmin(FakeCfg(), {})
    err = subserver.save_settings(
        mgr, {"enabled": True, "name": "  My Sub ", "refresh": "5m", "port": 8090}, 8080)
    assert err == ""
    assert mgr.cfg.d == {"sub_enabled": True, "sub_name": "My Sub",
                         "sub_refresh": "5m", "sub_port": 8090}


def test_save_settings_blank_fields_fall_back_to_defaults():
    mgr = FakeAdmin(FakeCfg(), {})
    subserver.save_settings(mgr, {"enabled": False, "name": "", "refresh": "", "port": 8081}, 8080)
    assert mgr.cfg.get("sub_name") == "FontaineRTC" and mgr.cfg.get("sub_refresh") == "10m"


def test_render_admin_disabled_returns_none():
    mgr = FakeAdmin(FakeCfg({"sub_enabled": False}), {})
    assert subserver._render_admin(mgr) is None


def test_render_admin_only_live_uris():
    data = {"servers": [
        {"name": "DE-01", "country": "Germany", "users": [
            {"uri": "olcrtc://jitsi?datachannel@any#abc", "uri_live": True},
            {"uri": "olcrtc://jitsi?datachannel@any#dead", "uri_live": False},  # not live → skip
            {"uri": "", "uri_live": True},                                     # no uri → skip
        ]},
        {"name": "ES-01", "country": "Spain", "users": [
            {"uri": "olcrtc://wbstream?seichannel@room#def", "uri_live": True},
        ]},
    ]}
    mgr = FakeAdmin(FakeCfg({"sub_enabled": True, "sub_name": "Pool", "sub_refresh": "10m"}), data)
    text = subserver._render_admin(mgr)
    lines = text.splitlines()
    assert lines[0] == "#name: Pool"
    assert lines[2] == "#refresh: 10m"
    assert "olcrtc://jitsi?datachannel@any#abc" in lines
    assert "##name: DE-01" in lines and "##comment: Germany" in lines
    assert "olcrtc://wbstream?seichannel@room#def" in lines and "##name: ES-01" in lines
    # only the two live instances make it in — dead/empty URIs are excluded
    assert "olcrtc://jitsi?datachannel@any#dead" not in lines
    assert sum(1 for ln in lines if ln.startswith("olcrtc://")) == 2
