"""ensure_binary: olcrtc binary is fetched only when missing or outdated."""

import time

import pytest

from fontaine import updater


@pytest.fixture(autouse=True)
def _clear_caches():
    updater._release_cache.clear()
    updater._latest_cache.update(sha="", msg="", at=0.0)
    yield


def test_skips_download_when_current(tmp_path, monkeypatch):
    dest = tmp_path / "olcrtc-linux-amd64"
    dest.write_bytes(b"existing")
    calls = []
    monkeypatch.setattr(updater, "_binary_up_to_date", lambda: True)
    monkeypatch.setattr(updater, "binary_version", lambda: "v1.0.0")
    monkeypatch.setattr(updater, "download_binary", lambda *a, **k: calls.append(a))

    msg = updater.ensure_binary(dest)
    assert "untouched" in msg and calls == []   # current binary left alone


def test_downloads_when_outdated(tmp_path, monkeypatch):
    dest = tmp_path / "olcrtc-linux-amd64"
    dest.write_bytes(b"old")
    monkeypatch.setattr(updater, "_binary_up_to_date", lambda: False)
    monkeypatch.setattr(updater, "download_binary", lambda *a, **k: "v2.0.0")

    assert updater.ensure_binary(dest) == "updated to v2.0.0"


def test_downloads_when_missing(tmp_path, monkeypatch):
    dest = tmp_path / "olcrtc-linux-amd64"   # does not exist
    # even if the sidecar claims current, a missing binary must be fetched
    monkeypatch.setattr(updater, "_binary_up_to_date", lambda: True)
    monkeypatch.setattr(updater, "download_binary", lambda *a, **k: "v2.0.0")

    assert updater.ensure_binary(dest) == "updated to v2.0.0"


def _ver(monkeypatch, *, panel_cur, panel_lat, bcur, blat):
    monkeypatch.setattr(updater, "current_commit", lambda: panel_cur)
    monkeypatch.setattr(updater, "latest_commit", lambda: panel_lat)
    monkeypatch.setattr(updater, "binary_version", lambda: bcur)
    monkeypatch.setattr(updater, "latest_binary_tag", lambda: blat)
    return updater.version_info(check_binary=True)


def test_binary_update_detected_when_outdated(monkeypatch):
    info = _ver(monkeypatch, panel_cur="abc", panel_lat="abc", bcur="v1.0.0", blat="v1.0.1")
    assert info["update_available"] is True


def test_binary_update_detected_when_local_unknown(monkeypatch):
    # missing/unreadable sidecar must not hide an available release
    info = _ver(monkeypatch, panel_cur="abc", panel_lat="abc", bcur="", blat="v1.0.1")
    assert info["binary"] == "unknown" and info["update_available"] is True


def test_no_update_when_binary_current(monkeypatch):
    info = _ver(monkeypatch, panel_cur="abc", panel_lat="abc", bcur="v1.0.1", blat="v1.0.1")
    assert info["update_available"] is False


def test_no_false_prompt_when_remote_unknown(monkeypatch):
    # GitHub unreachable (blat == "") must not trigger a prompt
    info = _ver(monkeypatch, panel_cur="abc", panel_lat="abc", bcur="v1.0.0", blat="")
    assert info["update_available"] is False


# ── per-package update plan: each of FontaineRTC/olcrtc/WDTT updates alone ──────
@pytest.fixture
def plan_spy(tmp_path, monkeypatch):
    """Record which package steps run, and whether a service restart happens."""
    calls: list[str] = []
    monkeypatch.setattr(updater, "_status",
                        {"updating": False, "step": "", "index": 0, "total": 4, "error": ""})
    monkeypatch.setattr(updater, "update_panel_code",
                        lambda d: (calls.append("panel"), (True, "ok"))[1])
    monkeypatch.setattr(updater, "ensure_binary",
                        lambda d, *a, **k: (calls.append("binary"), "v")[1])
    monkeypatch.setattr(updater, "schedule_restart",
                        lambda *a, **k: calls.append("restart"))
    return calls


def _run_plan(tmp_path, **kw) -> dict:
    ok, _ = updater.start_update(tmp_path, **kw)
    assert ok
    for _ in range(300):                      # wait for the worker to finish
        st = updater.update_status()
        if st["index"] == st["total"]:
            break
        time.sleep(0.01)
    return updater.update_status()


def _wdtt_extra(calls):
    def extra():
        calls.append("wdtt")
        return True, "ok"
    return extra


def test_plan_panel_only(tmp_path, plan_spy):
    _run_plan(tmp_path, do_panel=True, do_binary=False)
    assert plan_spy == ["panel", "restart"]   # restart only because panel changed


def test_plan_binary_only(tmp_path, plan_spy):
    st = _run_plan(tmp_path, do_panel=False, do_binary=True)
    assert plan_spy == ["binary"]             # no restart for a binary-only update
    assert st["updating"] is False


def test_plan_wdtt_only(tmp_path, plan_spy):
    st = _run_plan(tmp_path, do_panel=False, do_binary=False, extra=_wdtt_extra(plan_spy))
    assert plan_spy == ["wdtt"] and st["updating"] is False


def test_plan_binary_and_wdtt_no_restart(tmp_path, plan_spy):
    _run_plan(tmp_path, do_panel=False, do_binary=True, extra=_wdtt_extra(plan_spy))
    assert plan_spy == ["binary", "wdtt"]     # neither needs a panel restart


