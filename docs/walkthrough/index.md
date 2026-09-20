<title>Walkthrough</title>

# Walkthrough: helloworld from the inside

The [Quickstart](../home/quickstart.md) gets `helloworld` built in a few commands. This section takes the same
project apart: every step, what buckroot does at that step, and what is on disk or on the wire while it does it.
It is a tutorial - you follow along - but it stops at each command to show what happened underneath.

Everything printed here is real output from `experiments/helloworld` (Buildroot 2025.02.18, 4 cores), captured
while writing these pages. Timings were taken while another build was running on the same machine, so read
them as orders of magnitude, not benchmarks; the measured tables are on [Results](../project/results.md).

## Three ways to build a package

The same package - `hello` - can be built three ways. They differ in **who does the work inside a Buck2
action**, and therefore in how finely Buck2 can cache and skip it.

| | [Wrapped](wrapped.md) | [Stepped](stepped.md) | [Native](native.md) |
|---|---|---|---|
| One Buck2 action does | all of `make hello` | one Buildroot step (`hello-configure`, `hello-build`, ...) | one small job (compile, link, install) |
| Buildroot's `.mk` runs | yes, whole | yes, one step at a time | no |
| Works for | every package | every package | packages that have a rule |
| Skips work when | the package's inputs are unchanged | a *step's* inputs are unchanged | a *job's* inputs are unchanged |
| Status | **works**, used for every project | **design only**, not implemented | **works** for a set of packages |

Read [Wrapped](wrapped.md) first: it introduces everything the other two build on. The stepped page is honest about
being a design: it shows what was verified by hand and what has not been built.

## What you need

- The prerequisites of the [Quickstart](../home/quickstart.md) (Linux, root or `CAP_SYS_ADMIN`, about 8 GB RAM).
- A checkout of the repository. All commands run from `experiments/helloworld` unless stated otherwise.

## Part 0: the project

`helloworld` is a Buildroot image with one package of its own. The package is three files.

`buildroot-external/package/hello/hello.mk` - Buildroot's recipe:

```make
HELLO_VERSION = 1.0
HELLO_SITE = $(BR2_EXTERNAL_BUCKROOT_HELLOWORLD_PATH)/../common/hello
HELLO_SITE_METHOD = local
HELLO_LICENSE = MIT

define HELLO_BUILD_CMDS
	$(TARGET_CC) $(TARGET_CFLAGS) -o $(@D)/hello $(@D)/hello.c
endef

define HELLO_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/hello $(TARGET_DIR)/usr/bin/hello
endef

$(eval $(generic-package))
```

`common/hello/hello.c` - the program:

```c
#include <stdio.h>

int main(void)
{
    printf("hello from buckroot helloworld\n");
    return 0;
}
```

`HELLO_SITE_METHOD = local` means Buildroot does not download anything for `hello`: it copies (rsyncs) a directory.
That is why the source lives in `common/`, next to the experiment, and why `hello` has no download step - a fact
the [stepped](stepped.md) page returns to.

The whole project is described to buckroot by one file, `project.json`:

```json
{
  "name": "helloworld",
  "defconfig": "helloworld_qemu_aarch64_musl_rootfs_defconfig",
  "external": true,
  "buildroot": {"repo": "https://git.buildroot.net/buildroot", "ref": "2025.02.18"},
  "native": ["hello", "host-skeleton", "host-fakedate", "skeleton", "musl-compat-headers",
             "initscripts", "urandom-scripts", "skeleton-init-sysv", "skeleton-init-common",
             "toolchain", "toolchain-external", "toolchain-external-bootlin"]
}
```

| Key | What it says |
|---|---|
| `name` | names the cache directory `~/.cache/br2/helloworld` and the Buildbarn instance |
| `defconfig` | a file from the external tree's `configs/` |
| `external` | a `BR2_EXTERNAL` tree exists in `buildroot-external/` |
| `buildroot` | which Buildroot to fetch: a release tag |
| `native` | the packages the *native* variant builds with Buck2 jobs instead of `make`; ignored by wrapped |

