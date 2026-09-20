<title>Step 6: Native</title>

# Step 6: Native: Buck2 does the work, `make` does not run

In [Step 4](wrapped.md) Buck2 ran Buildroot's `make hello`. In the **native** variant it does not run `make` at all: Buck2
performs the same jobs itself, as separate actions (compile, link, install), and produces the same output file as the wrapped
build. The package keeps the same label and the same output, so nothing else in the build can tell the difference.

This page builds `hello` natively, shows the actions, and proves the result is the same as the wrapped one.

## What "native" replaces

Step 1 showed `hello.mk`. Its two important commands are:

```make
define HELLO_BUILD_CMDS
	$(TARGET_CC) $(TARGET_CFLAGS) -o $(@D)/hello $(@D)/hello.c
endef

define HELLO_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/hello $(TARGET_DIR)/usr/bin/hello
endef
```

Compile-and-link the program, then copy it into the filesystem. The native rule is the same two jobs written for Buck2, in the
file `native/hello/BUCK`:

```python
br2_cc_program(                                             # HELLO_BUILD_CMDS
    name = "hello-bin",
    srcs = ["//common/hello:hello.c"],
    toolchain = "//br2/native/tc-bootlin:bootlin-aarch64-musl",
    defines = ["_LARGEFILE_SOURCE", "_LARGEFILE64_SOURCE", "_FILE_OFFSET_BITS=64"],
    copts = ["-O2", "-g0"],
)

br2_native_package(                                         # HELLO_INSTALL_TARGET_CMDS, and the output file
    name = "hello",
    pkg = "hello",
    bdir = "buildroot-external/package/hello",
    pkg_inputs = "//buildroot-external/package/hello:inputs",
    stamp_dir = "build/hello-1.0",
    stamps = BR2_STAMPS_LOCAL,
    install = {"usr/bin/hello": ":hello-bin"},               # where in the filesystem -> what to put there
    deps = [br2_dep("host-fakedate", "..."), br2_dep("host-skeleton", "..."),
            br2_dep("skeleton", "..."), br2_dep("toolchain", "...")],
)
```

Read it line by line, with Step 2's vocabulary:

- `br2_cc_program` is a **rule** that builds a C program. `srcs` is `hello.c`, a declared input file. `toolchain` names the
  compiler, which is Bootlin's, **unpacked as a Buck2 output** (`br2_untar`): the same downloaded archive, with the same
  checksum, that the wrapped `toolchain-external-bootlin` package uses, but now an ordinary declared input instead of something
  hidden inside `make`.
- `defines` and `copts` are `$(TARGET_CFLAGS)` written out by hand: `-D_LARGEFILE_SOURCE -D_LARGEFILE64_SOURCE
  -D_FILE_OFFSET_BITS=64 -O2 -g0`. There is no automatic translation of a `.mk` file: the `BUCK` file is hand-written and then
  **checked** against the wrapped result (below).
- `br2_native_package` produces the output file the rest of the build expects. `install` is the install step: "put what
  `:hello-bin` produced at `usr/bin/hello`". `stamps` are the marker files Buildroot needs to see (Step 1). `deps` lists the
  dependencies.
- `br2_dep(...)` means "the native version of this dependency if it is on the native list, otherwise the normal one". A native
  package must use it. If it named the wrapped dependency directly, both versions would end up in the build.

## Try it

```bash
NATIVE=$(python3 -c "import json;print(','.join(json.load(open('project.json'))['native']))")
tools/buck2 build //native/hello:hello --config br2.native=$NATIVE --config br2.native_project=hello
```

`//native/hello:hello` is the native target. (The label `//buildroot-external/package/hello:hello` from Step 4 is always the
*wrapped* one. Native takes effect through the dependencies that other packages resolve with `br2_dep`.) With `hello` and its nine
dependencies all native, and nothing cached:

```text
Commands: 15 (cached: 0, remote: 0, local: 15)                real 31.6 s
```

That is 15 actions in 31 seconds, against 22 actions and 72 seconds in Step 4, where each dependency was a whole `make` in a
private room. Once the dependencies exist, `hello` alone is three actions:

