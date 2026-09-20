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
| the four remote cells (wrapped and native, remote and remote-cache), rerun with all fixes | in progress; the toolkit differs from the local cells (see the ADR) |

The first comparison of the Buck2 rootfs with the golden showed 40+ differences, all binaries
and libraries larger than the golden's: the cross `strip` was missing from the rootfs
action's host tree. [Verification](../concepts/verification.md#what-the-manifest-caught)
describes the cause. The first native cell also failed, in `host-gcc-final` (`cannot find crti.o`): the native skeleton
recipes hard-coded the musl toolchain tuple of `helloworld`, so on this glibc project glibc installed its
libraries into a real `usr/lib64`. The tuple now comes from Buildroot
([Wrapped and native](../concepts/wrapped-and-native.md#the-artifact-format-is-an-interface)); after the fix the
native local cell passes. The table will be filled in when the remaining cells complete. The first
cell's time (110 min) includes about ten minutes of overlap with source downloads for another project.

### The three OpenSSH differences

The wrapped remote cells (worker image without `xauth`) built all 199 actions and differed from the golden in exactly three files:
`/usr/bin/ssh`, `/usr/sbin/sshd` and `/usr/libexec/ssh-keysign` (same size, different hash, the same hashes in both remote runs). OpenSSH's `configure`
searches the build machine for `xauth` and embeds the path it finds (`/usr/bin/xauth`); the golden build and every local cell ran where that file exists, the worker
image had none. Only the three binaries that contain the string differ (`ssh-add` and `ssh-keygen` do not). After adding `xauth` to the image, the native remote cell,
which builds the same OpenSSH, is IDENTICAL. Background: [ADR-0013](../decisions/0013-worker-image-is-the-tool-baseline.md) and the
[design note](../design/worker-environment-in-the-key.md).
