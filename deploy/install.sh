#!/usr/bin/env bash
#
# FontaineRTC installer — pulls everything from the public repo and sets up a
# systemd service. Safe to re-run (acts as an update, preserving secrets/data).
#
# Usage (one-liner; pipe form works even without /dev/fd process substitution):
#   curl -fsSL https://raw.githubusercontent.com/naomifontaineisyourmommy/FontaineRTC/master/deploy/install.sh | sudo FONTAINE_ROLE=node  bash
#   curl -fsSL https://raw.githubusercontent.com/naomifontaineisyourmommy/FontaineRTC/master/deploy/install.sh | sudo FONTAINE_ROLE=admin bash
#
# Optional env:
#   FONTAINE_PORT=8080            panel port
set -euo pipefail

REPO_URL="${FONTAINE_REPO_URL:-https://github.com/naomifontaineisyourmommy/FontaineRTC.git}"
INSTALL_DIR="${FONTAINE_INSTALL_DIR:-/opt/fontaine}"
SERVICE="fontaine"
ROLE="${FONTAINE_ROLE:-node}"
PORT="${FONTAINE_PORT:-8080}"
BINARY_NAME="olcrtc-linux-amd64"

say() { printf '\033[1;36m>>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" = "0" ] || die "run as root (use sudo)"
case "$ROLE" in node|admin) ;; *) die "FONTAINE_ROLE must be 'node' or 'admin'";; esac

say "Installing FontaineRTC (role=$ROLE) into $INSTALL_DIR"

# ── system dependencies ──
if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq git python3 python3-venv python3-pip curl ca-certificates >/dev/null
else
  command -v git >/dev/null || die "git required"
  command -v python3 >/dev/null || die "python3 required"
fi

# ── fetch / update source ──
BRANCH="${FONTAINE_BRANCH:-master}"
if [ -d "$INSTALL_DIR/.git" ]; then
  say "Updating existing checkout"
  git -C "$INSTALL_DIR" fetch origin "$BRANCH"
  git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH"
else
  say "Cloning repository"
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

# ── python environment ──
say "Setting up Python environment"
[ -d "$INSTALL_DIR/.venv" ] || python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install -q --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -q "$INSTALL_DIR/backend"

# ── .env (generate once; preserve secrets on re-run) ──
ENV_FILE="$INSTALL_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  say "Generating configuration"
  API_KEY="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
  PASSWORD="$(python3 -c 'import secrets;print(secrets.token_urlsafe(9))')"
  cat > "$ENV_FILE" <<EOF
FONTAINE_ROLE=$ROLE
FONTAINE_PANEL_HOST=0.0.0.0
FONTAINE_PANEL_PORT=$PORT
FONTAINE_DATA_DIR=$INSTALL_DIR/data
FONTAINE_INSTALL_DIR=$INSTALL_DIR
FONTAINE_BINARY_PATH=$INSTALL_DIR/$BINARY_NAME
FONTAINE_API_KEY=$API_KEY
FONTAINE_PANEL_PASSWORD=$PASSWORD
EOF
  chmod 600 "$ENV_FILE"
  NEW_INSTALL=1
else
  say "Keeping existing $ENV_FILE"
fi

# Ensure the SPA path is set (installed package can't find frontend/dist relatively).
grep -q '^FONTAINE_DIST_DIR=' "$ENV_FILE" \
  || echo "FONTAINE_DIST_DIR=$INSTALL_DIR/frontend/dist" >> "$ENV_FILE"
# Ensure the install dir is set (pip-installed package can't locate the checkout).
grep -q '^FONTAINE_INSTALL_DIR=' "$ENV_FILE" \
  || echo "FONTAINE_INSTALL_DIR=$INSTALL_DIR" >> "$ENV_FILE"

# ── olcrtc binary (node role) — always the latest release ──
if [ "$ROLE" = "node" ]; then
  say "Downloading latest olcrtc binary"
  "$INSTALL_DIR/.venv/bin/python" - <<PY
from pathlib import Path
from fontaine.updater import download_binary
tag = download_binary(Path("$INSTALL_DIR/$BINARY_NAME"))
print("   olcrtc release:", tag)
PY

  # WDTT (second protocol): install on fresh setup, refresh on re-run.
  say "Installing WDTT (server + deploy)"
  FONTAINE_INSTALL_DIR="$INSTALL_DIR" "$INSTALL_DIR/.venv/bin/python" - <<'PY' || say "WDTT step failed — you can retry from the panel"