```text
root//native/hello:hello-bin (br2_cc_compile hello.c)
root//native/hello:hello-bin (br2_cc_link hello-bin)
root//native/hello:hello     (br2_native_package hello)
```

| Action | What it runs |
|---|---|
| `br2_cc_compile` | the cross-compiler, directly: `aarch64-buildroot-linux-musl-gcc.br_real --sysroot <sysroot> -mabi=lp64 -mcpu=cortex-a53 -fstack-protector-strong -fPIE -D_LARGEFILE_SOURCE ... -O2 -g0 -c hello.c -o hello.c.o` |
| `br2_cc_link` | the same compiler, linking: `... -pie -Wl,-z,max-page-size=4096 -Wl,-z,common-page-size=4096 -Wl,--build-id=none hello.c.o -o hello-bin` |
| `br2_native_package` | `native_pkg.py`: assemble `per-package/hello/{host,target}`, the stamps and the file lists into `hello.tar` |

Compiling and linking are separate actions. That is how the C build normally works: first turn each source file into an
**object file** (`hello.c.o`, machine code that is not yet a complete program), then **link** the objects and libraries
into the finished executable.

Notice what is missing: the private room, the view, the slice, `make`. The inputs are the declared source file and the declared
compiler; nothing else is reachable because nothing else is given. That is also why native actions are simple to run remotely:
they ran unchanged on the Buildbarn worker.

## The flags are the contract

Where do `-fstack-protector-strong -fPIE -pie -Wl,-z,relro,now -mabi=lp64 -mcpu=cortex-a53` come from? They are not in
`hello.mk`. Buildroot has a **toolchain wrapper**: a small program that stands in for the compiler and silently adds
security and architecture flags to every call (you can see them with `BR2_DEBUG_WRAPPER=1`). The wrapped `make hello` calls the
wrapper. The native rule calls the real compiler *behind* the wrapper, so it must add exactly the same flags itself. Get one
wrong and the program is different. Get them right and:

```text
$ tar -xOf hello-wrapped.tar per-package/hello/target/usr/bin/hello | sha256sum
fbec9258fc42341baec26630220c21ca7bd9d42054a8cfbc30399ed3c7519afb
$ tar -xOf hello-native.tar  per-package/hello/target/usr/bin/hello | sha256sum
fbec9258fc42341baec26630220c21ca7bd9d42054a8cfbc30399ed3c7519afb
```

