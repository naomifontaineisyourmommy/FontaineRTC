#!/usr/bin/env bash
# FontaineRTC bare-metal installer (venv + systemd).
# Usage:  sudo FONTAINE_ROLE=node bash install.sh
#         sudo FONTAINE_ROLE=admin bash install.sh
#
# Skeleton — fleshed out in migration phase 5 (frontend build, nginx/HTTPS,
# key generation, role-specific prompts). Mirrors the originals' install.sh UX.
set -euo pipefail

ROLE="${FONTAINE_ROLE:-node}"
APP_DIR="/opt/fontaine"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo ">> Installing FontaineRTC (role=$ROLE) into $APP_DIR"

install -d "$APP_DIR"
cp -r "$REPO_DIR/backend/." "$APP_DIR/"

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install "$APP_DIR"

# .env (preserve existing keys on re-run)
if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$REPO_DIR/.env.example" "$APP_DIR/.env"
  sed -i "s/^FONTAINE_ROLE=.*/FONTAINE_ROLE=$ROLE/" "$APP_DIR/.env"
  # TODO(phase 5): generate api_key + panel_password and print once.
fi

# systemd unit
cp "$REPO_DIR/deploy/fontaine.service" "/etc/systemd/system/fontaine.service"
systemctl daemon-reload
systemctl enable --now fontaine

echo ">> Done. Check: systemctl status fontaine ; journalctl -fu fontaine"
