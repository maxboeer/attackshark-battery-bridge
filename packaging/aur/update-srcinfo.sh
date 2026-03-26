#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

makepkg --printsrcinfo > .SRCINFO
printf '[aur] wrote %s/.SRCINFO\n' "$ROOT_DIR"
