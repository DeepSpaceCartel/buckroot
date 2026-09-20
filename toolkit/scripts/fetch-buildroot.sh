#!/usr/bin/env bash
# Clone the Buildroot tree named in project.json (buildroot.repo / buildroot.ref) into
# buildroot-src/ and record what was fetched. Idempotent.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
read -r REPO REF < <(python3 -c "
import json,sys
b=json.load(open('$HERE/project.json'))['buildroot']
print(b['repo'], b['ref'])")
DEST="$HERE/buildroot-src"

if [ -d "$DEST/.git" ]; then
  echo "buildroot-src already present at $DEST ($(git -C "$DEST" describe --tags 2>/dev/null || git -C "$DEST" rev-parse --short HEAD))"
else
  git clone --branch "$REF" --depth 1 "$REPO" "$DEST"
  git -C "$DEST" rev-parse HEAD > "$HERE/BUILDROOT_PINNED_COMMIT.txt"
  echo "$REF" > "$HERE/BUILDROOT_PINNED_VERSION.txt"
  echo "Fetched $REPO $REF ($(cat "$HERE/BUILDROOT_PINNED_COMMIT.txt")) into $DEST"
fi

# The project's BR2_EXTERNAL tree, when it lives in its own repository (pinned to a commit).
read -r EXT_URL EXT_COMMIT < <(python3 -c "
import json
e=json.load(open('$HERE/project.json')).get('external_repo') or {}
print(e.get('url',''), e.get('commit',''))")
if [ -n "$EXT_URL" ] && [ ! -d "$HERE/buildroot-external/.git" ]; then
  rm -rf "$HERE/buildroot-external"
  git clone "$EXT_URL" "$HERE/buildroot-external"
  git -C "$HERE/buildroot-external" checkout -q "$EXT_COMMIT"
  echo "Fetched external tree $EXT_URL @ $EXT_COMMIT"
fi
