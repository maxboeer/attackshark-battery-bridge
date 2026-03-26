#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

printf '[build] using root %s\n' "$ROOT_DIR"
printf '[build] starting PyInstaller onefile build\n'

"$ROOT_DIR/.venv/bin/python" -m PyInstaller \
  --noconfirm \
  --clean \
  --onefile \
  --name attackshark-battery-bridge \
  --paths "$ROOT_DIR/src" \
  --add-data "$ROOT_DIR/src/attackshark_battery_bridge/profiles:attackshark_battery_bridge/profiles" \
  "$ROOT_DIR/src/attackshark_battery_bridge/__main__.py"

printf '[build] finished: %s\n' "$ROOT_DIR/dist/attackshark-battery-bridge"
