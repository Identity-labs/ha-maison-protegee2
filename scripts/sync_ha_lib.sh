#!/usr/bin/env bash
# Sync ha-maison-protegee2-api into the HA integration lib/.
# Until the API package is published on PyPI, HACS installs this vendored copy.
#
# Override the source with MAISON_PROTEGEE_API_SRC=/path/to/maison_protegee
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${ROOT}/custom_components/maison_protegee/lib/maison_protegee"
SIBLING="${ROOT}/../ha-maison-protegee2-api/src/maison_protegee"

if [[ -n "${MAISON_PROTEGEE_API_SRC:-}" ]]; then
  SRC="${MAISON_PROTEGEE_API_SRC}"
elif [[ -f "${SIBLING}/client.py" ]]; then
  SRC="${SIBLING}"
else
  SRC="$(python3 -c 'import maison_protegee, pathlib; print(pathlib.Path(maison_protegee.__file__).resolve().parent)' 2>/dev/null || true)"
fi

if [[ -z "${SRC}" || ! -f "${SRC}/client.py" ]]; then
  echo "error: maison_protegee client not found." >&2
  echo "Clone https://github.com/Identity-labs/ha-maison-protegee2-api next to this repo," >&2
  echo "or pip install -e ../ha-maison-protegee2-api, or set MAISON_PROTEGEE_API_SRC." >&2
  exit 1
fi

mkdir -p "$(dirname "${DEST}")"
rsync -a --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'proto/' \
  "${SRC}/" "${DEST}/"

echo "Synced ${SRC} → ${DEST}"
