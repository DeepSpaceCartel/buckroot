#!/usr/bin/env bash
# Run a command with Buildroot's inputs at FIXED absolute paths, in a private
# mount namespace (nothing leaks to the host):
#
#   /mnt/src       buildroot-src            (read-only)
#   /mnt/external  buildroot-external       (read-only)
#   /mnt/common    common/                  (read-only; hello's HELLO_SITE is ../common/hello)
#   /mnt/dl        download dir             (read-write)
#   /mnt/out       Buildroot output dir     (read-write)
#
# Why: Buildroot bakes absolute build paths into the rootfs itself (e.g.
# /usr/lib/libstdc++.so.6.0.32-gdb.py, /bin/busybox), so two builds at different
# paths produce different filesystems. Fixing the paths makes the result
# independent of where the repo is checked out. Read-only sources also turn any
# write into the source tree into a loud error.
#
# Views: BR2_NS_SRC_VIEW / BR2_NS_EXT_VIEW / BR2_NS_COMMON_VIEW = FILE, one path per
# line relative to that tree (optionally `entry<TAB>real path` to bind an overlay instead). When set, the tree at /mnt/<x> contains ONLY those
# entries (each bind-mounted read-only, files or directories) instead of everything.
# This is how an action's declared inputs are ENFORCED: Buck2 runs local actions
# unsandboxed, so without a view the action could silently read undeclared files;
# with one, an undeclared read is ENOENT. For the external tree the view also gets
# an empty stub Config.in (support/scripts/br2-external insists on the file; Kconfig
# never runs in a view).
#
# .git is always hidden, in both trees (an empty directory is mounted over it): Buildroot asks git for
# BR2_VERSION_FULL ("-dirty" depends on the state of the worktree) and for
# SOURCE_DATE_EPOCH (the commit date). Without git both fall back to fixed values from
# the Makefile, so the result no longer depends on git or on which files a view shows.
#
# Usage: [BR2_NS_NET=off] br2-ns.sh OUT_DIR DL_DIR -- command [args...]
# Needs CAP_SYS_ADMIN (root in this devcontainer); `unshare -Urm` may work otherwise.
set -euo pipefail

# BR2_NS_HERE = the project root. Buck2 runs this script from its declared artifact under
# buck-out (locally and on remote workers), where "one directory up" is not the root.
HERE="${BR2_NS_HERE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
OUT="$(mkdir -p "$1" && cd "$1" && pwd)"
DL="$(mkdir -p "$2" && cd "$2" && pwd)"
[ "$3" = "--" ] || { echo "usage: $0 OUT_DIR DL_DIR -- command..." >&2; exit 2; }
shift 3

# View files are read inside the namespace, so make them absolute here.
for v in BR2_NS_SRC_VIEW BR2_NS_EXT_VIEW BR2_NS_COMMON_VIEW; do
  if [ -n "${!v:-}" ]; then
    export "$v=$(cd "$(dirname "${!v}")" && pwd)/$(basename "${!v}")"
  fi
done

export BR2_NS_HERE="$HERE" BR2_NS_OUT="$OUT" BR2_NS_DL="$DL"
# BR2_NS_NET=off also cuts the network (loopback only): every source must then come
# from the declared download dir, so an undeclared download fails loudly.
NETFLAG=()
[ "${BR2_NS_NET:-on}" = "off" ] && NETFLAG=(--net)
exec unshare --mount --propagation private "${NETFLAG[@]}" bash -c '
  set -euo pipefail
  mount -t tmpfs -o size=4m none /mnt
  mkdir /mnt/src /mnt/external /mnt/common /mnt/dl /mnt/out

  bind_ro() {                                   # bind_ro REAL MOUNTPOINT
    [ -e "$1" ] || return 0                     # e.g. common/ is not an input of every action
    mount --bind "$1" "$2"
    mount -o remount,bind,ro "$2"
  }
  build_view() {                                # build_view REAL_ROOT MOUNT VIEW_FILE
    local root="$1" mp="$2" list="$3" e src real
    while IFS=$(printf "\t") read -r e src || [ -n "$e" ]; do
      [ -n "$e" ] || continue
      real="${src:-$root/$e}"                   # `entry<TAB>path`: an overlay made by the caller
      if [ ! -e "$real" ]; then                 # a declared entry that is not there: fail, never mount an empty stand-in
        echo "br2-ns: view entry missing: $e (expected at $real)" >&2
        exit 97
      fi
      if [ -d "$real" ]; then
        mkdir -p "$mp/$e"
      else
        mkdir -p "$(dirname "$mp/$e")"
        : > "$mp/$e"                            # file mountpoint
      fi
      bind_ro "$real" "$mp/$e"
    done < "$list"
  }

  if [ -n "${BR2_NS_SRC_VIEW:-}" ]; then
    build_view "$BR2_NS_HERE/buildroot-src" /mnt/src "$BR2_NS_SRC_VIEW"
  else
    bind_ro "$BR2_NS_HERE/buildroot-src" /mnt/src
    if [ -d /mnt/src/.git ]; then
      mkdir /mnt/no-git
      bind_ro /mnt/no-git /mnt/src/.git
    fi
  fi
  if [ -n "${BR2_NS_EXT_VIEW:-}" ]; then
    build_view "$BR2_NS_HERE/buildroot-external" /mnt/external "$BR2_NS_EXT_VIEW"
    : > /mnt/external/Config.in
  else
    bind_ro "$BR2_NS_HERE/buildroot-external" /mnt/external
    if [ -d /mnt/external/.git ]; then         # BR2_EXTERNAL_<NAME>_VERSION comes from git describe
      mkdir -p /mnt/no-git-ext
      bind_ro /mnt/no-git-ext /mnt/external/.git
    fi
  fi
  # common/ holds local package sources. BR2_NS_COMMON_ROOT points at a directory the caller
  # assembled from the DECLARED source artifacts of the action (in a remote input root they are
  # not at common/ but under buck-out); the default is the checkout.
  COMMON_REAL="${BR2_NS_COMMON_ROOT:-$BR2_NS_HERE/common}"
  if [ -n "${BR2_NS_COMMON_VIEW:-}" ]; then
    build_view "$COMMON_REAL" /mnt/common "$BR2_NS_COMMON_VIEW"
  else
    bind_ro "$COMMON_REAL" /mnt/common
  fi
  mount --bind "$BR2_NS_DL" /mnt/dl
  mount --bind "$BR2_NS_OUT" /mnt/out
  # Old Buildroot trees (2021 and earlier) recurse so deeply in GNU make 4.3 (`printvars`, `show-info`) that
  # the default 8 MiB stack overflows and make dies with SIGSEGV; a 1 GiB limit avoids it.
  ulimit -s 1048576 2>/dev/null || true
  # Buildroot builds run as root here (namespace, container); old host-tar/host-m4 refuse to configure as root.
  export FORCE_UNSAFE_CONFIGURE=1
  exec "$@"
' br2-ns "$@"
