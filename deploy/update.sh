#!/usr/bin/env bash
#
# FontaineRTC updater — pulls the latest code from the repo, reinstalls the
# backend, refreshes the olcrtc binary (node role) and restarts the service.
# The interface "↺ Обновить" button does the same thing.
#
# Usage:  sudo bash /opt/fontaine/deploy/update.sh
#         curl -fsSL https://raw.githubusercontent.com/naomifontaineisyourmommy/FontaineRTC/master/deploy/update.sh | sudo bash
set -euo pipefail

INSTALL_DIR="${FONTAINE_INSTALL_DIR:-/opt/fontaine}"
SERVICE="fontaine"
BRANCH="${FONTAINE_BRANCH:-master}"
BINARY_NAME="olcrtc-linux-amd64"

say() { printf '\033[1;36m>>\033[0m %s\n' "$*"; }
[ "$(id -u)" = "0" ] || { echo "run as root (use sudo)"; exit 1; }
[ -d "$INSTALL_DIR/.git" ] || { echo "FontaineRTC not found in $INSTALL_DIR — run install.sh first"; exit 1; }

say "Pulling latest code"
# Hard reset to the remote — the repo is authoritative; locally regenerated files
# (e.g. setuptools build/) must not block updates. Ignored data/.env stay untouched.
git -C "$INSTALL_DIR" fetch origin "$BRANCH"
git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH"

say "Reinstalling backend"
"$INSTALL_DIR/.venv/bin/pip" install -q "$INSTALL_DIR/backend"

ROLE="$(grep '^FONTAINE_ROLE=' "$INSTALL_DIR/.env" 2>/dev/null | cut -d= -f2- || echo node)"
if [ "$ROLE" = "node" ]; then
  say "Refreshing olcrtc binary (latest release)"
  "$INSTALL_DIR/.venv/bin/python" - <<PY
from pathlib import Path
from fontaine.updater import download_binary
print("   olcrtc release:", download_binary(Path("$INSTALL_DIR/$BINARY_NAME")))
PY
fi

# Ensure the SPA path is set (older installs predate this).
grep -q '^FONTAINE_DIST_DIR=' "$INSTALL_DIR/.env" 2>/dev/null \
  || echo "FONTAINE_DIST_DIR=$INSTALL_DIR/frontend/dist" >> "$INSTALL_DIR/.env"
# Ensure the install dir is set (needed so the panel can locate its own checkout).
grep -q '^FONTAINE_INSTALL_DIR=' "$INSTALL_DIR/.env" 2>/dev/null \
  || echo "FONTAINE_INSTALL_DIR=$INSTALL_DIR" >> "$INSTALL_DIR/.env"

# Ensure admin has a push URL so nodes receive a push target (else: only polling).
if [ "$ROLE" = "admin" ] && ! grep -q '^FONTAINE_PANEL_URL=' "$INSTALL_DIR/.env" 2>/dev/null; then
  IP="$(curl -fsSL https://api.ipify.org 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')"
  PORT="$(grep '^FONTAINE_PANEL_PORT=' "$INSTALL_DIR/.env" | cut -d= -f2-)"
  [ -n "$IP" ] && echo "FONTAINE_PANEL_URL=http://$IP:${PORT:-8080}" >> "$INSTALL_DIR/.env"
fi

# Refresh the systemd unit so unit-level tweaks (timeouts, etc.) propagate.
if [ -f "$INSTALL_DIR/deploy/$SERVICE.service" ]; then
  cp "$INSTALL_DIR/deploy/$SERVICE.service" "/etc/systemd/system/$SERVICE.service"
  systemctl daemon-reload
fi

say "Restarting service"
systemctl restart "$SERVICE"
say "Updated. Logs: journalctl -fu $SERVICE"
