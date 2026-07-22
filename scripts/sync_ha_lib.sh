#!/usr/bin/env bash
# Sync the repo-root maison_protegee package into the HA integration lib/.
# Run after editing the client or regenerating protobuf stubs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${ROOT}/maison_protegee"
DEST="${ROOT}/custom_components/maison_protegee/lib/maison_protegee"

if [[ ! -f "${SRC}/client.py" ]]; then
  echo "error: missing ${SRC}/client.py" >&2
  exit 1
fi

mkdir -p "$(dirname "${DEST}")"
rsync -a --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'proto/' \
  "${SRC}/" "${DEST}/"

echo "Synced ${SRC} → ${DEST}"