import secrets
from fontaine.node.wdtt import installer
if installer.is_installed():
    ok, msg = installer.reinstall_latest()
else:
    ok, msg = installer.install_sync(dtls_port=56000, wg_port=56001, ssh_port=22,
                                     main_password=secrets.token_urlsafe(12), dns="1.1.1.1")
print("   WDTT:", "ok" if ok else msg)
raise SystemExit(0 if ok else 1)
PY
fi

# ── detect server IP (used for panel URL + push target) ──
IP="$(curl -fsSL https://api.ipify.org 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')"
[ -n "$IP" ] || IP="<this-server-ip>"

# Admin pushes are registered on nodes using this URL, so nodes can reach the
# panel directly over HTTP (anyone who wants TLS can put their own reverse proxy
# in front — the panel doesn't manage nginx/certificates).
if [ "$ROLE" = "admin" ]; then
  grep -q '^FONTAINE_PANEL_URL=' "$ENV_FILE" \
    || echo "FONTAINE_PANEL_URL=http://$IP:$PORT" >> "$ENV_FILE"
fi

# ── systemd service ──
say "Installing systemd service"
cp "$INSTALL_DIR/deploy/$SERVICE.service" "/etc/systemd/system/$SERVICE.service"
systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null 2>&1 || true
systemctl restart "$SERVICE"

