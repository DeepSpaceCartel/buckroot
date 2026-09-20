<title>The br2 CLI</title>

# The br2 CLI

`scripts/br2` drives everything from an experiment directory (one with a `project.json`).
It is vendored there by `toolkit/bin/br2-sync`.

## Commands

| Command | What it does |
|---|---|
| `br2 setup` | install the pinned `buck2` (into `tools/`) and fetch the Buildroot and external trees named in `project.json` |
| `br2 extract` | defconfig to `golden/model.json`, then render the `BUCK` files |
| `br2 fetch` | download sources Buck2's `http_file` cannot express and vendor them |
| `br2 preflight [--pkg P ...]` | extract and patch every package in its view; compare applied patches with the golden |
| `br2 golden [--vanilla]` | plain `make` reference build; writes `golden/rootfs.manifest.json` and `results/golden.json` |
| `br2 dev [--pkg P] [--target L] [--variant V] [--mode M] [--strict]` | iteration loop; see [Iterating fast](../guides/fast-iteration.md) |
| `br2 viewcheck [--mode M]` | build every package's `[viewcheck]`: enter each view with that action's declared inputs and run nothing. `--mode remote` runs it on the worker and finds entries that only work locally |
| `br2 build --variant V --mode M` | one clean, timed, manifest-checked Buck2 build of `//:rootfs`; prints JSON |
| `br2 matrix [--variants ...] [--modes ...]` | every variant and mode; writes `results/matrix.{json,md}` |

Variants: `wrapped`, `native`. Modes: `local`, `local-cache`, `remote`, `remote-cache`. The
two cache modes run twice, cold and warm.

## Other tools

| Script | Purpose |
|---|---|
| `scripts/fs-manifest.py scan IMAGE [-o OUT]` | reduce an ext4, squashfs or tar image to a manifest |
| `scripts/fs-manifest.py diff A B [--ignore PATH ...]` | compare two manifests |
| `scripts/compare-pkg.py WRAPPED.tar NATIVE.tar` | check a native package artifact against the wrapped one |
| `scripts/check-narrow.py [--pkg P ...] [--jobs N] [--golden DIR] [--apply]` | soundness check of views and slices; propose `extra_view` entries |
| `scripts/show-inputs.py PKG [--files] [--config]` | what a package action can see |
| `scripts/deps-graph.py [--full]` | a readable package dependency graph (Graphviz DOT) from `buck2 uquery` |
| `scripts/br2buck.py {extract,fetch,render [--check]}` | the generator behind `br2 extract` and `br2 fetch` |
| `toolkit/bin/br2-sync DIR` | vendor the toolkit into an experiment |
| `toolkit/bin/br2-new NAME --like DIR [--fragment LINE ...] [--drop-heavy]` | create a variant experiment (a lite config) |

## Environment

| Variable | Default | Effect |
|---|---|---|
| `BR2_CACHE` | `~/.cache/br2` | where Buildroot output trees and the golden build live |
| `BR2_WORK_DIR` | `/var/tmp/buckroot-work` | scratch directories of running actions |
| `BR2_KEEP_WORK` | unset | keep an action's scratch directory (and its `make.log`) after it ends |
| `BB_VOLUMES` | `/var/lib/buckroot-buildbarn` | Buildbarn state |

## Exit behaviour

`br2 dev` exits with Buck2's exit code and prints `OK` or `FAILED` with the target and
the elapsed time, then, for every failed action, the last lines of its output.
`br2 build` and `br2 matrix` print JSON and Markdown results; a manifest difference is
reported in the result (`"manifest": [...]`), not as a failed exit.