The defconfig selects a small aarch64 image: musl libc, Bootlin's prebuilt external toolchain (so nothing compiles
a compiler), BusyBox with sysv-style init scripts, and `hello`.

## Part 1: `br2 setup`

```bash
../../toolkit/bin/br2-sync .     # vendor the toolkit into this directory
scripts/br2 setup
```

`br2-sync` copies `scripts/`, `br2/`, `platforms/`, `toolchains/`, `infra/` from the toolkit into the experiment
and writes `.buckconfig` and the root `BUCK` from templates plus `project.json`. Those copies are git-ignored: the
experiment *contains* the toolkit version it was run with, so Buck2 sees the rules as part of its own cell.

`br2 setup` then does two things, both idempotent:

1. `scripts/fetch-buck2.sh` installs the pinned `buck2` binary into `tools/`, from a shared cache in
   `~/.cache/br2/tools`, so a second experiment does not download it again.
2. `scripts/fetch-buildroot.sh` runs `git clone --depth 1 --branch 2025.02.18` into `buildroot-src/` and records the
   commit in `BUILDROOT_PINNED_COMMIT.txt`:

```text
Fetched https://git.buildroot.net/buildroot 2025.02.18 (d030e36bbc9669230c015be971b14b6e062cfdde) into .../buildroot-src
```

Nothing is built yet. `buildroot-src/` is a plain Buildroot tree that nothing will ever write to: from here on it is
mounted read-only into every action.

## Part 2: `br2 extract`

```bash
scripts/br2 extract
```

```text
+ scripts/br2buck.py extract
29 packages -> golden/model.json
+ scripts/br2buck.py render
33 files rendered
```

This is the step that turns "a Buildroot configuration" into "a Buck2 graph". It has two halves.

### Extract: ask Buildroot what the project contains

