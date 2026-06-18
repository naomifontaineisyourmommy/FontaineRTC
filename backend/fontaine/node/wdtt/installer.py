"""Install / uninstall the WDTT service on the node.

Source = the upstream project's APK release. The prebuilt server binary isn't in
git nor a standalone asset — it lives inside WDTT-universal.apk at assets/server
(linux/amd64 Go ELF), together with assets/deploy.sh. So we download the APK from
the latest release, extract both with stdlib zipfile, run deploy.sh, record the
release tag as the WDTT version, and delete the APK. deploy.sh is kept for a later
`uninstall` (same mechanism the Android app uses).

Runs in a background thread with a pollable status for the UI overlay.
"""

import os
import shutil
import stat
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

from ... import updater
from . import manager

WDTT_REPO = os.environ.get("FONTAINE_WDTT_REPO", "amurcanov/proxy-turn-vk-android")
APK_ASSET = os.environ.get("FONTAINE_WDTT_APK", "WDTT-universal.apk")

DEPLOY_PERSIST = Path("/usr/local/bin/wdtt-deploy.sh")   # kept for uninstall
_VERSION_FILE = manager.BINARY.with_name(manager.BINARY.name + ".version")

_LATEST_TTL = 300.0
_latest_cache: dict = {"tag": "", "at": 0.0}

_status: dict = {"running": False, "step": "", "error": "", "action": ""}
_lock = threading.Lock()


def install_status() -> dict:
    with _lock:
        return dict(_status)


def _set(**kw) -> None:
    with _lock:
        _status.update(kw)


def installed_version() -> str:
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def latest_version() -> str:
    now = time.time()
    if _latest_cache["tag"] and now - _latest_cache["at"] < _LATEST_TTL:
        return _latest_cache["tag"]
    try:
        _, tag = updater.release_asset_url(WDTT_REPO, APK_ASSET)
    except Exception:
        tag = ""
    if tag and tag != "latest":
        _latest_cache.update(tag=tag, at=now)
        return tag
    return _latest_cache["tag"]


def version_info() -> dict:
    cur = installed_version()
    lat = latest_version()
    installed = manager.WdttManager().installed()
    return {
        "installed": installed,
        "version": cur or ("unknown" if installed else ""),
        "latest": lat,
        "update_available": bool(installed and cur and lat and cur != lat),
        "repo": WDTT_REPO,
    }


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "FontaineRTC"})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def _extract_from_apk(apk: Path, server_dest: Path, deploy_dest: Path) -> None:
    with zipfile.ZipFile(apk) as z:
        with z.open("assets/server") as src, open(server_dest, "wb") as d:
            shutil.copyfileobj(src, d)
        with z.open("assets/deploy.sh") as src, open(deploy_dest, "wb") as d:
            shutil.copyfileobj(src, d)
    server_dest.chmod(server_dest.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# ── install ────────────────────────────────────────────────────────────────---
def start_install(*, dtls_port: int, wg_port: int, ssh_port: int,
                  main_password: str, dns: str = "1.1.1.1") -> tuple[bool, str]:
    with _lock:
        if _status["running"]:
            return False, "already running"
        _status.update(running=True, step="Скачивание APK…", error="", action="install")
    threading.Thread(target=_install_worker,
                     args=(dtls_port, wg_port, ssh_port, main_password, dns),
                     daemon=True).start()
    return True, "install started"


def _install_worker(dtls_port, wg_port, ssh_port, main_password, dns) -> None:
    apk = Path(tempfile.gettempdir()) / "wdtt-universal.apk"
    try:
        url, tag = updater.release_asset_url(WDTT_REPO, APK_ASSET)
        _download(url, apk)
        _set(step="Извлечение бинарника…")
        _extract_from_apk(apk, Path("/tmp/wdtt-server"), Path("/tmp/deploy.sh"))
        _set(step="Развёртывание сервиса…")
        env = {
            **os.environ,
            "WDTT_DTLS_PORT": str(dtls_port),
            "WDTT_WG_PORT": str(wg_port),
            "WDTT_SSH_PORT": str(ssh_port),
            "WDTT_ARGS": f"-password {main_password} -dns {dns}",
        }
        import subprocess
        p = subprocess.run(["bash", "/tmp/deploy.sh"], env=env, capture_output=True, text=True)
        if p.returncode != 0:
            _set(running=False, step="", error=(p.stderr or p.stdout or "deploy failed")[-600:])
            return
        # keep deploy.sh for later uninstall; record version
        try:
            shutil.copyfile("/tmp/deploy.sh", DEPLOY_PERSIST)
            DEPLOY_PERSIST.chmod(0o755)
            _VERSION_FILE.write_text(tag)
        except Exception:
            pass
        _set(running=False, step="", error="")
    except Exception as e:
        _set(running=False, step="", error=str(e))
    finally:
        for leftover in (apk, Path("/tmp/deploy.sh"), Path("/tmp/wdtt-server")):
            try:
                leftover.unlink(missing_ok=True)
            except Exception:
                pass


# ── uninstall ──────────────────────────────────────────────────────────────---
def start_uninstall() -> tuple[bool, str]:
    with _lock:
        if _status["running"]:
            return False, "already running"
        _status.update(running=True, step="Удаление…", error="", action="uninstall")
    threading.Thread(target=_uninstall_worker, daemon=True).start()
    return True, "uninstall started"


def _uninstall_worker() -> None:
    import subprocess
    deploy = DEPLOY_PERSIST
    apk = None
    try:
        if not deploy.exists():
            # no persisted copy — re-fetch the APK just to get deploy.sh
            apk = Path(tempfile.gettempdir()) / "wdtt-universal.apk"
            url, _ = updater.release_asset_url(WDTT_REPO, APK_ASSET)
            _download(url, apk)
            with zipfile.ZipFile(apk) as z, z.open("assets/deploy.sh") as src, \
                    open("/tmp/deploy.sh", "wb") as d:
                shutil.copyfileobj(src, d)
            deploy = Path("/tmp/deploy.sh")
        p = subprocess.run(["bash", str(deploy), "uninstall"], capture_output=True, text=True)
        _VERSION_FILE.unlink(missing_ok=True)
        DEPLOY_PERSIST.unlink(missing_ok=True)
        _set(running=False, step="",
             error="" if p.returncode == 0 else (p.stderr or p.stdout or "")[-600:])
    except Exception as e:
        _set(running=False, step="", error=str(e))
    finally:
        if apk:
            try:
                apk.unlink(missing_ok=True)
            except Exception:
                pass
