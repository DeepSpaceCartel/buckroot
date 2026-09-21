#!/usr/bin/env bash
# Plain `make` (vanilla Buildroot, no Buck2) at the canonical fixed paths (see br2-ns.sh). Its
# rootfs.ext4 is what golden/rootfs.manifest.json is taken from, and what Buck2 must reproduce.
#
# Env: OUT (default ~/.cache/br2/<name>/golden), JOBS (default: all cores),
#      GOLDEN_FRAGMENT=1 appends the instrumentation's config fragment (see br2project.py).
# Output lives OUTSIDE the project: Buildroot trees hold tens of thousands of directories and
# would exhaust the OS file-watch limit for Buck2.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
eval "$(python3 - "$HERE" <<'PY'
import json, os, shlex, sys
c = json.load(open(os.path.join(sys.argv[1], "project.json")))
frag = ["BR2_PER_PACKAGE_DIRECTORIES=y", "BR2_REPRODUCIBLE=y"] + c.get("config_fragment", [])
for k, v in (("NAME", c["name"]), ("DEFCONFIG", c["defconfig"]), ("EXTERNAL", "1" if c.get("external", True) else ""),
             ("FRAGMENT", "\n".join(frag))):
    print(f"{k}={shlex.quote(v)}")     # quoted: fragment lines contain $(BR2_...) which the shell must not expand
PY
)"
OUT="${OUT:-${BR2_CACHE:-$HOME/.cache/br2}/$NAME/golden}"
export JOBS="${JOBS:-$(nproc)}"
export MAKE_ARGS="${MAKE_ARGS:-}"       # e.g. -k: keep going, to see every failing package in one run (diagnosis only)
export DEFCONFIG EXTERNAL
export FRAGMENT="${GOLDEN_FRAGMENT:+$FRAGMENT}"     # only for the instrumented golden build

exec "$HERE/scripts/br2-ns.sh" "$OUT" "$HERE/buildroot-src/dl" -- bash -c '
  set -euo pipefail
  MK="make -C /mnt/src O=/mnt/out BR2_DL_DIR=/mnt/dl ${EXTERNAL:+BR2_EXTERNAL=/mnt/external}"
  $MK "$DEFCONFIG"
  if [ -n "$FRAGMENT" ]; then printf "%s\n" "$FRAGMENT" >> /mnt/out/.config; $MK olddefconfig; fi
  $MK -j"$JOBS" $MAKE_ARGS
'
