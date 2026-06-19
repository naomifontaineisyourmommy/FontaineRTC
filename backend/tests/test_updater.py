"""ensure_binary: olcrtc binary is fetched only when missing or outdated."""

import time

import pytest

from fontaine import updater


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
