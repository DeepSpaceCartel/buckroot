#!/usr/bin/env bash
# Build a Tier 0 Buildroot baseline (defconfig + full build).
#
# Env (all optional):
#   DEFCONFIG  defconfig name (default: the full one with kernel + QEMU)
#   O          out-of-tree output dir (default: buildroot-src/output)
#   JOBS       parallel jobs (default: 4). Never let a stray -j reach a package
#              build with a value you did not mean: Buildroot skips its own
#              -j$(nproc+1) whenever any -j is already in MAKEFLAGS.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTERNAL="$HERE/buildroot-external"
SRC="$HERE/buildroot-src"
DEFCONFIG="${DEFCONFIG:-helloworld_qemu_aarch64_musl_defconfig}"
JOBS="${JOBS:-4}"

if [ ! -d "$SRC/.git" ]; then
  echo "buildroot-src not found; run scripts/fetch-buildroot.sh first" >&2
  exit 1
fi

cd "$SRC"
make ${O:+O="$O"} BR2_EXTERNAL="$EXTERNAL" "$DEFCONFIG"
make ${O:+O="$O"} -j"$JOBS"
