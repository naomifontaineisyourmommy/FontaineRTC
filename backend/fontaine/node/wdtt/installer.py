"""Install / update / uninstall the WDTT service on the node.

Source = the upstream project's APK release. The prebuilt server binary isn't in
git nor a standalone asset — it lives inside WDTT-universal.apk at assets/server
(linux/amd64 Go ELF), with assets/deploy.sh. We download the APK from the latest
release, extract both with stdlib zipfile, run deploy.sh, record the release tag
as the WDTT version, and delete the APK. deploy.sh is kept for `uninstall`
(same mechanism the Android app uses; keeps passwords.json).

WDTT is part of the node lifecycle: installed at panel install, updated together
with FontaineRTC + olcrtc, removed at panel uninstall.
"""

import json
import os
import shutil
import stat
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

from ... import updater
from . import manager, store

WDTT_REPO = os.environ.get("FONTAINE_WDTT_REPO", "amurcanov/proxy-turn-vk-android")
APK_ASSET = os.environ.get("FONTAINE_WDTT_APK", "WDTT-universal.apk")

DEPLOY_PERSIST = Path("/usr/local/bin/wdtt-deploy.sh")
_VERSION_FILE = manager.BINARY.with_name(manager.BINARY.name + ".version")
_PARAMS_FILE = store.WDTT_DIR / ".fontaine-install.json"   # ports/dns for re-deploy

_LATEST_TTL = 300.0
_latest_cache: dict = {"tag": "", "at": 0.0}

_status: dict = {"running": False, "step": "", "error": "", "action": ""}
_lock = threading.Lock()


def is_installed() -> bool:
    return manager.BINARY.exists()


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


def is_up_to_date() -> bool:
    """True only when WDTT is installed and confirmed at the latest tag."""
    cur, lat = installed_version(), latest_version()
    return bool(is_installed() and cur and lat and cur == lat)


def version_info() -> dict:
    cur, lat = installed_version(), latest_version()
    inst = is_installed()
    return {
        "installed": inst,
        "version": cur or ("unknown" if inst else ""),
        "latest": lat,
        "update_available": bool(inst and cur and lat and cur != lat),
        "repo": WDTT_REPO,
    }


# ── params persistence (so updates re-deploy with the same ports) ───────────────
def _save_params(dtls: int, wg: int, ssh: int, dns: str) -> None:
    try:
        store.WDTT_DIR.mkdir(parents=True, exist_ok=True)
        _PARAMS_FILE.write_text(json.dumps(
            {"dtls": dtls, "wg": wg, "ssh": ssh, "dns": dns}))
    except Exception:
        pass


def _load_params() -> dict:
    try:
        return json.loads(_PARAMS_FILE.read_text())
    except Exception:
        return {"dtls": manager.DTLS_PORT, "wg": manager.WG_PORT, "ssh": 22, "dns": "1.1.1.1"}


# ── core install (synchronous) ─────────────────────────────────────────────────
def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "FontaineRTC"})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def install_sync(*, dtls_port: int, wg_port: int, ssh_port: int,
                 main_password: str, dns: str = "1.1.1.1") -> tuple[bool, str]:
    """Download the latest APK, extract server+deploy.sh, run deploy.sh. Blocking."""
    apk = Path(tempfile.gettempdir()) / "wdtt-universal.apk"
    try:
        url, tag = updater.release_asset_url(WDTT_REPO, APK_ASSET)
        _download(url, apk)
        with zipfile.ZipFile(apk) as z:
            with z.open("assets/server") as s, open("/tmp/wdtt-server", "wb") as d:
                shutil.copyfileobj(s, d)
            with z.open("assets/deploy.sh") as s, open("/tmp/deploy.sh", "wb") as d:
                shutil.copyfileobj(s, d)
        os.chmod("/tmp/wdtt-server", 0o755)
        env = {
            **os.environ,
            "WDTT_DTLS_PORT": str(dtls_port), "WDTT_WG_PORT": str(wg_port),
            "WDTT_SSH_PORT": str(ssh_port),
            "WDTT_ARGS": f"-password {main_password} -dns {dns}",
        }
        p = subprocess.run(["bash", "/tmp/deploy.sh"], env=env, capture_output=True, text=True)
        if p.returncode != 0:
            return False, (p.stderr or p.stdout or "deploy failed")[-600:]
        try:
            shutil.copyfile("/tmp/deploy.sh", DEPLOY_PERSIST)
            DEPLOY_PERSIST.chmod(0o755)
            _VERSION_FILE.write_text(tag)
        except Exception:
            pass
        _save_params(dtls_port, wg_port, ssh_port, dns)
        return True, tag
    except Exception as e:
        return False, str(e)
    finally:
        for leftover in (apk, Path("/tmp/deploy.sh"), Path("/tmp/wdtt-server")):
            try:
                leftover.unlink(missing_ok=True)
            except Exception:
                pass


def reinstall_latest() -> tuple[bool, str]:
    """Re-deploy the latest APK keeping current ports + main password (for updates)."""
    pr = _load_params()
    main_pw = store.load().get("main_password", "") or manager.gen_password()
    return install_sync(dtls_port=pr["dtls"], wg_port=pr["wg"], ssh_port=pr["ssh"],
                        main_password=main_pw, dns=pr.get("dns", "1.1.1.1"))


# ── background install (for the UI overlay) ─────────────────────────────────────
def start_install(*, dtls_port: int, wg_port: int, ssh_port: int,
                  main_password: str, dns: str = "1.1.1.1") -> tuple[bool, str]:
    with _lock:
        if _status["running"]:
            return False, "already running"
        _status.update(running=True, step="Установка WDTT…", error="", action="install")

    def worker():
        ok, msg = install_sync(dtls_port=dtls_port, wg_port=wg_port, ssh_port=ssh_port,
                               main_password=main_password, dns=dns)
        _set(running=False, step="", error="" if ok else msg)

    threading.Thread(target=worker, daemon=True).start()
    return True, "install started"


# ── uninstall ──────────────────────────────────────────────────────────────---
def start_uninstall() -> tuple[bool, str]:
    with _lock:
        if _status["running"]:
            return False, "already running"
        _status.update(running=True, step="Удаление WDTT…", error="", action="uninstall")
    threading.Thread(target=_uninstall_worker, daemon=True).start()
    return True, "uninstall started"


def _uninstall_worker() -> None:
    apk = None
    try:
        deploy = DEPLOY_PERSIST
        if not deploy.exists():
            apk = Path(tempfile.gettempdir()) / "wdtt-universal.apk"
            url, _ = updater.release_asset_url(WDTT_REPO, APK_ASSET)
            _download(url, apk)
            with zipfile.ZipFile(apk) as z, z.open("assets/deploy.sh") as s, \
                    open("/tmp/deploy.sh", "wb") as d:
                shutil.copyfileobj(s, d)
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