(`sha256sum` prints a fingerprint of a file's bytes; two files with the same fingerprint are identical.) The program Buck2
compiled is **byte-for-byte identical** to the one Buildroot's `make` produced.

## Checking the whole package, not just the program

A package's output is more than one file, so buckroot compares the whole archives:

```bash
scripts/compare-pkg.py hello-wrapped.tar hello-native.tar
```

```text
directories only in wrapped (inherited layout, informational): 350
EQUIVALENT
```

`compare-pkg.py` compares what the image step will consume: regular files (path, mode, hash), symbolic links, the stamps and
the `.files-list` contents. Two kinds of difference are expected and ignored:

- The 350 *directories* that only the wrapped archive has. They are the empty folder skeleton that a wrapped package inherits from
  its dependencies; the image does not depend on them.
- Two *files* the wrapped archive has and the native one does not:
  `sysroot/usr/share/buildroot/gdbinit` and `sysroot/usr/lib/libstdc++.so.6.0.32-gdb.py`. Buildroot rewrites these two for every
  package that depends on the toolchain, so each contains that package's own paths. They are harmless, and the tool ignores them by
  name.

The final check is the one used everywhere: the manifest of the whole native build's image must be IDENTICAL to the golden's,
and it is, in every native row of the `helloworld` [results](../project/results.md).

## What reruns when something changes

Make the same comment-only edit to `hello.c` as on the [wrapped page](wrapped.md#what-reruns-when-something-changes):

```text
$ tools/buck2 build //native/hello:hello --config br2.native=$NATIVE --config br2.native_project=hello
Commands: 1 (cached: 0, remote: 0, local: 1)          real 0.67 s
  root//native/hello:hello-bin (br2_cc_compile hello.c)
```

Only the compile ran. The compiler produced an **identical object file** (a comment does not change the machine code), so the
link action's inputs were unchanged, and Buck2 skipped it. That is the *early cutoff* from [Step 2](buck2.md), now at the
granularity of a single job. The package action after it was skipped too, and everything after that. Wrapped reran the whole
`hello` (12 seconds); native ran a 0.67-second compile and stopped. A real code change reruns the compile, the link, the package
and the image step (about 35 seconds, most of it the image step).

That is where native pays: not the first build (31 seconds against 72 here, with all ten packages of the closure native), but the
**rebuild**.

## Packages that depend on configuration

`hello` reads no configuration. Most packages do. For instance `skeleton-init-common` (also native in `helloworld`) depends on
three options: `BR2_ROOTFS_MERGED_USR` (are `/bin`, `/sbin`, `/lib` symbolic links to `/usr/...`?), `BR2_ARCH_IS_64` (is the library
directory `lib64` or `lib32`?) and `BR2_SYSTEM_DEFAULT_PATH` (written into `/etc/profile`). A native rule lists the options it reads:

```python
br2_native_package(name = "skeleton-init-common",
                   config = ["BR2_ROOTFS_MERGED_USR", "BR2_ARCH_IS_64", "BR2_SYSTEM_DEFAULT_PATH"], ...)
```

An action extracts just those values into a small file that the package's `recipe.py` (its install logic, in Python) reads. So
changing any *other* option leaves this package's key untouched. That is a stricter promise than the
[slice](wrapped.md#the-configuration-slice) a wrapped package gets. A recipe also **refuses** any configuration it does not
implement (say, glibc instead of musl) rather than producing a quietly wrong result.

Even the sysroot's location depends on the toolchain: the folder is named after the toolchain (`aarch64-buildroot-linux-musl`
here, `aarch64-buildroot-linux-gnu` for a glibc one). `br2 extract` records that name and the rules read it from
`br2/generated/target.bzl` ([ADR-0012](../decisions/0012-toolchain-tuple-from-buildroot.md)); a first version that hard-coded it
failed on the Car Thing project. One rule is still specific to this project: `br2_cc_program` names the Bootlin musl compiler and
`-mcpu=cortex-a53` directly. Making that come from the model is the next step before a second project can use it.

## Writing a native package

1. Read the package's makefile and the log of its wrapped build (`make.log`, as in Step 4): what commands run, with which flags?
2. Write `native/<pkg>/BUCK` (or add a generic one to `toolkit/br2/native/`): compile and link actions, an install
   mapping, and the right stamps for the package's kind (`BR2_STAMPS_LOCAL`, `_TARGET`, `_HOST`, `_STAGING`).
3. Add the package to `native` in `project.json`.
4. Build both the wrapped and the native output and run `compare-pkg.py`. Fix until it says EQUIVALENT.
5. Run the whole variant and compare the image manifest with the golden.

What can go wrong is listed in [Wrapped and native packages](../concepts/wrapped-and-native.md#the-artifact-format-is-an-interface): an
empty `host/` directory that must exist or the image step fails with an obscure error, file-modification-time accidents in
Buildroot's copy commands, stamps that differ per kind of package, and toolchain names that were hard-coded.

## What native cannot do (yet)

- **Cover every package.** Rules exist for the skeleton, the init scripts, the external toolchain and `hello`. A package that
  compiles a large upstream archive needs a real rule for its build system (autotools, cmake, meson) that understands its options.
  That work is not done ([Status and roadmap](../project/status.md)).
- **Follow Buildroot upgrades for free.** For wrapped, the makefile is the source of truth. For native it is only documentation: when
  Buildroot changes a recipe, the native rule does not notice; `compare-pkg.py` against a fresh wrapped build does.

## Which one should I use?

| If you... | Use |
|---|---|
| are starting with a project, or just want it working | wrapped: works for every package on day one |
| have a few packages you change constantly, and rebuild time hurts | native for those packages, wrapped for the rest (they mix per package) |
| want to understand a package's build fully, with no hidden steps | native: everything is declared |
| are considering finer skipping inside big packages | read the [stepped](stepped.md) design first |

The [Results](../project/results.md) page has the measured comparison for each project; the [Guides](../guides/adding-a-project.md)
show how to bring in a project of your own.
