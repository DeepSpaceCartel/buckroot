<title>Debugging a failing package</title>

# Debugging a failing package

An action fails, or the build passes and the manifest differs. Find out why.

## Read the failure

`br2 dev` prints every failed action with the tail of its output. The whole log of an
action is in Buck2:

```bash
tools/buck2 log what-failed
tools/buck2 log what-ran --show-std-err | less
```

## Watch a long action while it runs

The wrapped actions work in a scratch directory. While `make <pkg>` runs, its log is
being written to `make.log` in it:

```bash
ls -dt /var/tmp/buckroot-work/br2-* | head
tail -f /var/tmp/buckroot-work/br2-host-cmake-*/make.log
```

The base directory is `BR2_WORK_DIR` (default `/var/tmp/buckroot-work`). It is deleted
when the action ends; to keep it, and the whole Buildroot output tree with it, set
`BR2_KEEP_WORK=1` in the environment of the run.

## Re-run one action by hand

Every action is `python3 br2/pkg_action.py <mode> --spec SPEC --out OUT`, and the spec
is a JSON file Buck2 wrote:

```bash
SPEC=$(ls -t buck-out/v2/art/root/br2/generated/__rootfs__/*/rootfs.spec.json | head -1)
BR2_KEEP_WORK=1 python3 br2/pkg_action.py rootfs --spec "$SPEC" --out /tmp/rootfs.tar
```

This runs exactly what the action ran, with a work directory you can go and look at.
It is how a missing cross `strip` was found (every binary in the image was larger than
in the golden): `out/host/bin/` lacked the cross tools because the rootfs action had merged only some of
the packages' host trees.

## Failure catalogue

| Symptom | Likely cause | Where to go |
|---|---|---|
| `No rule to make target 'package/x/x.mk'` | a package outside this one's dependency closure | [`extra_view`](../reference/project-json.md#extra_view) |
| Patches missing, build fails late | a patch directory outside the view (a group directory such as `package/gcc/`) | `br2 preflight`, then `extra_view` |
| `Killed` / OOM | two heavy actions at once | [`heavy`](fast-iteration.md#keep-a-heavy-package-from-taking-the-machine) |
| `Kconfig` / `syncconfig` error inside a package action | a symbol's slice lacked a `PROVIDES`/`HAS` option | `scripts/show-inputs.py PKG --config` |
| `hash file` / download errors | a dead URL or a SHA-512-only hash | [`br2 fetch`](adding-a-project.md#5-fetch-sources-buck2-cannot-download) |
| Build passes, a lot of files differ in size | the strip step did not run, or a config the golden had | compare with `br2 golden` |
| Same digest, different results across machines | an ambient host tool that differs | [Wrapped and native](../concepts/wrapped-and-native.md#the-host-tools-are-not-in-the-key) |
| `You must install 'git'` in a remote action only | the worker image lacks a host tool the local machine has | add it to `toolkit/infra/buildbarn/runner/Dockerfile` and recreate the runner |
| `make` exits with `-11` (SIGSEGV) on an old Buildroot | GNU make 4.3 overflows the 8 MiB stack in `printvars`/`show-info` | already handled: the namespace raises the stack limit; keep `br2-ns.sh` current |
| `you should not run configure as root` | old `host-tar`, `host-m4` refuse root | already handled: the namespace sets `FORCE_UNSAFE_CONFIGURE=1` |
| `No rule to make target 'show-vars'` | Buildroot older than 2023 | already handled: extract falls back to `printvars` |
| `unexpected local source '/mnt/...'` at extract | a local package site outside `common/` | in-tree sites (`/mnt/external/...`, `/mnt/src/...`) are accepted; anything else belongs in `common/` |
| `make: *** No rule to make target` for a package that builds locally, in a remote action only | a view entry is not a declared input at its real path (a copied `export_file`), so the worker has nothing there | `br2 viewcheck --mode remote`; see [ADR-0014](../decisions/0014-view-entries-are-declared-inputs.md) |
| `br2-ns: view entry missing: ...` | a declared entry is absent from this action's inputs | declare it (a `links` or `extra_view` entry), then re-run `br2 viewcheck` |
| `ld: cannot find crti.o` in a native build | a native recipe hard-coded a toolchain tuple or the sysroot's directory name | native rules read `TARGET_TUPLE` and `STAGING_SUBDIR` from `br2/generated/target.bzl` ([ADR-0012](../decisions/0012-toolchain-tuple-from-buildroot.md)) |
| Kernel: `kernelrelease` probe fails in the rootfs action | the kernel's build tree is not there | handled by a stub; if you see it, the toolkit is stale |

## Reading a manifest difference

```bash
scripts/fs-manifest.py scan <image> -o /tmp/mine.json
scripts/fs-manifest.py diff golden/rootfs.manifest.json /tmp/mine.json
```

`differs: /bin/busybox (size: 813512 -> 997264)` with a *larger* result is nearly
always "not stripped". `only in A` is a file the golden had and Buck2 lost - commonly
a dangling symlink Buck2 cannot see as an input (`/var/log`, `/etc/mtab`), which the
renderer records as data. A file that differs on *every* run of the golden build
too (random salts) belongs in `manifest_ignore`.

To compare one package's artifact between wrapped and native:

```bash
scripts/compare-pkg.py wrapped.tar native.tar
```
