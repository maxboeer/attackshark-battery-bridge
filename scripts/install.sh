#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[install] %s\n' "$1"
}

BIN_SOURCE="${1:-dist/attackshark-battery-bridge}"
PREFIX="${PREFIX:-/usr/local}"
CONFIG_DIR="${CONFIG_DIR:-/etc/attackshark-battery-bridge}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
SYSTEMCTL_BIN="${SYSTEMCTL_BIN:-systemctl}"
SKIP_SYSTEMD="${SKIP_SYSTEMD:-0}"
BIN_TARGET="$PREFIX/bin/attackshark-battery-bridge"
SERVICE_TARGET="$SYSTEMD_DIR/attackshark-battery-bridge.service"
CONFIG_TARGET="$CONFIG_DIR/config.toml"

if [[ ! -f "$BIN_SOURCE" ]]; then
  log "binary not found: $BIN_SOURCE"
  exit 1
fi

log "installing binary to $BIN_TARGET"
install -Dm755 "$BIN_SOURCE" "$BIN_TARGET"
log "installing service file to $SERVICE_TARGET"
install -Dm644 "systemd/attackshark-battery-bridge.service" "$SERVICE_TARGET"
log "ensuring config directory $CONFIG_DIR exists"
install -d "$CONFIG_DIR"

if [[ ! -f "$CONFIG_TARGET" ]]; then
  log "installing default config to $CONFIG_TARGET"
  install -m644 "packaging/config.example.toml" "$CONFIG_TARGET"
else
  log "keeping existing config at $CONFIG_TARGET"
fi

if [[ "$SKIP_SYSTEMD" == "1" ]]; then
  log "skipping systemd daemon-reload because SKIP_SYSTEMD=1"
else
  log "reloading systemd daemon"
  "$SYSTEMCTL_BIN" daemon-reload
fi

log "installed binary to $BIN_TARGET"
log "installed service to $SERVICE_TARGET"
log "config available at $CONFIG_TARGET"
