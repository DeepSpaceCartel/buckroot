<title>The br2 CLI</title>

# The br2 CLI

`scripts/br2` drives everything from an experiment directory (one with a `project.json`).
It is vendored there by `toolkit/bin/br2-sync`.

## Commands

| Command | What it does |
|---|---|
| `br2 setup [--no-buck2]` | install the pinned `buck2` (into `tools/`) and fetch the Buildroot and external trees named in `project.json` |
| `br2 extract` | defconfig to `golden/model.json`, then render the `BUCK` files |
| `br2 fetch` | download sources Buck2's `http_file` cannot express and vendor them |
| `br2 preflight [--pkg P ...]` | extract and patch every package in its view; compare applied patches with the golden |
| `br2 golden [--vanilla] [--k8s ...]` | plain `make` reference build; writes `golden/rootfs.manifest.json` and `results/golden.json`. `--k8s` runs it as a Kubernetes Job on the cluster, in the workers' own tool-baseline image, and copies the small results back (push first: the Job clones the current commit); options `--namespace`, `--image`, `--cpu`, `--memory`, `--deadline`, `--dl-claim` (the volume that keeps Buildroot's downloads between Jobs, default `golden-dl`), `--dry-run` (print the Job). See [Buildbarn on Kubernetes](../guides/kubernetes.md) |
| `br2 dev [--pkg P] [--target L] [--variant V] [--mode M] [--strict]` | iteration loop; see [Iterating fast](../guides/fast-iteration.md) |
| `br2 viewcheck [--mode M]` | build every package's `[viewcheck]`: enter each view with that action's declared inputs and run nothing. `--mode remote` runs it on the worker and finds entries that only work locally |
| `br2 build --variant V --mode M` | one clean, timed, manifest-checked Buck2 build of `//:rootfs`; prints JSON |
| `br2 matrix [--variants ...] [--modes ...] [--parallel N] [--pool P] [--dry-run]` | every variant and mode; writes `results/matrix.{json,md}`. `--parallel N` runs N cells at once, each in its own Buck2 isolation directory (only meaningful with remote capacity to match; timings of parallel cells are not comparable with a serial run); `--pool P` sends the remote actions to a worker pool (see below); `--dry-run` prints the Buck2 commands and runs nothing |

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
| `BR2_RE_ENDPOINT` | unset (`localhost:8980`) | `grpc://host:port` of a Buildbarn frontend, for engine, action cache and CAS; set it in a Kubernetes workspace to `grpc://frontend.buildbarn.svc.cluster.local:8980`, on a tailnet machine to `grpc://buildbarn.<tailnet>.ts.net:8980` |
| `BR2_JOBS` | unset | Buildroot `PARALLEL_JOBS` inside every wrapped action. Default: the smaller of the CPU count plus one and the memory (cgroup limit included) divided by 2 GiB, because a single `make -jN` of GCC was killed by the OOM killer on a 7.7 GB machine |

## Worker pools

A project whose Buildroot pin predates current host tools names its baseline in `project.json` (`"baseline": "funkey"`): its remote
actions then go to the `legacy` pool and its golden Job runs in that image ([ADR-0017](../decisions/0017-tool-baseline-per-project-era.md)).

`--pool P` (on `br2 build` and `br2 matrix`) prefixes the Buck2 instance name with `P/`. The Buildbarn frontend routes an instance-name prefix to the
scheduler of that pool (`schedulers` in `env.libsonnet`, `pools` in the Helm chart), so `--pool dedicated` runs on the dedicated-CPU workers and the
default runs on the shared ones. The CAS is shared by all pools. See [Buildbarn on Kubernetes](../guides/kubernetes.md).

## Exit behaviour

`br2 dev` exits with Buck2's exit code and prints `OK` or `FAILED` with the target and
the elapsed time, then, for every failed action, the last lines of its output.
`br2 build` and `br2 matrix` print JSON and Markdown results; a manifest difference is
reported in the result (`"manifest": [...]`), not as a failed exit.