`br2buck.py extract` creates a throwaway output directory and, **inside the fixed-path namespace** described on the
[wrapped page](wrapped.md#the-namespace), runs:

1. `make helloworld_qemu_aarch64_musl_rootfs_defconfig` - Buildroot turns the defconfig into a `.config`.
2. It appends the two settings every buckroot build needs, `BR2_PER_PACKAGE_DIRECTORIES=y` (one output tree per
   package) and `BR2_REPRODUCIBLE=y` (fixed timestamps), plus the project's `config_fragment` if it has one, and
   runs `make olddefconfig` so Kconfig settles.
3. `make show-info` - Buildroot's own JSON description of every package in the configuration.
4. `make show-vars VARS=GNU_TARGET_NAME` - the toolchain tuple (`aarch64-buildroot-linux-musl`), which names the sysroot
   directory.

No package is built. On this machine the whole extract takes about a minute. What comes out is
`golden/model.json`: only the *graph* - versions, direct dependencies, sources with hashes, the directory where each
package's makefile lives, the stamp directory Buildroot will use. Build commands and hooks stay in Buildroot. This is
the entry for `hello`:

```json
"hello": {
  "deps": ["host-fakedate", "host-skeleton", "skeleton", "toolchain"],
  "dir": "buildroot-external/package/hello",
  "dl_dir": "hello",
  "kind": "target",
  "sources": [{"file": "hello-1.0.tar.gz", "local": "common/hello"}],
  "stamp_dir": "build/hello-1.0",
  "version": "1.0",
  "virtual": false
}
```

`deps` is Buildroot's answer to "what must exist before `hello` is built". `sources[].local` says the source is the
directory `common/hello`. And this is what a package with a real download looks like (`host-e2fsprogs`, shortened):

```json
"host-e2fsprogs": {
  "deps": ["host-fakedate", "host-pkgconf", "host-skeleton", "host-util-linux"],
  "dir": "buildroot-src/package/e2fsprogs",
  "kind": "host",
  "sources": [{
    "file": "e2fsprogs-1.47.2.tar.xz",
    "sha256": "08242e64ca0e8194d9c1caad49762b19209a06318199b63ce74ae4ef2d74e63c",
    "urls": ["https://cdn.kernel.org/pub/linux/kernel/people/tytso/e2fsprogs/v1.47.2/e2fsprogs-1.47.2.tar.xz", "..."]
  }],
  "stamp_dir": "build/host-e2fsprogs-1.47.2",
  "version": "1.47.2"
}
```

### Render: turn the model into `BUCK` files

`br2buck.py render` needs no Buildroot. It writes one `BUCK` file per directory that holds packages, so the Buck2
target graph mirrors Buildroot's tree. For `hello` it wrote `buildroot-external/package/hello/BUCK`:

```python
br2_inputs(                       # (1)
    name = "inputs",
    srcs = ["Config.in", "hello.mk"],
    visibility = ["PUBLIC"],
)

br2_package(                      # (2)
    name = "hello",
    pkg = "hello",
    pkg_inputs = ":inputs",
    stamp_dir = "build/hello-1.0",
    dl_dir = "hello",
    deps = [                      # (3)
        ("//br2/native/host-fakedate:host-fakedate" if "host-fakedate" in read_config("br2", "native", "").split(",")
         else "//buildroot-src/package/fakedate:host-fakedate"),
        ...
        ("//br2/native/toolchain:toolchain" if "toolchain" in read_config("br2", "native", "").split(",")
         else "//buildroot-src/toolchain/toolchain:toolchain"),
    ],
    local_srcs = ["//common/hello:src"],   # (4)
    visibility = ["PUBLIC"],
)
```

1. `br2_inputs` lists every file in the package's directory. It is an input of `hello`'s actions and of every
   package that depends on `hello`: a change to `hello.mk` invalidates them.
2. `br2_package` is the rule that runs Buildroot's `make hello` in an action. This is the **wrapped** target.
3. Dependencies are the model's `deps`. Each one is a conditional: if the package is listed in the `[br2] native`
   config (the native variant), the dependency is the native target, otherwise the wrapped one. That single
   `read_config` is the whole switch between the variants for a dependency edge.
4. `local_srcs` declares `common/hello` as an input, because `hello`'s source is not downloaded.

The top-level `BUCK` only aliases `//:rootfs` to `//br2/generated:rootfs`, and `br2/generated/BUCK` holds three
targets: `config` (`br2_config`, the `.config` for the defconfig), `owners` (`br2_owners`, which config symbol
belongs to which directory, used later to slice the config) and `rootfs` (`br2_rootfs`, the final image, depending on
all 29 packages). `buck2 uquery 'kind(br2_package, deps(//:rootfs))'` lists exactly 29 package targets.

## Part 3: `br2 golden`

```bash
scripts/br2 golden
```

Before Buck2 builds anything, buckroot builds the same project with **plain `make`** - no Buck2 - in the same
namespace and with the same config fragment. It takes a few minutes on four cores. This *golden* build is the
answer key. `scripts/fs-manifest.py scan` reduces its `rootfs.ext4` to `golden/rootfs.manifest.json`: for each of the
369 paths in the image, its type, mode, owner and (for files) size and SHA-256:

```json
"/etc/hostname": {"gid": 0, "mode": "0644", "sha256": "b75d7f28...", "size": 10, "type": "file", "uid": 0}
```

From now on "Buck2 got it right" means one thing: the manifest of the Buck2-built image is **IDENTICAL** to this one.
Why a manifest and not the image bytes is [ADR-0006](../decisions/0006-golden-and-manifest-comparison.md).

## Where to next

- [Wrapped](wrapped.md): build `hello` with Buck2 and follow one action from the Buck2 command line down to `make`.
- [Stepped](stepped.md): what changes when each Buildroot step becomes its own action.
- [Native](native.md): what changes when `make` is not involved at all.
