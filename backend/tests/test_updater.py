"""ensure_binary: olcrtc binary is fetched only when missing or outdated."""

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
