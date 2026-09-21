#!/bin/bash
# Buck2 rejects a source path with a backslash ("Relative path contains a backslash"), and systemd names a mount unit for
# /etc/modules-load.d with an escaped dash: etc-modules\x2dload.d.mount. The two such files in the overlay are renamed here (_BS_
# for the backslash) and 0002 restores the exact names in post-build.sh, before anything looks at them, so the image is unchanged.
set -euo pipefail
find rootfs-overlay -name '*\\*' | while IFS= read -r f; do
  mv -- "$f" "$(dirname -- "$f")/$(basename -- "$f" | sed 's/\\/_BS_/g')"
done