# ── summary ──
echo
cat <<'ART'
⠀⠀⠀⠀⠀⠀⢀⣴⣾⣿⣿⣿⡿⠁⢀⣴⣶⣾⡟⠀⣰⡾⠀⠀⠀⣰⣶⡇⠀⢰⣶⡄⠀⠀⢸⣷⣦⡀⠀⠀⠀⠈⢹⣿⣿⡸⣝⠷⢭⢛
⠀⠀⠀⠀⠀⠰⠋⢸⣿⣿⣿⡟⢀⣴⣿⣿⣿⠏⠀⣴⣿⠃⠀⠀⣰⣿⣿⢁⠀⣾⣿⣿⠀⠀⠈⣿⣿⣿⣆⠀⠀⠀⠀⠻⡿⠀⠈⠀⠉⠉
⠀⠀⠀⠀⠀⠀⢀⣿⣿⣿⡟⢠⣾⣿⣿⣿⡏⠀⣸⣿⡏⠀⠀⢈⣿⠿⠣⠾⠄⠿⠿⠿⠇⡄⠀⢸⣿⣿⣿⣧⠀⠀⠈⣆⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⣼⣿⣿⠟⠀⣿⣿⣿⣿⡟⠀⢰⣿⡿⠀⠀⢀⣤⠖⠀⣀⣤⡄⢰⣶⣶⡆⣶⡀⠀⢿⣿⣿⣿⣆⠀⠀⢹⣦⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⢰⣿⣿⠏⠀⢠⣿⣿⣿⡿⠁⠀⣿⣿⠇⠀⢀⡚⠉⣢⣾⣿⣿⣿⢸⣿⣿⢣⣏⢿⡄⢸⣿⣿⣿⣿⡀⠀⠀⣿⣇⠀⠀⠀⢀
⠀⠀⡀⠀⠀⢼⣿⠃⠀⠀⢸⠿⠿⠛⠁⠀⢸⣿⣏⠃⢠⠟⣱⣾⣿⡿⠟⣫⣾⡆⠿⠟⠘⠉⠙⠛⠈⠛⠛⠟⠛⣃⠀⠀⢹⣿⡆⠀⠀⠀
⠀⠀⠀⠀⠀⣿⠃⠀⠀⠀⠰⠾⠃⠀⠀⠀⣿⡟⠁⠠⢫⣾⣿⣿⣿⡇⣾⣿⠋⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⣿⠀⠀⠸⣿⣿⠀⠀⠀
⠀⠀⠀⠀⠀⠇⠀⠀⠀⠀⠠⠆⠀⠀⠀⢀⠋⠀⢀⣴⣿⣿⣿⣿⣿⣿⡏⠁⡠⠄⢀⣤⡄⡴⠄⠰⠎⣡⣦⠻⢿⣿⠀⢂⠀⣿⣿⡇⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⣿⣿⣿⣿⣿⣿⣿⣶⡧⢺⣥⣴⣶⣾⣿⣿⣿⣿⠫⠁⡰⡙⡻⠀⠘⠀⢹⣿⣷⠀⠀
⠀⠀⠀⠀⠀⢀⡇⠀⠀⠀⢀⡄⠀⠀⢀⣴⣿⣿⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⢁⣠⣶⣿⡽⡄⠀⠀⠀⢸⣿⣿⡂⠀
⠀⠀⠀⠀⠀⡼⠀⠀⠀⠀⠈⠀⠀⠀⠀⢈⣿⣿⢇⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⣶⣿⡿⠟⠁⠠⢩⡄⠀⠀⣼⣿⣿⠀⠀
⠀⠀⠀⠀⠠⠃⠀⠀⠀⠀⠀⠀⣠⠄⣀⣬⣽⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⢛⣁⣀⣤⣶⣾⡏⡇⠀⢀⣿⣿⣿⠀⠀
⠀⠀⠀⠀⠀⠀⠀⣴⣏⡠⠀⣳⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⣸⣿⣿⡟⢸⠀
⠀⠀⠀⠀⠀⠀⠰⣬⣬⣥⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣤⣀⣀⣀⡁⠀⢠⣿⣿⣿⠃⣼⠀
⠀⠀⠀⠀⠀⠀⠀⠈⡙⠻⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⢛⣛⣛⣛⣛⣛⣻⠿⢿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠀⢀⣿⣿⣿⠏⣰⡏⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢿⣶⣶⣾⣿⣿⣿⣿⣿⣿⣿⣿⠟⡥⠞⠋⠁⠀⠀⠀⠀⢀⣀⡀⣿⣿⣿⣿⣿⣿⣿⣿⠃⢀⣾⣿⣿⠏⣰⠟⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠘⠛⠋⢁⣴⣿⣿⣿⣿⣿⣿⣿⠼⠀⠀⠀⠀⠀⠀⣠⣾⣿⣿⢇⣿⣿⣿⣿⣿⣿⣿⠃⠀⠼⣛⣥⣥⣶⣶⣶⣦⣤
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠠⣶⣿⡿⢻⣿⣿⣿⣿⣿⣿⣦⡂⠀⣀⣴⣶⣾⣿⡟⢹⡏⣼⣿⣿⣿⣿⣿⣿⠃⢀⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿
⠀⢀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠋⢀⣾⣿⣿⣿⣿⣿⣿⣿⣷⡐⣿⣿⣿⣿⡿⢡⡟⣴⣿⣿⣿⣿⣿⡿⠁⣰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⠀⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠺⣿⣿⣿⣿⣿⣿⣿⣿⣿⣇⢻⣿⣿⣿⠇⡟⣼⣿⣿⣿⣿⣿⡟⠁⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⠀⢹⡟⣶⡀⠀⠀⢠⠀⠀⠀⠀⠀⠈⠛⢿⣿⣿⣿⣿⣿⣿⣿⣌⢿⣿⣿⢸⣸⣿⣿⣿⣿⣿⠟⠀⢰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⠀⠀⠃⣿⣷⡀⠀⢸⡆⠀⠀⠀⠀⠀⠀⠀⢨⣛⠿⣿⣿⣿⣿⣿⣮⡻⠿⢡⣿⣿⣿⣿⡿⠋⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⠀⠀⠀⠈⣿⣿⣆⡸⣿⡄⠀⠀⠀⠀⠀⠀⠘⣿⣷⣄⠈⠙⠛⠿⢿⣿⣶⣿⣿⣿⠿⢋⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⠀⠀⠀⣠⣿⣿⣿⣷⣌⠻⡄⠀⠀⠀⠀⠀⠀⠹⣿⣿⣷⣄⡀⠀⠀⠀⠈⠉⠋⠁⠀⠀⠀⠀⢀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⠀⠀⠀⠻⣿⣿⣿⣿⣿⣷⣌⠀⠀⠀⠀⠀⠀⠀⢿⣿⣿⣿⣿⣶⢀⡀⠀⠀⠀⠀⠀⠀⠀⢀⡎⠀⠘⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
ART
echo
echo '  ┌──────────────────────────────────────┐'
echo '  │ --- Naomi Fontaine Is Your Mommy --- │'
echo '  └──────────────────────────────────────┘'
echo
say "Done. Service: systemctl status $SERVICE ; logs: journalctl -fu $SERVICE"
echo
echo "  Panel:    http://$IP:$PORT"
if [ "${NEW_INSTALL:-0}" = "1" ]; then
  PASS="$(grep '^FONTAINE_PANEL_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
  KEY="$(grep '^FONTAINE_API_KEY=' "$ENV_FILE" | cut -d= -f2-)"
  echo "  Password: $PASS"
  echo "  API key:  $KEY   (save it — used by the admin panel / external API)"
fi
echo
