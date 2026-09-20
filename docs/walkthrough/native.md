<title>Native</title>

# Native: Buck2 does the work, `make` does not run

In the native variant a package's `make` is replaced by Buck2 actions that do the same jobs themselves: unpack, compile,
link, install. The package keeps the same label and produces the same artifact, so nothing downstream can tell. This
page builds `hello` natively, shows the actions, and proves the result equals the wrapped one.

Start from the [overview](index.md); the [wrapped page](wrapped.md) explains the artifact this variant has to produce.

## What "native" replaces

`hello.mk` says what Buildroot does for `hello`:

```make
define HELLO_BUILD_CMDS
	$(TARGET_CC) $(TARGET_CFLAGS) -o $(@D)/hello $(@D)/hello.c
endef
define HELLO_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/hello $(TARGET_DIR)/usr/bin/hello
endef
```

A compile-and-link, and an install. The native rule for `hello`, `native/hello/BUCK`, says the same thing to Buck2:

```python
br2_cc_program(                                             # HELLO_BUILD_CMDS
    name = "hello-bin",
    srcs = ["//common/hello:hello.c"],
    toolchain = "//br2/native/tc-bootlin:bootlin-aarch64-musl",
    defines = ["_LARGEFILE_SOURCE", "_LARGEFILE64_SOURCE", "_FILE_OFFSET_BITS=64"],
    copts = ["-O2", "-g0"],
)

br2_native_package(                                         # HELLO_INSTALL_TARGET_CMDS + the artifact
    name = "hello",
    pkg = "hello",
    bdir = "buildroot-external/package/hello",
    pkg_inputs = "//buildroot-external/package/hello:inputs",
    stamp_dir = "build/hello-1.0",
    stamps = BR2_STAMPS_LOCAL,
    install = {"usr/bin/hello": ":hello-bin"},               # path in the target tree -> what to put there
    deps = [br2_dep("host-fakedate", "..."), br2_dep("host-skeleton", "..."),
            br2_dep("skeleton", "..."), br2_dep("toolchain", "...")],
)
```

Line by line:

- `toolchain` is Bootlin's compiler, **unpacked as a Buck2 artifact** (`br2_untar`): the same tarball and SHA-256 that the
  wrapped `toolchain-external-bootlin` package downloads, but declared as an input instead of hidden in a `make`.
- `defines` and `copts` are `$(TARGET_CFLAGS)` written out. The link to `hello.mk` is a comment: there is no machine
  translation of a `.mk` file, the `BUCK` file is hand-written and checked (below).
- `br2_native_package` writes the artifact the rootfs action expects: the file tree (`install`), the five stamps
  `BR2_STAMPS_LOCAL` for a local-site package, and the `.files-list*` files.
- `br2_dep` picks the *native* label of a dependency when it is in the native list, and the wrapped one otherwise. A
  native package must use it, or one package would appear twice in the closure.

## Build it

```bash
NATIVE=$(python3 -c "import json;print(','.join(json.load(open('project.json'))['native']))")
tools/buck2 build //native/hello:hello --config br2.native=$NATIVE --config br2.native_project=hello
```

`//native/hello:hello` is the native target. (The `//buildroot-external/package/hello:hello` label is always the *wrapped*
one; the native variant takes effect through the dependencies that other packages resolve with `br2_dep`.) With `hello`
and its nine dependencies all native, and nothing cached:

```text
Commands: 15 (cached: 0, remote: 0, local: 15)                real 31.6 s
```

15 actions and 31 seconds, against 22 actions and 72 seconds wrapped. Once the dependencies exist, `hello` itself is three
actions:

```text
root//native/hello:hello-bin (br2_cc_compile hello.c)
root//native/hello:hello-bin (br2_cc_link hello-bin)
root//native/hello:hello     (br2_native_package hello)
```

| Action | What it runs |
|---|---|
| `br2_cc_compile` | the unwrapped cross compiler: `aarch64-buildroot-linux-musl-gcc.br_real --sysroot <sysroot> -mabi=lp64 -mcpu=cortex-a53 -fstack-protector-strong -fPIE -D_LARGEFILE_SOURCE ... -O2 -g0 -c hello.c -o hello.c.o` |
| `br2_cc_link` | the same compiler: `... -pie -Wl,-z,max-page-size=4096 -Wl,-z,common-page-size=4096 -Wl,--build-id=none hello.c.o -o hello-bin` |
| `br2_native_package` | `native_pkg.py`: assemble `per-package/hello/{host,target}`, the stamps and the file lists into `hello.tar` |

There is no namespace, no `make` and no view: the inputs are the declared source file and the declared toolchain
artifact, and nothing else is reachable because nothing else is passed. That is also why native actions are remote-safe
without any special handling: they ran unchanged on the Buildbarn worker.

## The flags are the contract

Where do `-fstack-protector-strong -fPIE -pie -Wl,-z,relro,now -mabi=lp64 -mcpu=cortex-a53` come from? Not from
`hello.mk`. Buildroot's **toolchain wrapper** adds them to every compiler call, silently (visible with
`BR2_DEBUG_WRAPPER=1`). The wrapped `make hello` calls the wrapper; the native rule calls the real compiler behind it
and must add exactly those flags itself. Get one wrong and the binary differs. Reproduce them, and it does not:

```text
$ tar -xOf hello-wrapped.tar per-package/hello/target/usr/bin/hello | sha256sum
fbec9258fc42341baec26630220c21ca7bd9d42054a8cfbc30399ed3c7519afb
$ tar -xOf hello-native.tar  per-package/hello/target/usr/bin/hello | sha256sum
fbec9258fc42341baec26630220c21ca7bd9d42054a8cfbc30399ed3c7519afb
```

The program compiled by Buck2 is **byte-identical** to the one Buildroot's `make` produced.

## Equivalence is checked, not assumed

```bash
scripts/compare-pkg.py hello-wrapped.tar hello-native.tar
```

```text
directories only in wrapped (inherited layout, informational): 350
EQUIVALENT
```

`compare-pkg.py` compares what the rootfs action consumes: regular files (path, mode, SHA-256), symlinks, stamps and the
`.files-list*` contents. The 350 directories are the empty directory skeleton a wrapped artifact inherits from its
dependencies, which the image does not depend on. Two *files* the wrapped artifact has are absent from the native one:
`sysroot/usr/share/buildroot/gdbinit` and `sysroot/usr/lib/libstdc++.so.6.0.32-gdb.py`. Buildroot rewrites those two, for every
package that depends on the toolchain, to contain that package's own paths; the tool ignores them by name.
The image-level check is the same one as everywhere: the manifest of the whole native build must be IDENTICAL to the
golden's, which it is in every native row of the `helloworld` [results](../project/results.md) table.

## What reruns when something changes

The same comment-only edit to `hello.c` as on the wrapped page:

```text
$ tools/buck2 build //native/hello:hello --config br2.native=$NATIVE --config br2.native_project=hello
Commands: 1 (cached: 0, remote: 0, local: 1)          real 0.67 s
  root//native/hello:hello-bin (br2_cc_compile hello.c)
```

One action ran: the compile. The compiler produced an **identical object file**, so the link action's inputs were
unchanged and it was skipped, and so was the package action, and everything after it. Wrapped reran `hello` (12 s); native
reran a 0.67 s compile and stopped. That is *early cutoff* at the granularity of a job instead of a package. A real code
change reruns compile, link, package and the rootfs (about 35 s of which the rootfs finalize is most).

This is where native pays: not the first build (31 s against 72 s here, with all ten packages of the closure native), but
the *rebuild*.

## Config-dependent packages

`hello` reads no configuration. Most packages do. `skeleton-init-common` (also native here) depends on
`BR2_ROOTFS_MERGED_USR` (are `/bin`, `/sbin`, `/lib` symlinks?), `BR2_ARCH_IS_64` (`lib64` or `lib32`) and
`BR2_SYSTEM_DEFAULT_PATH` (substituted into `/etc/profile`). A native rule declares the symbols it reads:

```python
br2_native_package(name = "skeleton-init-common", config = ["BR2_ROOTFS_MERGED_USR", "BR2_ARCH_IS_64", "BR2_SYSTEM_DEFAULT_PATH"], ...)
```

An action extracts just those values into a small JSON that the package's `recipe.py` reads, so changing any other
symbol leaves the package's action key untouched. That is a stricter contract than the [slice](wrapped.md#the-config-slice)
a wrapped package gets. A recipe **raises on any configuration it does not implement** (glibc, Fortran, host gdb...)
instead of producing a quietly wrong artifact.

The sysroot's location depends on the toolchain, so it is data too: `br2 extract` records the toolchain tuple
(`aarch64-buildroot-linux-musl` here) and the rules load it from `br2/generated/target.bzl`
([ADR-0012](../decisions/0012-toolchain-tuple-from-buildroot.md)). The rule that compiles `hello` itself is still specific
to this project: `br2_cc_program` names the Bootlin musl compiler and the `-mcpu=cortex-a53` flags directly. Making them
come from the model is the next step before a second project can use it.

## Writing a native package

1. Read the package's `.mk` and the log of its wrapped build (`make.log`): what runs, with which flags?
2. Write `native/<pkg>/BUCK` (or `toolkit/br2/native/` for a generic one), with the compile/link/install actions and the
   stamps for the package kind (`BR2_STAMPS_LOCAL`, `_TARGET`, `_HOST`, `_STAGING`).
3. Add `<pkg>` to `native` in `project.json`.
4. Build the wrapped and the native artifact and run `compare-pkg.py`. Iterate until it says EQUIVALENT.
5. Run the whole variant and compare the image manifest with the golden.

What can go wrong is in [Wrapped and native packages](../concepts/wrapped-and-native.md#the-artifact-format-is-an-interface):
a missing empty `host/` directory fails the rootfs with an `rsync` error far from the cause, `rsync -u` mtime ordering
accidents, stamps that differ per package kind, and toolchain paths that were hard-coded.

## What native cannot do

- **Scale to every package by hand.** Rules exist for the skeleton, init scripts, the external toolchain and `hello`. A
  package that compiles a large upstream tarball needs a real build-system rule (autotools, cmake, meson) that
  understands its options; that work is not done ([Status and roadmap](../project/status.md)).
- **Follow Buildroot upgrades for free.** The `.mk` is the source of truth for the wrapped variant and a document for the
  native one. When Buildroot changes a recipe, the native rule does not notice; `compare-pkg.py` against a fresh wrapped
  build does.
