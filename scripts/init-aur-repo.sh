#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[aur-init] %s\n' "$1"
}

if [[ $# -lt 2 ]]; then
  printf 'usage: %s <ssh-key-file> <target-dir>\n' "$(basename "$0")" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEY_FILE="$1"
TARGET_DIR="$2"
PKGNAME="attackshark-battery-bridge"
AUR_URL="ssh://aur@aur.archlinux.org/${PKGNAME}.git"

if [[ ! -f "$KEY_FILE" ]]; then
  log "ssh key file not found: $KEY_FILE"
  exit 1
fi

if [[ -e "$TARGET_DIR" && -n "$(find "$TARGET_DIR" -mindepth 1 -maxdepth 1 2>/dev/null)" ]]; then
  log "target directory is not empty: $TARGET_DIR"
  exit 1
fi

mkdir -p "$TARGET_DIR"

log "cloning $AUR_URL into $TARGET_DIR"
GIT_SSH_COMMAND="ssh -i \"$KEY_FILE\" -o IdentitiesOnly=yes" git clone "$AUR_URL" "$TARGET_DIR"

log "copying initial package files"
install -m644 "$ROOT_DIR/packaging/aur/PKGBUILD" "$TARGET_DIR/PKGBUILD"
install -m644 "$ROOT_DIR/packaging/aur/.SRCINFO" "$TARGET_DIR/.SRCINFO"
install -m644 "$ROOT_DIR/packaging/aur/attackshark-battery-bridge.install" \
  "$TARGET_DIR/attackshark-battery-bridge.install"

log "repository initialized in $TARGET_DIR"
log "next steps:"
log "  cd $TARGET_DIR"
log "  git add PKGBUILD .SRCINFO attackshark-battery-bridge.install"
log "  git commit -m 'Initial import'"
log "  GIT_SSH_COMMAND='ssh -i $KEY_FILE -o IdentitiesOnly=yes' git push origin HEAD"
