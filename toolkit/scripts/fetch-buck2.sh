#!/usr/bin/env bash
# Install the pinned Buck2 release as tools/buck2 (gitignored), downloading it once into the
# shared cache ~/.cache/br2/tools so that every experiment reuses the same binary.
# Idempotent: no-ops if tools/buck2 already exists. The download is verified
# against the sha256 published by GitHub for this exact release asset.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${BUCK2_VERSION:-2026-09-15}"
DEST="$HERE/tools/buck2"
SHARED="${BR2_CACHE:-$HOME/.cache/br2}/tools/buck2-$VERSION"

if [ -x "$DEST" ]; then
  echo "buck2 already present: $("$DEST" --version 2>/dev/null | head -1)"
  exit 0
fi

if [ -x "$SHARED" ]; then
  mkdir -p "$HERE/tools" && cp -f "$SHARED" "$DEST"
  echo "buck2 $VERSION installed from $SHARED"
  exit 0
fi

if [ "$VERSION" != "2026-09-15" ]; then
  echo "no pinned checksums for BUCK2_VERSION=$VERSION; add them to this script" >&2
  exit 1
fi

case "$(uname -m)" in
  x86_64)  ASSET="buck2-x86_64-unknown-linux-musl.zst"
           SHA256="631eb84a8925d19146e0f5d594b9f2d0b1f0864e63f24e0d5914a75a6a0a4dea" ;;
  aarch64) ASSET="buck2-aarch64-unknown-linux-musl.zst"
           SHA256="d416933520ffdcd05303c0dd22ec368047fb64e8781b5ad10485f584a6fbc694" ;;
  *) echo "unsupported host arch: $(uname -m)" >&2; exit 1 ;;
esac

mkdir -p "$HERE/tools" "$(dirname "$SHARED")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

curl -fsSL -o "$TMP/$ASSET" \
  "https://github.com/facebook/buck2/releases/download/$VERSION/$ASSET"
echo "$SHA256  $TMP/$ASSET" | sha256sum -c -

zstd -d -q "$TMP/$ASSET" -o "$SHARED"
chmod +x "$SHARED"
cp -f "$SHARED" "$DEST"
echo "Fetched buck2 $VERSION into $DEST: $("$DEST" --version | head -1)"
