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


def test_render_admin_alt_names_icon_comment():
    data = {"servers": [
        {"name": "ES-02", "country": "Spain", "users": [
            {"uri": "u1", "uri_live": True, "carrier": "jitsi",
             "jitsi_chosen_domain": "https://meet.example.com/"},
            {"uri": "uDead", "uri_live": False, "carrier": "jitsi"},        # skipped
            {"uri": "u2", "uri_live": True, "carrier": "jitsi",
             "jitsi_chosen_domain": "https://meet.example.com"},
            {"uri": "u3", "uri_live": True, "carrier": "wbstream"},         # no comment
        ]},
    ]}
    mgr = FakeAdmin(FakeCfg({"sub_enabled": True, "sub_name": "Pool", "sub_refresh": "10m"}), data)
    lines = subserver._render_admin(mgr).splitlines()
    # first live → server name; subsequent → "(ALT n)"
    assert "##name: ES-02" in lines
    assert "##name: ES-02 (ALT 1)" in lines      # second live (u2)
    assert "##name: ES-02 (ALT 2)" in lines      # third live (u3, wbstream)
    assert "##name: ES-02 (ALT 3)" not in lines  # dead one didn't count
    # country icon on every entry
    assert lines.count("##icon: 🇪🇸") == 3
    # jitsi → bare domain comment; wbstream → none
    assert lines.count("##comment: meet.example.com") == 2
    assert sum(1 for ln in lines if ln.startswith("##comment:")) == 2
    assert sum(1 for ln in lines if ln in ("u1", "u2", "u3")) == 3 and "uDead" not in lines


def _fake_node(users, cfg):
    class Lock:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    class M:
        pass
    m = M()
    m.cfg = cfg
    m.lock = Lock()
    m.users = {i: u for i, u in enumerate(users)}
    return m


def test_render_node_alt_names_and_jitsi_comment(monkeypatch):
    import fontaine.node.instance as inst
    monkeypatch.setattr(inst, "public", lambda u: u)
    users = [
        {"uri": "u1", "uri_live": True, "carrier": "jitsi",
         "jitsi_chosen_domain": "https://m.example.com/"},
        {"uri": "uDead", "uri_live": False, "carrier": "jitsi"},
        {"uri": "u3", "uri_live": True, "carrier": "wbstream"},
    ]
    mgr = _fake_node(users, FakeCfg({"sub_enabled": True, "sub_name": "N", "sub_refresh": "10m"}))
    lines = subserver._render_node(mgr).splitlines()
    assert "##name: ALT 1" in lines and "##name: ALT 2" in lines
    assert "##name: ALT 3" not in lines              # only two live
    assert "##comment: m.example.com" in lines       # jitsi: scheme + trailing slash stripped
    assert sum(1 for ln in lines if ln.startswith("##comment:")) == 1   # wbstream has none
    assert "##icon:" not in "\n".join(lines)         # node has no country icon
