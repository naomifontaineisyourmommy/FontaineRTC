#!/usr/bin/env bash
#
# FontaineRTC uninstaller. By default keeps your data (config.json, data.db,
# instances.db). Pass --purge to remove everything including data.
#
# Usage:  sudo bash /opt/fontaine/deploy/uninstall.sh [--purge]
#         curl -fsSL https://raw.githubusercontent.com/naomifontaineisyourmommy/FontaineRTC/master/deploy/uninstall.sh | sudo bash
set -euo pipefail

INSTALL_DIR="${FONTAINE_INSTALL_DIR:-/opt/fontaine}"
SERVICE="fontaine"
PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

say() { printf '\033[1;36m>>\033[0m %s\n' "$*"; }
[ "$(id -u)" = "0" ] || { echo "run as root (use sudo)"; exit 1; }

say "Stopping service"
systemctl stop "$SERVICE" 2>/dev/null || true
systemctl disable "$SERVICE" 2>/dev/null || true
rm -f "/etc/systemd/system/$SERVICE.service"
systemctl daemon-reload

# best-effort: stop any stray olcrtc processes (node hosts)
pkill -f olcrtc-linux-amd64 2>/dev/null || true

# Remove WDTT too if this node installed it (same mechanism the app uses;
# keeps /etc/wdtt/passwords.json). deploy.sh was persisted at install time.
if [ -x /usr/local/bin/wdtt-deploy.sh ]; then
  say "Removing WDTT (wdtt-server)"
  bash /usr/local/bin/wdtt-deploy.sh uninstall 2>/dev/null || true
  rm -f /usr/local/bin/wdtt-deploy.sh /usr/local/bin/wdtt-server.version
fi

if [ "$PURGE" = "1" ]; then
  say "Removing everything in $INSTALL_DIR (--purge)"
  rm -rf "$INSTALL_DIR"
else
  say "Removing install, keeping data ($INSTALL_DIR/data, .env)"
  if [ -d "$INSTALL_DIR" ]; then
    find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 \
      ! -name data ! -name .env -exec rm -rf {} + 2>/dev/null || true
  fi
fi
say "Uninstalled."
