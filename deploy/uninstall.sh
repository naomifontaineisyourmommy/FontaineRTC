#!/usr/bin/env bash
#
# FontaineRTC uninstaller. By default keeps your data (config.json, data.db,
# instances.db). Pass --purge to remove everything including data.
#
# Usage:  sudo bash /opt/fontaine/deploy/uninstall.sh [--purge]
#         sudo bash <(curl -fsSL https://raw.githubusercontent.com/naomifontaineisyourmommy/FontaineRTC/main/deploy/uninstall.sh)
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

# remove nginx site if present
if [ -e /etc/nginx/sites-enabled/fontaine ]; then
  rm -f /etc/nginx/sites-enabled/fontaine /etc/nginx/sites-available/fontaine
  nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null || true
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
