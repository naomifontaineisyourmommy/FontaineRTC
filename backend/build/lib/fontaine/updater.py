"""Self-update + olcrtc binary fetch.

- The olcrtc binary is always pulled fresh from the latest release (including
  prereleases) of the OlcRTC-AdvancedInteractive repo.
- Panel self-update pulls the FontaineRTC repo (git), reinstalls the backend and
  re-fetches the binary, then schedules a service restart (systemd restarts us).

All overridable via env so forks/local setups work without code changes.
"""

import json
import os
import shutil
import stat
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

PANEL_REPO = os.environ.get("FONTAINE_REPO", "naomifontaineisyourmommy/FontaineRTC")
PANEL_BRANCH = os.environ.get("FONTAINE_BRANCH", "master")
BINARY_REPO = os.environ.get("FONTAINE_BINARY_REPO", "naomifontaineisyourmommy/OlcRTC-AdvancedInteractive")
BINARY_ASSET = os.environ.get("FONTAINE_BINARY_ASSET", "olcrtc-linux-amd64")
RESTART_CMD = os.environ.get("FONTAINE_RESTART_CMD", "systemctl restart fontaine")

_UA = {"User-Agent": "FontaineRTC-updater"}

# cache the latest remote commit/tag briefly to avoid hammering the GitHub API
_LATEST_TTL = 300.0
_latest_cache: dict = {"sha": "", "at": 0.0}
_bin_cache: dict = {"tag": "", "at": 0.0}