def test_plan_all_three_restarts(tmp_path, plan_spy):
    _run_plan(tmp_path, do_panel=True, do_binary=True, extra=_wdtt_extra(plan_spy))
    assert plan_spy == ["panel", "binary", "wdtt", "restart"]


def test_plan_nothing_to_update(tmp_path, plan_spy):
    ok, msg = updater.start_update(tmp_path, do_panel=False, do_binary=False, extra=None)
    assert ok is False and msg == "nothing to update" and plan_spy == []


def test_plan_panel_failure_aborts(tmp_path, plan_spy, monkeypatch):
    monkeypatch.setattr(updater, "update_panel_code", lambda d: (False, "git boom"))
    updater.start_update(tmp_path, do_panel=True, do_binary=True, extra=_wdtt_extra(plan_spy))
    for _ in range(300):
        if not updater.update_status()["updating"]:
            break
        time.sleep(0.01)
    st = updater.update_status()
    # panel is fatal: binary/WDTT must not run, error surfaced, no restart
    assert st["error"] == "git boom" and "restart" not in plan_spy and "binary" not in plan_spy


# ── release_asset_url: combine /releases/latest + list, pick newest ─────────────
def _fake_api(latest, listing):
    def api(url):
        if url.endswith("/releases/latest"):
            if latest is None:
                raise RuntimeError("404")
            return latest
        if url.endswith("/releases"):
            return listing
        raise AssertionError(url)
    return api


def _rel(tag, when, asset="olcrtc-linux-amd64", draft=False):
    a = [{"name": asset, "browser_download_url": f"https://x/{tag}/{asset}"}] if asset else []
    return {"tag_name": tag, "published_at": when, "draft": draft, "assets": a}


def test_release_pick_latest_when_list_lags(monkeypatch):
    # /releases/latest already has v1.0.2 but the list still lags (only v1.0.1)
    latest = _rel("v1.0.2-beta", "2026-06-20T05:29:48Z")
    listing = [_rel("v1.0.1-beta", "2026-06-19T06:00:55Z"),
               _rel("v1.0.0-beta", "2026-06-16T08:47:04Z")]
    monkeypatch.setattr(updater, "_api", _fake_api(latest, listing))
    url, tag = updater.release_asset_url("r", "olcrtc-linux-amd64")
    assert tag == "v1.0.2-beta" and url.endswith("/v1.0.2-beta/olcrtc-linux-amd64")


def test_release_prerelease_newer_than_latest(monkeypatch):
    # a pre-release (only in the list, excluded from /releases/latest) is newest
    latest = _rel("v1.0.2-beta", "2026-06-20T05:29:48Z")
    listing = [_rel("v1.0.3-pre", "2026-06-21T10:00:00Z"),
               _rel("v1.0.1-beta", "2026-06-19T06:00:55Z")]
    monkeypatch.setattr(updater, "_api", _fake_api(latest, listing))
    _, tag = updater.release_asset_url("r", "olcrtc-linux-amd64")
    assert tag == "v1.0.3-pre"


def test_release_skips_draft_and_missing_asset(monkeypatch):
    latest = _rel("v2.0.0", "2026-07-01T00:00:00Z", asset=None)   # no matching asset
    listing = [_rel("v2.0.1", "2026-07-02T00:00:00Z", draft=True),  # draft ignored
               _rel("v1.9.0", "2026-06-01T00:00:00Z")]              # has the asset
    monkeypatch.setattr(updater, "_api", _fake_api(latest, listing))
    _, tag = updater.release_asset_url("r", "olcrtc-linux-amd64")
    assert tag == "v1.9.0"


def test_release_fallback_when_asset_absent_everywhere(monkeypatch):
    monkeypatch.setattr(updater, "_api", _fake_api(None, []))
    url, tag = updater.release_asset_url("owner/repo", "olcrtc-linux-amd64")
    assert tag == "latest" and url == \
        "https://github.com/owner/repo/releases/latest/download/olcrtc-linux-amd64"


# ── changelog notes in the update prompt ────────────────────────────────────────
def test_clean_notes_strips_coauthor_and_trims():
    txt = "Title\n\nBody line\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>\n"
    assert updater.clean_notes(txt) == "Title\n\nBody line"
    assert updater.clean_notes("") == ""
    # case-insensitive, handles CRLF
    assert updater.clean_notes("a\r\nco-authored-by: x <y>\r\n") == "a"


def test_version_info_includes_notes(monkeypatch):
    monkeypatch.setattr(updater, "current_commit", lambda: "aaaaaaa")
    monkeypatch.setattr(updater, "latest_commit", lambda: "bbbbbbb")
    monkeypatch.setattr(updater, "latest_commit_message", lambda: "panel changelog")
    monkeypatch.setattr(updater, "binary_version", lambda: "v1")
    monkeypatch.setattr(updater, "latest_binary_tag", lambda: "v2")
    monkeypatch.setattr(updater, "latest_binary_notes", lambda: "olcrtc changelog")
    info = updater.version_info(check_binary=True)
    assert info["update_available"] is True
    assert info["notes"] == "panel changelog" and info["binary_notes"] == "olcrtc changelog"


def test_version_info_no_notes_when_current(monkeypatch):
    monkeypatch.setattr(updater, "current_commit", lambda: "x")
    monkeypatch.setattr(updater, "latest_commit", lambda: "x")
    monkeypatch.setattr(updater, "binary_version", lambda: "v1")
    monkeypatch.setattr(updater, "latest_binary_tag", lambda: "v1")
    info = updater.version_info(check_binary=True)
    assert info["update_available"] is False
    assert info["notes"] == "" and info["binary_notes"] == ""
