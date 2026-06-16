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
import urllib.request
from pathlib import Path

PANEL_REPO = os.environ.get("FONTAINE_REPO", "naomifontaineisyourmommy/FontaineRTC")
BINARY_REPO = os.environ.get("FONTAINE_BINARY_REPO", "naomifontaineisyourmommy/OlcRTC-AdvancedInteractive")
BINARY_ASSET = os.environ.get("FONTAINE_BINARY_ASSET", "olcrtc-linux-amd64")
RESTART_CMD = os.environ.get("FONTAINE_RESTART_CMD", "systemctl restart fontaine")

_UA = {"User-Agent": "FontaineRTC-updater"}


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


def download_binary(dest: Path, repo: str = BINARY_REPO) -> str:
    """Download the latest olcrtc binary to `dest` (atomic, chmod +x). Returns tag."""
    url, tag = binary_download_url(repo)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    tmp.chmod(tmp.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    tmp.replace(dest)
    return tag


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


def self_update(install_dir: Path, fetch_binary: bool = True) -> tuple[bool, str]:
    """git pull + reinstall backend + (optionally) refresh binary. Caller restarts."""
    steps: list[str] = []
    ok, out = _run(["git", "pull", "--ff-only"], cwd=install_dir)
    steps.append(f"git pull: {out or 'ok'}")
    if not ok:
        return False, " | ".join(steps)

    pip = install_dir / ".venv" / "bin" / "pip"
    if pip.exists():
        ok, out = _run([str(pip), "install", "-q", str(install_dir / "backend")])
        steps.append(f"pip: {'ok' if ok else out}")
        if not ok:
            return False, " | ".join(steps)

    if fetch_binary:
        try:
            tag = download_binary(install_dir / BINARY_ASSET)
            steps.append(f"binary: {tag}")
        except Exception as e:
            steps.append(f"binary fetch failed: {e}")

    return True, " | ".join(steps)
