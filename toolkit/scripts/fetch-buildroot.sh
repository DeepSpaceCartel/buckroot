#!/usr/bin/env bash
# Clone the Buildroot tree named in project.json (buildroot.repo, and buildroot.ref or buildroot.commit)
# into buildroot-src/ and record what was fetched. Idempotent.
#
#   "buildroot": {"repo": URL, "ref": "2024.05.3"}            a tag or branch
#   "buildroot": {"repo": URL, "ref": "2021.02", "commit": H}  an exact commit (a vendor fork's submodule pin)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
read -r REPO REF COMMIT < <(python3 -c "
import json
b=json.load(open('$HERE/project.json'))['buildroot']
print(b['repo'], b['ref'], b.get('commit', '-'))")
DEST="$HERE/buildroot-src"

if [ -d "$DEST/.git" ]; then
  echo "buildroot-src already present at $DEST ($(git -C "$DEST" describe --tags 2>/dev/null || git -C "$DEST" rev-parse --short HEAD))"
else
  if [ "$COMMIT" = "-" ]; then
    git clone --branch "$REF" --depth 1 "$REPO" "$DEST"
  else
    git init -q "$DEST"
    git -C "$DEST" remote add origin "$REPO"
    git -C "$DEST" fetch -q --depth 1 origin "$COMMIT"
    git -C "$DEST" checkout -q FETCH_HEAD
  fi
  git -C "$DEST" rev-parse HEAD > "$HERE/BUILDROOT_PINNED_COMMIT.txt"
  echo "$REF" > "$HERE/BUILDROOT_PINNED_VERSION.txt"
  echo "Fetched $REPO $REF ($(cat "$HERE/BUILDROOT_PINNED_COMMIT.txt")) into $DEST"
fi

# The project's BR2_EXTERNAL tree, when it lives in its own repository (pinned to a commit), either
# at the repository root or in a subdirectory ("subdir"), as in a monorepo with several external trees.
read -r EXT_URL EXT_COMMIT EXT_SUBDIR < <(python3 -c "
import json
e=json.load(open('$HERE/project.json')).get('external_repo') or {}
print(e.get('url','') or '-', e.get('commit','') or '-', e.get('subdir','') or '-')")
if [ "$EXT_URL" != "-" ] && [ ! -e "$HERE/buildroot-external/external.desc" ]; then
  rm -rf "$HERE/buildroot-external"
  if [ "$EXT_SUBDIR" = "-" ]; then
    git clone "$EXT_URL" "$HERE/buildroot-external"
    git -C "$HERE/buildroot-external" checkout -q "$EXT_COMMIT"
  else
    TMP="$(mktemp -d)"
    git clone -q "$EXT_URL" "$TMP/repo"
    git -C "$TMP/repo" checkout -q "$EXT_COMMIT"
    mkdir -p "$HERE/buildroot-external"
    cp -a "$TMP/repo/$EXT_SUBDIR/." "$HERE/buildroot-external/"
    echo "$EXT_COMMIT $EXT_SUBDIR" > "$HERE/EXTERNAL_PINNED_COMMIT.txt"
    rm -rf "$TMP"
  fi
  echo "Fetched external tree $EXT_URL @ $EXT_COMMIT"
fi
