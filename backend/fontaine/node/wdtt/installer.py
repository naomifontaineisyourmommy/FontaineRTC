"""Install / uninstall the WDTT service on the node.

Mirrors the olcrtc updater pattern: pull `wdtt-server` + `deploy.sh` from a
GitHub release (FONTAINE_WDTT_REPO) and run deploy.sh, in a background thread with
a pollable status for the UI overlay. deploy.sh sets up the systemd service, NAT,
ip_forward and ports; it expects the binary at /tmp/wdtt-server.
"""

import os
import shutil
import stat
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from ... import updater
from . import manager, store

WDTT_REPO = os.environ.get("FONTAINE_WDTT_REPO", "")  # e.g. "naomifontaineisyourmommy/WDTT"
SERVER_ASSET = os.environ.get("FONTAINE_WDTT_SERVER_ASSET", "wdtt-server")
DEPLOY_ASSET = os.environ.get("FONTAINE_WDTT_DEPLOY_ASSET", "deploy.sh")
_VERSION_FILE = store.WDTT_DIR / "wdtt-server.version"

_status: dict = {"running": False, "step": "", "error": "", "action": ""}
_lock = threading.Lock()


def configured() -> bool:
    return bool(WDTT_REPO)


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
    if not WDTT_REPO:
        return ""
    try:
        _, tag = updater.release_asset_url(WDTT_REPO, SERVER_ASSET)
        return "" if tag == "latest" else tag
    except Exception:
        return ""


def _download(repo: str, asset: str, dest: Path, executable: bool = False) -> None:
    url, _ = updater.release_asset_url(repo, asset)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    req = urllib.request.Request(url, headers={"User-Agent": "FontaineRTC"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    if executable:
        tmp.chmod(tmp.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    tmp.replace(dest)


def start_install(*, dtls_port: int, wg_port: int, ssh_port: int,
                  main_password: str, dns: str = "1.1.1.1") -> tuple[bool, str]:
    if not WDTT_REPO:
        return False, "WDTT repo is not configured (FONTAINE_WDTT_REPO)"
    with _lock:
        if _status["running"]:
            return False, "already running"
        _status.update(running=True, step="Скачивание…", error="", action="install")
    threading.Thread(target=_install_worker,
                     args=(dtls_port, wg_port, ssh_port, main_password, dns),
                     daemon=True).start()
    return True, "install started"


def _install_worker(dtls_port, wg_port, ssh_port, main_password, dns) -> None:
    try:
        _download(WDTT_REPO, DEPLOY_ASSET, Path("/tmp/deploy.sh"))
        _set(step="Установка бинарника…")
        _, tag = updater.release_asset_url(WDTT_REPO, SERVER_ASSET)
        _download(WDTT_REPO, SERVER_ASSET, Path("/tmp/wdtt-server"), executable=True)
        _set(step="Развёртывание сервиса…")
        env = {
            **os.environ,
            "WDTT_DTLS_PORT": str(dtls_port),
            "WDTT_WG_PORT": str(wg_port),
            "WDTT_SSH_PORT": str(ssh_port),
            "WDTT_ARGS": f"-password {main_password} -dns {dns}",
        }
        p = subprocess.run(["bash", "/tmp/deploy.sh"], env=env, capture_output=True, text=True)
        if p.returncode != 0:
            _set(running=False, step="", error=(p.stderr or p.stdout or "deploy failed")[-500:])
            return
        store.WDTT_DIR.mkdir(parents=True, exist_ok=True)
        try:
            _VERSION_FILE.write_text(tag)
        except Exception:
            pass
        _set(running=False, step="", error="")
    except Exception as e:
        _set(running=False, step="", error=str(e))


def start_uninstall() -> tuple[bool, str]:
    if not WDTT_REPO:
        # uninstall can still run if deploy.sh is reachable; require repo for fetch
        return False, "WDTT repo is not configured (FONTAINE_WDTT_REPO)"
    with _lock:
        if _status["running"]:
            return False, "already running"
        _status.update(running=True, step="Удаление…", error="", action="uninstall")
    threading.Thread(target=_uninstall_worker, daemon=True).start()
    return True, "uninstall started"


def _uninstall_worker() -> None:
    try:
        _download(WDTT_REPO, DEPLOY_ASSET, Path("/tmp/deploy.sh"))
        p = subprocess.run(["bash", "/tmp/deploy.sh", "uninstall"],
                           capture_output=True, text=True)
        _VERSION_FILE.unlink(missing_ok=True)
        _set(running=False, step="",
             error="" if p.returncode == 0 else (p.stderr or p.stdout or "")[-500:])
    except Exception as e:
        _set(running=False, step="", error=str(e))


def version_info() -> dict:
    cur, lat = installed_version(), latest_version()
    return {
        "installed": manager.WdttManager().installed(),
        "version": cur or "unknown",
        "latest": lat,
        "update_available": bool(cur and lat and cur != lat),
        "configured": configured(),
    }
