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