def _api(url: str, timeout: int = 15) -> object:
    req = urllib.request.Request(url, headers={**_UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def binary_download_url(repo: str = BINARY_REPO) -> tuple[str, str]:
    """Return (url, tag) for the newest release's olcrtc binary (prereleases included)."""
    releases = _api(f"https://api.github.com/repos/{repo}/releases")
    if not isinstance(releases, list) or not releases:
        # Fallback: the conventional 'latest' asset path (non-prerelease only).
        return (f"https://github.com/{repo}/releases/latest/download/{BINARY_ASSET}", "latest")
    rel = releases[0]  # GitHub returns releases newest-first
    for asset in rel.get("assets", []):
        if asset.get("name") == BINARY_ASSET:
            return asset["browser_download_url"], rel.get("tag_name", "?")
    raise RuntimeError(f"asset {BINARY_ASSET} not found in latest release {rel.get('tag_name')}")


def _version_file(dest: Path) -> Path:
    return dest.with_name(dest.name + ".version")


def download_binary(dest: Path, repo: str = BINARY_REPO) -> str:
    """Download the latest olcrtc binary to `dest` (atomic, chmod +x). Returns tag
    and records it in a sidecar <binary>.version file (the installed binary version)."""
    url, tag = binary_download_url(repo)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    tmp.chmod(tmp.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    tmp.replace(dest)
    try:
        _version_file(dest).write_text(tag)
    except Exception:
        pass
    return tag


def binary_version() -> str:
    """Installed olcrtc binary version (from the sidecar file), '' if unknown."""
    try:
        return _version_file(install_dir() / BINARY_ASSET).read_text().strip()
    except Exception:
        return ""


def latest_binary_tag() -> str:
    """Newest olcrtc release tag (cached briefly)."""
    now = time.time()
    if _bin_cache["tag"] and now - _bin_cache["at"] < _LATEST_TTL:
        return _bin_cache["tag"]
    try:
        _, tag = binary_download_url()
    except Exception:
        tag = ""
    if tag and tag != "latest":
        _bin_cache.update(tag=tag, at=now)
        return tag
    return _bin_cache["tag"]


def install_dir() -> Path:
    """Repo root that contains backend/ (where the service is installed)."""
    return Path(__file__).resolve().parents[2]


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    out = (p.stdout + p.stderr).strip()
    return p.returncode == 0, out


def schedule_restart(delay: float = 2.0) -> None:
    """Restart the service shortly, letting the HTTP response flush first."""
    def _do():
        try:
            subprocess.run(RESTART_CMD.split(), check=False)
        except Exception:
            pass
    threading.Timer(delay, _do).start()


def self_update(install_dir: Path, fetch_binary: bool = True, progress=None) -> tuple[bool, str]:
    """git pull + reinstall backend + (optionally) refresh binary. Caller restarts.
    `progress(index, step)` is called as it advances (for the UI overlay)."""
    def p(i: int, s: str) -> None:
        if progress:
            progress(i, s)

    p(1, "Обновление кода…")
    ok, out = _run(["git", "pull", "--ff-only"], cwd=install_dir)
    if not ok:
        return False, f"git pull: {out}"

    pip = install_dir / ".venv" / "bin" / "pip"
    if pip.exists():
        p(2, "Зависимости…")
        ok, out = _run([str(pip), "install", "-q", str(install_dir / "backend")])
        if not ok:
            return False, f"pip: {out}"

    if fetch_binary:
        p(3, "Бинарник…")
        try:
            download_binary(install_dir / BINARY_ASSET)
        except Exception as e:
            # non-fatal: a stale binary is better than a failed update
            pass

    return True, "ok"


# ── async update with progress (drives the UI overlay) ──────────────────────────
_UPDATE_TOTAL = 4
_status: dict = {"updating": False, "step": "", "index": 0, "total": _UPDATE_TOTAL, "error": ""}
_status_lock = threading.Lock()


def update_status() -> dict:
    with _status_lock:
        return dict(_status)


def _set_status(**kw) -> None:
    with _status_lock:
        _status.update(kw)


def start_update(install_dir: Path, fetch_binary: bool = True) -> tuple[bool, str]:
    """Begin an update in the background. Returns immediately so the UI can poll
    update_status(). On success the service is restarted (systemd brings it back)."""
    with _status_lock:
        if _status["updating"]:
            return False, "update already in progress"
        _status.update(updating=True, step="Подключение…", index=0,
                       total=_UPDATE_TOTAL, error="")

    def worker():
        ok, msg = self_update(install_dir, fetch_binary,
                              progress=lambda i, s: _set_status(index=i, step=s))
        if ok:
            _set_status(index=_UPDATE_TOTAL, step="Перезапуск…")
            schedule_restart(1.5)
        else:
            _set_status(updating=False, step="", error=msg)

    threading.Thread(target=worker, daemon=True).start()
    return True, "update started"


# ── versioning (commit-based) ───────────────────────────────────────────────────
def current_commit() -> str:
    """Full SHA of the installed checkout (== the version installed/last updated)."""
    ok, out = _run(["git", "rev-parse", "HEAD"], cwd=install_dir())
    return out.strip() if ok else ""


def latest_commit() -> str:
    """Full SHA of the newest commit on the repo's branch (cached briefly)."""
    now = time.time()
    if _latest_cache["sha"] and now - _latest_cache["at"] < _LATEST_TTL:
        return _latest_cache["sha"]
    try:
        data = _api(f"https://api.github.com/repos/{PANEL_REPO}/commits/{PANEL_BRANCH}")
        sha = data.get("sha", "") if isinstance(data, dict) else ""
    except Exception:
        sha = ""
    if sha:
        _latest_cache.update(sha=sha, at=now)
    return sha or _latest_cache["sha"]


def _panel_up_to_date() -> bool:
    cur, lat = current_commit(), latest_commit()
    return bool(cur and lat and cur == lat)


def _binary_up_to_date() -> bool:
    cur, lat = binary_version(), latest_binary_tag()
    return bool(cur and lat and cur == lat)


def is_up_to_date(check_binary: bool = False) -> bool:
    """True only when everything checked is confirmed at the latest version.
    Anything unknown (offline) -> False, so an explicit update stays allowed."""
    if not _panel_up_to_date():
        return False
    if check_binary and not _binary_up_to_date():
        return False
    return True


def version_info(check_binary: bool = False) -> dict:
    cur, lat = current_commit(), latest_commit()
    panel_upd = bool(cur and lat and cur != lat)
    info = {
        "current": cur[:7] if cur else "unknown",
        "latest": lat[:7] if lat else "",
        "update_available": panel_upd,
    }
    if check_binary:
        bcur, blat = binary_version(), latest_binary_tag()
        info["binary"] = bcur or "unknown"
        info["binary_latest"] = blat or ""
        info["update_available"] = panel_upd or bool(bcur and blat and bcur != blat)
    return info
