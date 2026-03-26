#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[uninstall] %s\n' "$1"
}

PREFIX="${PREFIX:-/usr/local}"
CONFIG_DIR="${CONFIG_DIR:-/etc/attackshark-battery-bridge}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
SYSTEMCTL_BIN="${SYSTEMCTL_BIN:-systemctl}"
SKIP_SYSTEMD="${SKIP_SYSTEMD:-0}"
BIN_TARGET="$PREFIX/bin/attackshark-battery-bridge"
SERVICE_TARGET="$SYSTEMD_DIR/attackshark-battery-bridge.service"

if [[ "$SKIP_SYSTEMD" == "1" ]]; then
  log "skipping systemd disable and daemon-reload because SKIP_SYSTEMD=1"
else
  log "stopping and disabling attackshark-battery-bridge.service if present"
  "$SYSTEMCTL_BIN" disable --now attackshark-battery-bridge.service 2>/dev/null || true
fi

log "removing $BIN_TARGET"
rm -f "$BIN_TARGET"
log "removing $SERVICE_TARGET"
rm -f "$SERVICE_TARGET"

if [[ "$SKIP_SYSTEMD" == "1" ]]; then
  :
else
  log "reloading systemd daemon"
  "$SYSTEMCTL_BIN" daemon-reload
fi

log "removed $BIN_TARGET"
log "removed $SERVICE_TARGET"
log "configuration in $CONFIG_DIR was left intact"
