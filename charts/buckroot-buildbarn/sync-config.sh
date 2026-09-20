#!/usr/bin/env bash
# Copy the Buildbarn jsonnet from the toolkit (the single source, also used by docker compose) into the chart.
# env.libsonnet and gen/ are NOT copied: the chart renders them from values.yaml.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="$here/../../toolkit/infra/buildbarn/config"
dst="$here/files/config"
mkdir -p "$dst"
rm -f "$dst"/*.jsonnet "$dst"/*.libsonnet
for f in "$src"/*.jsonnet "$src"/common.libsonnet; do cp "$f" "$dst/"; done
echo "synced $(ls "$dst" | wc -l) files into $dst"
