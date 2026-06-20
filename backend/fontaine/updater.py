"""Self-update + olcrtc binary fetch.

- The olcrtc binary comes from the latest release (including prereleases) of the
  OlcRTC-AdvancedInteractive repo. It's only re-downloaded when missing or a newer
  release exists (same rule as WDTT) — a current binary is left untouched.
- Panel self-update pulls the FontaineRTC repo (git), reinstalls the backend and
  refreshes the binary if needed, then schedules a service restart.

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


def _asset_url(rel: dict, asset_name: str) -> str:
    """Download URL of `asset_name` within a release object, '' if absent."""
    if not isinstance(rel, dict):
        return ""
    for asset in rel.get("assets", []):
        if asset.get("name") == asset_name:
            return asset.get("browser_download_url", "")
    return ""


def release_asset_url(repo: str, asset_name: str) -> tuple[str, str]:
    """Return (download_url, tag) for `asset_name` in the newest release of `repo`.

    Considers BOTH `/releases/latest` (authoritative for the latest full release,
    but excludes pre-releases) and the `/releases` list (includes pre-releases, but
    GitHub may omit a just-published release from it for a while — a real CDN/
    replication lag we hit in practice). We collect every published release that
    actually carries the asset from both sources and pick the newest by
    `published_at`. Falls back to the conventional latest/download path."""
    candidates: list[tuple[str, str, str]] = []   # (published_at, tag, url)

    def consider(rel: dict) -> None:
        if not isinstance(rel, dict) or rel.get("draft"):
            return
        url = _asset_url(rel, asset_name)
        if url:
            candidates.append((rel.get("published_at") or rel.get("created_at") or "",
                               rel.get("tag_name", "?"), url))

    try:
        consider(_api(f"https://api.github.com/repos/{repo}/releases/latest"))
    except Exception:
        pass   # 404 when the repo has no non-prerelease release yet
    try:
        releases = _api(f"https://api.github.com/repos/{repo}/releases")
        if isinstance(releases, list):
            for rel in releases:
                consider(rel)
    except Exception:
        pass

    if candidates:
        # ISO-8601 UTC timestamps sort lexicographically; newest first.
        candidates.sort(key=lambda c: c[0], reverse=True)
        _, tag, url = candidates[0]
        return url, tag

    return (f"https://github.com/{repo}/releases/latest/download/{asset_name}", "latest")


def binary_download_url(repo: str = BINARY_REPO) -> tuple[str, str]:
    """(url, tag) for the newest olcrtc binary release."""
    return release_asset_url(repo, BINARY_ASSET)


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


def ensure_binary(dest: Path, repo: str = BINARY_REPO) -> str:
    """Download the olcrtc binary only if missing or a newer release exists —
    same rule as WDTT. Returns a short status string; a current binary is left
    untouched (no download)."""
    if dest.exists() and _binary_up_to_date():
        return f"up to date ({binary_version()}) — untouched"
    return f"updated to {download_binary(dest, repo)}"


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
    """Repo root that contains backend/ (where the service is installed).

    Prefer the explicit FONTAINE_INSTALL_DIR (set by install.sh) — when the
    package is pip-installed into a venv, the __file__ heuristic points at
    site-packages, not the git checkout."""
    env = os.environ.get("FONTAINE_INSTALL_DIR")
    if env:
        return Path(env)
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


def update_panel_code(install_dir: Path) -> tuple[bool, str]:
    """git fetch + hard reset + reinstall the backend (FontaineRTC panel only).
    The repo is the source of truth — hard reset so locally regenerated files
    (e.g. setuptools build/) can never block the update. Ignored data/.env/config
    are untracked and stay untouched. Caller is responsible for the restart."""
    ok, out = _run(["git", "fetch", "origin", PANEL_BRANCH], cwd=install_dir)
    if not ok:
        return False, f"git fetch: {out}"
    ok, out = _run(["git", "reset", "--hard", f"origin/{PANEL_BRANCH}"], cwd=install_dir)
    if not ok:
        return False, f"git reset: {out}"
    pip = install_dir / ".venv" / "bin" / "pip"
    if pip.exists():
        ok, out = _run([str(pip), "install", "-q", str(install_dir / "backend")])
        if not ok:
            return False, f"pip: {out}"
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


def start_update(install_dir: Path, *, do_panel: bool = True,
                 do_binary: bool = False, extra=None) -> tuple[bool, str]:
    """Begin a background update of only the parts the caller flags as stale, so
    each package (FontaineRTC / olcrtc / WDTT) updates independently:

    - ``do_panel``  — git reset + pip reinstall the panel, then restart the service.
    - ``do_binary`` — refresh the olcrtc binary (``ensure_binary`` re-checks too).
    - ``extra()``   — optional callable updating WDTT, returns ``(ok, msg)``; kept
      out of this module to avoid an import cycle.

    The panel step is fatal (aborts with an error); olcrtc/WDTT are best-effort.
    The service is restarted **only** when the panel itself changed — a binary- or
    WDTT-only update needs no panel restart (the UI just reloads). Returns
    immediately; the UI polls ``update_status()``."""
    # Ordered plan of (label, fn, fatal) — only the stale parts.
    plan: list = []
    if do_panel:
        plan.append(("Обновление панели FontaineRTC…",
                     lambda: update_panel_code(install_dir), True))
    if do_binary:
        plan.append(("Обновление бинарника olcrtc…",
                     lambda: (True, ensure_binary(install_dir / BINARY_ASSET)), False))
    if extra:
        plan.append(("Обновление WDTT…", extra, False))
    if not plan:
        return False, "nothing to update"

    total = len(plan) + 1   # + the final restart / finish step

    with _status_lock:
        if _status["updating"]:
            return False, "update already in progress"
        _status.update(updating=True, step="Подключение…", index=0, total=total, error="")

    def worker():
        for i, (label, fn, fatal) in enumerate(plan, start=1):
            _set_status(index=i, step=label)
            try:
                ok, msg = fn()
            except Exception as e:
                ok, msg = False, str(e)
            if not ok and fatal:
                _set_status(updating=False, step="", error=msg)
                return
            # non-fatal failures (binary/WDTT) are left as-is: better a stale
            # component than a failed update; the panel (if any) still proceeds.
        if do_panel:
            _set_status(index=total, step="Перезапуск…")
            schedule_restart(1.5)   # systemd brings us back; UI reloads after
        else:
            # No panel change → no service restart; the UI reloads on its own.
            _set_status(updating=False, index=total, step="Готово")

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


# Public predicates the caller uses to plan which parts to update. An unknown
# local version counts as "not up to date" (so it gets refreshed); an unknown
# remote (offline) also returns False, but the binary/WDTT steps are best-effort.
def panel_up_to_date() -> bool:
    return _panel_up_to_date()


def binary_up_to_date() -> bool:
    return _binary_up_to_date()


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
        # Offer an update whenever a remote tag is known and the installed one
        # differs — including when the installed version is unknown (missing
        # sidecar). Only an empty remote tag (offline / API down) suppresses it,
        # so we never false-prompt when we couldn't check. Matches is_up_to_date.
        binary_upd = bool(blat) and bcur != blat
        info["update_available"] = panel_upd or binary_upd
    return info
