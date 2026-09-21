<title>Wrapped and native packages</title>

# Wrapped and native packages

buckroot builds a project in one of two variants. They produce the same package
artifacts and the same root filesystem, and you can mix them per package.

| | wrapped | native |
|---|---|---|
| A package's action | Buildroot's own `make <pkg>` in a [view](views-and-slices.md) | Buck2 actions that do the work: untar, compile, link, install |
| Works for | every Buildroot package | packages with a rule in `toolkit/br2/native/` or the project's `native/` |
| Early cutoff | package granularity | per step: a comment-only change in a C file skips the link and everything after |
| Runs remotely | needs the pinned tool baseline in the worker image | nothing ambient beyond the declared toolchain |
| Cost of a rebuild of one small package | a whole `make` in a namespace plus the toolchain overlay (about 40 s) | the compile alone (under a second when nothing changed) |

Switch per package with the `native` list in `project.json`; the
generated targets are the same and downstream packages do not change.

## Wrapped: Buildroot does the work

The action seeds a scratch output tree with the package's config slice and its
dependencies' artifacts, runs `make <pkg>` in the view, and packs whatever changed -
`per-package/<pkg>/{host,target}`, the stamps, the `.files-list*` files - as the package's
artifact. Buck2 owns ordering, parallelism and invalidation; Buildroot owns everything
about how a package is built. That is what makes this variant work for projects
with Mesa, a vendor kernel and Rust host tools without modelling any of it.

### The host tools are not in the key

The action key hashes the command, the declared inputs and the declared environment - not
the host's `gcc`, `perl`, `rsync` or `make`. Two machines with different tools can
produce different bytes for the same key, so a cache hit is unsound rather than
loudly failing. For remote execution the answer is to pin the tools: the worker
image (`toolkit/infra/buildbarn/runner/Dockerfile`) is the tool baseline, and
the action's `PATH` is fixed (Buck2 sends an empty environment; the runner resolves
executables through the command's own `PATH`).

## Native: Buck2 does the work

A native package stands in for a Buildroot package: it has the same label and produces
the same artifact. Because wrapped packages that *depend on* a native one still need
Buildroot's `.mk` for it (`make` must know `host-fakedate` as a target), a native package
reports the Buildroot package directory it replaces as its own.

The `hello` package shows the shape: the toolchain tarball is unpacked as a Buck2 artifact
(`br2_untar`), `hello.c` is compiled and linked by two separate actions with the real
cross compiler (`br2_cc_program`), and `br2_native_package` writes the artifact the
rootfs action expects.

### The flags are the contract

Buildroot's toolchain wrapper silently adds `--sysroot`, `-mabi`, `-mcpu`,
`-fstack-protector-strong`, `-fPIE -pie`, `-Wl,-z,relro,now` and `-Wl,--build-id=none` to
every compiler call (visible with `BR2_DEBUG_WRAPPER=1`). Reproducing exactly those flags
on the *unwrapped* compiler gives a byte-identical `hello`.

### The artifact format is an interface

- `host-finalize` rsyncs every package's `per-package/<pkg>/host/`, so a native artifact
  without that (empty) directory fails the whole rootfs with an `rsync` error 23, far from
  the cause.
- Each package kind needs its own stamps for `make` to consider it done (host:
  `.stamp_host_installed`; sysroot headers: `.stamp_staging_installed`; local sites:
  `.stamp_rsynced`).
- `rsync -u` skips destination files that are *newer*. That was an accident of the mtime
  ordering of a sequential build (the toolchain's `etc/passwd` never overwrote the
  skeleton's); native artifacts have fixed mtimes, so the ordering is reproduced *by
  dependency*.
- `.files-list-host.txt` covers only what an install step adds; `.files-list-staging.txt`
  covers the merged sysroot including dependencies. Only the former is exactly
  reproducible per package.
- **Nothing may hard-code the toolchain.** A sysroot lives at `host/<tuple>/sysroot`, and the
  tuple depends on the configuration: `aarch64-buildroot-linux-gnu` for an internal glibc
  toolchain, `aarch64-buildroot-linux-musl` for a Bootlin musl one. `br2 extract` asks
  Buildroot for `GNU_TARGET_NAME` and `br2 render` writes it to `br2/generated/target.bzl`;
  native rules load `TARGET_TUPLE` from there. The first version hard-coded the musl tuple
  it was developed on. On a glibc project the native skeleton then created its
  `lib64 -> lib` symlinks in a sysroot nobody used, glibc installed a real `usr/lib64`
  directory, and `host-gcc-final` failed with `ld: cannot find crti.o` about fifty minutes
  into the build. (The sysroot's directory name is data as well: Bottlerocket's SDK calls it `sys-root`, recorded as
  `STAGING_SUBDIR`, [ADR-0012](../decisions/0012-toolchain-tuple-from-buildroot.md#addendum-2026-09-21-the-sysroots-directory-name-is-data-too).) The symptom was far from the cause, and a first equivalence check
  missed it because both sides were the wrapped artifact (see
  [below](#equivalence-is-checked-not-assumed)).

### Config-dependent packages declare their config

A native package declares the symbols it reads (`config = [...]`); an action extracts only
their values into a small JSON that the recipe reads. `skeleton-init-common` reads
`BR2_ROOTFS_MERGED_USR`, `BR2_ARCH_IS_64` and `BR2_SYSTEM_DEFAULT_PATH`; changing any other
symbol leaves the package's key untouched. That is a stricter contract than the heuristic
slice wrapped packages get.

A recipe **raises on any configuration it does not implement** (glibc instead of musl,
Fortran, host gdb...) instead of quietly producing a wrong artifact.

### Equivalence is checked, not assumed

```bash
scripts/compare-pkg.py wrapped.tar native.tar
```

compares files (path, mode, sha256), symlinks, stamps and the `.files-list*` contents.
Building the `//buildroot-src/...` label of a package always gives the *wrapped* artifact:
`native` takes effect through the labels that dependents resolve (`br2_dep`), so build the
native artifact as `//br2/native/<pkg>` when comparing.
The two toolchain-sysroot files Buildroot rewrites for every package that depends on the
toolchain (`ppd-fixup-paths`) are ignored. See [Verification](verification.md).

## What ships as native

The generic ones (`toolkit/br2/native/`): `host-skeleton`, `host-fakedate`, `skeleton`,
`skeleton-init-sysv`, `skeleton-init-common`, `initscripts`, `urandom-scripts`,
`musl-compat-headers`, and the external-toolchain trio `toolchain-external-bootlin`,
`toolchain-external`, `toolchain`. A project adds its own under `native/<pkg>/BUCK`.

`helloworld` builds `hello`, its whole dependency closure, and two init-script packages this way (12 packages). The
external-toolchain package is the hardest: it unpacks the tarball, compiles Buildroot's
compiler wrapper with the host compiler (a byte-identical result once `__FILE__` is
mapped), installs the sysroot, rewrites the libtool `.la` files, generates `gdbinit` and
copies the runtime libraries into the target tree following symlink chains. Every one of
those steps is a Buildroot make macro reimplemented in a small `recipe.py`.

Still wrapped in every project: anything that compiles a large upstream tarball. Native
rules for autotools and make projects - not just install-only recipes - are the next
frontier; see [Status and roadmap](../project/status.md).
