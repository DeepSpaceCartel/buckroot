<title>Results</title>

# Results

Every project is measured the same way: the *golden* build with plain `make`, then Buck2 in
two variants (`wrapped`, `native`) and four modes (`local`, `local-cache`, `remote`,
`remote-cache`). Each cell starts from `buck2 kill` and `buck2 clean`, uses its own
[cache salt](../decisions/0010-cache-salt-per-cell.md) so a cold run really is cold, runs
strict, and compares the resulting root filesystem manifest with the golden's. The cache
modes run twice: cold, then warm after a clean.

Hardware for all numbers below: 4 cores, 7.9 GB RAM, the Buildbarn worker on the same
machine, so "remote" adds no hardware.

## helloworld

Buildroot 2025.02.18, aarch64, musl, Bootlin external toolchain, one local package
(`hello`). 29 packages, 61 Buck2 actions. `native` builds the 12 packages listed in
`project.json` with Buck2 actions: `hello`, its nine dependencies, and `initscripts` and `urandom-scripts` (56 actions in total).

| variant | mode | run | ok | seconds | commands | cached | remote | local | manifest |
|---|---|---|---|---|---|---|---|---|---|
| wrapped | local | cold | yes | 338.0 | 61 | 0 | 0 | 61 | IDENTICAL |
| wrapped | local-cache | cold | yes | 363.8 | 61 | 0 | 0 | 61 | IDENTICAL |
| wrapped | local-cache | warm | yes | 8.5 | 61 | 61 | 0 | 0 | IDENTICAL |
| wrapped | remote | cold | yes | 363.4 | 61 | 0 | 61 | 0 | IDENTICAL |
| wrapped | remote-cache | cold | yes | 416.8 | 61 | 0 | 61 | 0 | IDENTICAL |
| wrapped | remote-cache | warm | yes | 9.0 | 61 | 61 | 0 | 0 | IDENTICAL |
| native | local | cold | yes | 346.0 | 56 | 0 | 0 | 56 | IDENTICAL |
| native | local-cache | cold | yes | 355.2 | 56 | 0 | 0 | 56 | IDENTICAL |
| native | local-cache | warm | yes | 23.2 | 56 | 55 | 0 | 1 | IDENTICAL |
| native | remote | cold | yes | 354.9 | 56 | 0 | 56 | 0 | IDENTICAL |
| native | remote-cache | cold | yes | 317.3 | 56 | 0 | 56 | 0 | IDENTICAL |
| native | remote-cache | warm | yes | 11.9 | 56 | 56 | 0 | 0 | IDENTICAL |

Reading it:

- The build is dominated by compiling upstream tarballs (busybox, e2fsprogs, util-linux),
  which are still `make` in both variants, so `native` saves 4-5 actions of 61 and little
  wall time here.
- A warm cache rebuild of the whole graph takes 8-23 s.
- Remote execution on the same four cores costs about what local does (no extra
  hardware); the cold cache modes cost 5-15 % for uploading results.
- Where native shows its value is incremental: a comment-only edit to `hello.c` is a
  0.7 s rebuild (the object file is identical, so link, package and rootfs are skipped)
  against 41 s for the wrapped path.

Incremental behaviour of the wrapped variant on a 30-package image with four cores:

| Change | Time | Actions that ran |
|---|---|---|
| cold build | 5 min 16 s | everything |
| add an upstream package (`tree`) | 43 s | `tree`, rootfs |
| add an external package with its own source | 40 s | that package, rootfs |
| flip a busybox-only symbol | 81 s | busybox, rootfs |
| flip a global symbol (`BR2_OPTIMIZE_S`) | 5 min 2 s | everything (by design) |

### helloworld on the Kubernetes cluster

The first build on the [cluster](../guides/kubernetes.md) (2026-09-20; one `cpx51` worker, 16 shared vCPU, the Buck2 client on the 4-core
machine through a port-forward), against a golden built **on the cluster** by `br2 golden --k8s` in the worker image itself (181.9 s):

| variant | mode | run | ok | seconds | commands | cached | remote | local | manifest |
|---|---|---|---|---|---|---|---|---|---|
| wrapped | remote-cache | cold | yes | 353.7 | 61 | 0 | 61 | 0 | IDENTICAL |
| wrapped | remote-cache | warm | yes | 17.4 | 61 | 61 | 0 | 0 | IDENTICAL |

