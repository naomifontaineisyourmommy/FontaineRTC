#!/usr/bin/env bash
#
# FontaineRTC updater — pulls the latest code from the repo, reinstalls the
# backend, refreshes the olcrtc binary (node role) and restarts the service.
# The interface "↺ Обновить" button does the same thing.
#
# Usage:  sudo bash /opt/fontaine/deploy/update.sh
#         sudo bash <(curl -fsSL https://raw.githubusercontent.com/naomifontaineisyourmommy/FontaineRTC/main/deploy/update.sh)
set -euo pipefail

INSTALL_DIR="${FONTAINE_INSTALL_DIR:-/opt/fontaine}"
SERVICE="fontaine"
BINARY_NAME="olcrtc-linux-amd64"

say() { printf '\033[1;36m>>\033[0m %s\n' "$*"; }
[ "$(id -u)" = "0" ] || { echo "run as root (use sudo)"; exit 1; }
[ -d "$INSTALL_DIR/.git" ] || { echo "FontaineRTC not found in $INSTALL_DIR — run install.sh first"; exit 1; }

say "Pulling latest code"
git -C "$INSTALL_DIR" pull --ff-only

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

say "Restarting service"
systemctl restart "$SERVICE"
say "Updated. Logs: journalctl -fu $SERVICE"