The cold time is the same as on the single machine: helloworld's critical path is serial (the toolchain and the few packages that depend on each
other), and a worker's `make -j` inside one action was already the whole small machine. The warm run is slower than the local warm run (17 s
against 9 s) because 61 action results travel over the network instead of a socket. What the cluster changes is not one cell's time; it is
running many cells and many actions at once, which the Car Thing rows below measure.

## superduperbird (Spotify Car Thing)

[`nd-0r/superduperbird-buildroot`](https://github.com/nd-0r/superduperbird-buildroot): a
`BR2_EXTERNAL` tree on Buildroot 2024.05.3 for the Amlogic S905D2 (aarch64, glibc, an
internal Buildroot toolchain, a 4.9 vendor kernel, Mesa, SDL2, Rust host tools). 98
packages and 199 Buck2 actions; the root filesystem is a 79 MB tar.

Deviations from the project's own defconfig, applied to golden and Buck2 alike (see the
project's `notes`): no post-image script (it loop-mounts an image and writes into the
external tree), an older full kernel config that builds at the pinned commit, and the DTS
settings the external tree's hook needs. `/etc/shadow` is compared by presence only: its
sha-256 hash has a random salt on every build.

| Milestone | Status |
|---|---|
| golden build (plain `make`, instrumented config) | done: manifest of 864 entries |
| preflight: patches applied in every view | done |
| Buck2 `wrapped`, local, dev mode | done: 199 actions, manifest **IDENTICAL** (after the strip fix below) |
| Buck2 `native`, local, cold (strict, clean state) | done: 193 actions in 6,629 s (110 min), manifest **IDENTICAL** |
| Buck2 `native`, local-cache | done: cold 7,038 s; warm 268 s with 191 of 193 actions cached; both **IDENTICAL** |
| Buck2 `wrapped`, local, cold | done: 199 actions in 6,354 s (106 min), manifest **IDENTICAL** |
| Buck2 `native`, remote and remote-cache, first attempt | failed in about 100 s: the worker image had no `git` (fixed) |
| Buck2 `wrapped`, remote, first attempt | failed after 33 min: `cc1plus` killed for lack of memory, the worker ran two actions at once (fixed: `concurrency: 1`) |
| Buck2 `wrapped`, local-cache | done: cold 6,091 s; warm 236 s with 197 of 199 actions cached; both **IDENTICAL** |
| Buck2 `wrapped`, remote and remote-cache, fourth attempt (no `xauth` in the worker image) | complete: 199 of 199 actions on the worker; cold 7,982 s and 7,338 s, warm 17 s (199 of 199 cached). Manifest: three OpenSSH binaries differ (see below) |
| Buck2 `native`, remote, with `xauth` added to the worker image | done: 193 actions on the worker in 7,473 s, manifest **IDENTICAL**; confirms the OpenSSH explanation |
| Buck2 `wrapped`, remote, second attempt | failed after 102 min, 184 of 199 actions: `util-linux-libs` (and others with cross-directory links) had no `util-linux.mk` on the worker; fixed by [ADR-0014](../decisions/0014-view-entries-are-declared-inputs.md) |
| the four remote cells on the Kubernetes cluster ([guide](../guides/kubernetes.md)) | done, all **IDENTICAL**: see the table below |

The first comparison of the Buck2 rootfs with the golden showed 40+ differences, all binaries
and libraries larger than the golden's: the cross `strip` was missing from the rootfs
action's host tree. [Verification](../concepts/verification.md#what-the-manifest-caught)
describes the cause. The first native cell also failed, in `host-gcc-final` (`cannot find crti.o`): the native skeleton
recipes hard-coded the musl toolchain tuple of `helloworld`, so on this glibc project glibc installed its
libraries into a real `usr/lib64`. The tuple now comes from Buildroot
([Wrapped and native](../concepts/wrapped-and-native.md#the-artifact-format-is-an-interface)); after the fix the
native local cell passes. The table will be filled in when the remaining cells complete. The first
cell's time (110 min) includes about ten minutes of overlap with source downloads for another project.

### The remote cells on the cluster

The four remote cells, run on 2026-09-21 on the [Kubernetes cluster](../guides/kubernetes.md): the Buck2 client on the 4-core machine,
actions on shared-vCPU `cpx51` workers (16 vCPU, 32 GB; at the time two workers per node, each `make -j7`), the four cells in parallel
on 4 to 7 workers, one worker slot per action. Golden and workers use the same tool baseline image ([ADR-0013](../decisions/0013-worker-image-is-the-tool-baseline.md)),
so the OpenSSH `xauth` difference of the single-machine runs is gone. Results in `results/cluster-remote.json`.

| variant | mode | run | ok | seconds | commands | cached | remote | local | manifest |
|---|---|---|---|---|---|---|---|---|---|
| wrapped | remote | cold | yes | 2101.2 | 199 | 0 | 199 | 0 | IDENTICAL |
| wrapped | remote-cache | cold | yes | 1392.5 | 199 | 0 | 199 | 0 | IDENTICAL |
| wrapped | remote-cache | warm | yes | 25.0 | 199 | 199 | 0 | 0 | IDENTICAL |
| native | remote | cold | yes | 1851.3 | 193 | 0 | 193 | 0 | IDENTICAL |
| native | remote-cache | cold | yes | 2065.6 | 193 | 0 | 193 | 0 | IDENTICAL |
| native | remote-cache | warm | yes | 22.2 | 193 | 193 | 0 | 0 | IDENTICAL |

Compared with the single machine (wrapped remote cold 7,982 s, native remote cold 7,473 s): 3.5 to 4 times faster per cell, and the
cells ran side by side, so the matrix took about 35 minutes instead of 8 hours. The cold times are not comparable with each other in
detail: they shared 4 to 7 worker slots while running, and the wrapped remote-cache cell (1,392 s) ran alone after a rerun, which is
the fairest number for "one cell on the cluster". Its first attempt failed at the last action: a `terraform apply` rolled the frontend
pods mid-build (an operational mistake, now a rule in the guide), not a build defect. The warm runs (25 s and 22 s) are the whole
199- or 193-action graph served from the action cache over the network.

### The three OpenSSH differences

The wrapped remote cells (worker image without `xauth`) built all 199 actions and differed from the golden in exactly three files:
`/usr/bin/ssh`, `/usr/sbin/sshd` and `/usr/libexec/ssh-keysign` (same size, different hash, the same hashes in both remote runs). OpenSSH's `configure`
searches the build machine for `xauth` and embeds the path it finds (`/usr/bin/xauth`); the golden build and every local cell ran where that file exists, the worker
image had none. Only the three binaries that contain the string differ (`ssh-add` and `ssh-keygen` do not). After adding `xauth` to the image, the native remote cell,
which builds the same OpenSSH, is IDENTICAL. Background: [ADR-0013](../decisions/0013-worker-image-is-the-tool-baseline.md) and the
[design note](../design/worker-environment-in-the-key.md).

## What the remote actions used

Measured on 2026-09-21 on the [Kubernetes cluster](../guides/kubernetes.md): every remote action of five projects' matrix runs, read from the
result the Buildbarn worker stores for each action (`scripts/br2-usage.py`; [how to repeat it](../guides/action-resource-usage.md)). Buck2's own
`execution_stats` are empty for remote actions. 2,513 of 2,597 unique actions had a stored result (the missing ones are mostly from the earlier
single-machine run, whose cache no longer exists). Cores are CPU seconds over wall seconds while the action ran; memory is the largest single
process of the action, not the sum over its parallel jobs. Each cell has its own cache salt, so a package built in several cells counts once per cell.

| Project | Actions | Wall h | CPU h | Avg cores | Median | p90 | Largest process |
|---|---|---|---|---|---|---|---|
| bottlerocket-sdk | 346 | 1.22 | 4.77 | 3.90 | 0.98 | 1.72 | 1.33 GiB |
| funkey-os | 441 | 0.85 | 1.62 | 1.91 | 0.97 | 1.49 | 0.41 GiB |
| helloworld | 60 | 0.01 | 0.01 | 0.93 | 0.98 | 1.05 | 0.04 GiB |
| qemu-x86_64 | 684 | 2.16 | 8.39 | 3.89 | 0.97 | 2.02 | 1.33 GiB |
| superduperbird | 982 | 3.81 | 13.11 | 3.44 | 0.97 | 1.81 | 1.21 GiB |
| **All** | **2,513** | **8.04** | **27.89** | **3.47** | | | |

By how long the action ran (all projects):

| Wall time | Actions | Share of wall | Avg cores | p90 cores | Largest process |
|---|---|---|---|---|---|
| under 5 s | 1,633 | 2% | 0.91 | 0.98 | 0.09 GiB |
| 5 to 20 s | 535 | 22% | 1.29 | 2.03 | 0.33 GiB |
| 20 to 60 s | 258 | 30% | 1.91 | 3.31 | 0.23 GiB |
| 60 to 300 s | 79 | 37% | 5.78 | 9.11 | 1.33 GiB |
| over 300 s | 8 | 9% | 5.09 | 5.53 | 1.33 GiB |

- **Two populations.** 96.5% of the actions run under a minute and average one to two cores; the other 87 take 46% of the running time and average
  5 to 6 cores. 75 actions averaged more than the 4.5 cores a worker requests (`host-cmake`, `host-gcc-initial`, `host-gcc-final`, `glibc`).
- **Memory is small.** The largest process anywhere was 1.33 GiB (`host-gcc-initial`, `host-gcc-final`). The busiest worker container over three hours
  peaked at 4.3 GiB (all its processes, `make -j4`) and at 13 cores.
- **Longest action: 350 s.** The compiler chain is long end to end, not in one action.
- **No memory kills on this cluster:** no `OOMKilled` container, no `container_oom_events_total`, no stored action that ended on a signal. Failed
  actions are not cached, so the last check cannot see them. The OOM kills that set `concurrency: 1` were on the single 7.7 GB machine
  ([ADR-0015](../decisions/0015-buildbarn-on-kubernetes.md)).
- **Consequence:** a worker requests 4.5 vCPU and 9 GiB for one action at a time, so three fill a node while the cluster reads 30% CPU and 6% memory
  in use. See [Action sizes and execution platforms](../design/action-sizes.md).

## Status when testing paused (2026-09-21)

The testing phase is **not finished**. Per project, what exists and what does not (a cell counts only when its manifest is IDENTICAL to the golden):

| Project | Golden | Cells done | Open |
|---|---|---|---|
| helloworld | yes | all 8 cells, IDENTICAL | none |
| superduperbird (Car Thing) | yes | all 8 cells, both variants in local, local-cache, remote and remote-cache (cold and warm for the cache modes), every manifest IDENTICAL: see its section above | none |
| bottlerocket-sdk | yes | wrapped remote, remote-cache (cold and warm): IDENTICAL | native cells not re-run after the `STAGING_SUBDIR` fix (a native remote dev build passed, 59 of 59 actions); local and local-cache cells not run |
| qemu-x86_64 | yes | none | remote cells failed on `host-gettext-tiny` (fixed: `extra_view`); `host-libglib2` then fails in the remote action after about 100 s, not an OOM (`oom_kill 0`, peak 0.8 GB of 9 GiB); the cause is not found (the action's log shows only its last 100 lines) |
| funkey-os | rebuilt after the libvorbis patch; differs from the first golden in `libSDL_sound` (expected), `/boot/zImage` and `/etc/shadow` (not explained; no Buck2 cell has compared yet) | none | the local wrapped cell failed in `sdl_sound` (fixed by `patches/buildroot/0002`); the following local-cache dev build failed on `host-lzo`, `lzo`, `host-icu` (`stamp_dir` fix) and `host-gettext-tiny` (`extra_view` fix); neither fix has been re-run; remote cells need the `legacy` pool |
| home-assistant-os | no | none | the golden failed twice at `rtl8821cu` (`--no-print-directory`, [ADR-0018](../decisions/0018-make-runs-with-no-print-directory.md)); the rerun was stopped when the cluster was torn down |

Found on the way, all fixed and committed: native recipes assumed the sysroot directory name (`STAGING_SUBDIR`, [ADR-0012](../decisions/0012-toolchain-tuple-from-buildroot.md)),
`stamp_dir` included a package's SUBDIR on an older Buildroot, the FunKey `libvorbis*.la` files named libvorbis's build directory, `make` printed directories into a
captured `KVER` (ADR-0018). Every action key changed once with ADR-0018, so the caches of earlier runs are gone.

The cluster this ran on was destroyed at the end of the session (`terraform/` recreates it). Two of the measured limits worth knowing: scale-from-zero needs the predeclared
queue, and scale-in needs the drain ([Kubernetes guide](../guides/kubernetes.md#how-autoscaling-works)).
