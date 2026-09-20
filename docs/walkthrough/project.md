<title>Step 3: Joining Buildroot and Buck2</title>

# Step 3: Joining Buildroot and Buck2

[Step 1](buildroot.md) showed what Buildroot builds; [Step 2](buck2.md) showed how Buck2 decides what to run. buckroot
joins them: it reads a Buildroot project and **generates a Buck2 graph from it**, one target per package, so that
Buck2 can build, cache and distribute a Buildroot image. This page runs the commands that do the joining, and explains
what each one does under the hood.

All commands run from `experiments/helloworld`. Every output is real.

## The one input: `project.json`

buckroot needs to be told which Buildroot project you mean. That is one small file:

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
| `name` | what to call the project: it names the cache directory `~/.cache/br2/helloworld` and the Buildbarn instance |
| `defconfig` | the Buildroot configuration to build (a file from the external tree's `configs/`, see [Step 1](buildroot.md#you-describe-the-system-in-one-file-the-defconfig)) |
| `external` | there is a `BR2_EXTERNAL` tree (your own packages) in the directory `buildroot-external/` |
| `buildroot` | which Buildroot to download: a release, by tag |
| `native` | a list used only by the *native* variant: which packages Buck2 should build itself, without `make` (see [Step 6](native.md)) |

Everything else in an experiment directory has a fixed name and meaning: `buildroot-src/` is the downloaded Buildroot,
`buildroot-external/` your packages, `common/` local sources, `golden/` the reference results.

## Installing the tools into the project: `br2-sync`

```bash
../../toolkit/bin/br2-sync .
```

buckroot's code (the Buck2 rules, the scripts, the `br2` command) lives in `toolkit/`. `br2-sync` **copies** the parts an
experiment needs into it (`scripts/`, `br2/`, `platforms/`, `toolchains/`, `infra/`) and writes two files: `.buckconfig`
(which tells Buck2 where the project root is and which rules to use) and a small top-level `BUCK`. The copies are ignored
by git, so an experiment directory *contains* the version of the toolkit it was run with, and Buck2 sees the rules as
part of its own project.

## `br2 setup`: fetch what is needed

```bash
scripts/br2 setup
```

```text
Fetched https://git.buildroot.net/buildroot 2025.02.18 (d030e36bbc9669230c015be971b14b6e062cfdde) into .../buildroot-src
```

Two things happen, and both are safe to repeat:

1. The `buck2` program itself is downloaded into `tools/` (from a shared cache in `~/.cache/br2/tools`, so a second
   project does not download it again). Every experiment pins the same version.
2. Buildroot is fetched with `git clone --depth 1 --branch 2025.02.18` into `buildroot-src/`, and the exact commit is
   written to `BUILDROOT_PINNED_COMMIT.txt`.

Nothing has been built. `buildroot-src/` is a plain Buildroot tree that nothing will ever write to again: from here on it
is mounted read-only into every build step.

## `br2 extract`: from a configuration to a graph

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

### Half one: ask Buildroot what the project contains

To build a graph, buckroot needs to know which packages the configuration includes and which depend on which. Buildroot
knows: it has a command, `make show-info`, that prints exactly that as JSON. So `extract` runs Buildroot (but does **not**
build anything) in a scratch directory:

1. `make helloworld_qemu_aarch64_musl_rootfs_defconfig`: turn the defconfig into a full `.config`.
2. Append the two settings every buckroot build needs, `BR2_PER_PACKAGE_DIRECTORIES=y` and `BR2_REPRODUCIBLE=y`, then
   `make olddefconfig` to let Buildroot settle the result.
3. `make show-info`: ask for every package.
4. `make show-vars VARS=GNU_TARGET_NAME`: ask for the toolchain's name (`aarch64-buildroot-linux-musl`), which names the
   sysroot directory.

That takes about a minute and writes `golden/model.json`, the **model**: only the *graph* - each package's version, its
direct dependencies, its source with checksums, the directory where its makefile lives, and the stamp directory Buildroot
uses. This is the entry for `hello`:

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

`deps` is Buildroot's own answer to "what has to exist before `hello` can be built?". `kind` is `target` (runs on the
device) or `host` (runs on the build machine). `sources` says where the code comes from. A package with a real
download looks like this (`host-e2fsprogs`, shortened):

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

Notice what is *not* in the model: how to build anything. The build commands stay in Buildroot's makefiles, where they
belong. buckroot takes the *graph* from Buildroot and lets Buildroot keep doing the building.

### Half two: write the `BUCK` files

`render` reads only the model (no Buildroot needed) and writes one `BUCK` file for every directory that holds packages, so
the Buck2 graph has the same shape as Buildroot's tree. For `hello` it wrote `buildroot-external/package/hello/BUCK`. If
Step 2 made `BUCK` files familiar, this is the same thing, generated:

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

1. `br2_inputs` lists every file in the package's directory: an input of `hello`'s actions, and of every package that
   depends on `hello`. Edit `hello.mk` and they are invalidated.
2. `br2_package` is the **rule** that runs Buildroot's `make hello` inside an action. The target's label is
   `//buildroot-external/package/hello:hello`.
3. The dependencies are the model's `deps`, as Buck2 labels. Each is a conditional: if the package is on the `native`
   list, the dependency is its native target, otherwise the normal one. That single `read_config` is the whole switch
   between the variants, per dependency.
4. `local_srcs` declares `common/hello` as an input, because `hello`'s source is a directory, not a download.

The top-level `BUCK` aliases `//:rootfs` to `//br2/generated:rootfs`. The file `br2/generated/BUCK` defines three
targets: `config` (the `.config` for the defconfig), `owners` (which config option belongs to which package
directory; used to give each package only the options it can see), and `rootfs` (the final image, which depends on all 29
packages). So:

```text
$ buck2 build //:rootfs        # build the whole image, every package in dependency order
$ buck2 uquery 'kind(br2_package, deps(//:rootfs))' | wc -l
29
```

That is the graph: 29 package targets, the same 29 Buildroot lists. What is left is what runs *inside* each target's
action, and that is what the three variants differ on.

## `br2 golden`: the answer key

```bash
scripts/br2 golden
```

Before Buck2 builds anything, buckroot builds the same project with **plain Buildroot** (no Buck2) and keeps the result.
It takes a few minutes. It runs in the same fixed-path environment as the Buck2 build (explained on the
[next page](wrapped.md#the-private-room-a-namespace)) with the same configuration. This **golden** build is the reference: the definition
of "correct".

To compare images, buckroot reduces one to a **manifest**: for every path in the image, its type, mode, owner and (for files)
size and SHA-256. `scripts/fs-manifest.py scan` writes `golden/rootfs.manifest.json`, 369 paths for `helloworld`:

```json
"/etc/hostname": {"gid": 0, "mode": "0644", "sha256": "b75d7f28...", "size": 10, "type": "file", "uid": 0}
```

From now on, "Buck2 got it right" means one thing: the manifest of the Buck2-built image is **IDENTICAL** to this one, path
for path and hash for hash. Why a manifest and not the raw image bytes is
[ADR-0006](../decisions/0006-golden-and-manifest-comparison.md): filesystem images contain incidental details (inode
numbers, allocation order) that say nothing about the contents.

## What you have now

- `golden/model.json`: the package graph, extracted from Buildroot;
- `BUCK` files: the graph as Buck2 targets (`//:rootfs` and one target per package);
- `golden/rootfs.manifest.json`: the answer key;
- tools and Buildroot fetched, but nothing yet built by Buck2.

The next three pages fill in the same question: **what runs inside a package's action?**

| | [Step 4: Wrapped](wrapped.md) | [Step 5: Stepped](stepped.md) | [Step 6: Native](native.md) |
|---|---|---|---|
| One action does | all of `make hello` | one Buildroot step | one small job (compile, link, install) |
| Buildroot's makefile runs | yes, whole | yes, one step at a time | no |
| Works for | every package | every package | packages that have a rule |
| Skips work when | the package's inputs are unchanged | a *step's* inputs are unchanged | a *job's* inputs are unchanged |
| Status | **works**; used for every project | **design only** | **works** for a set of packages |

[Continue to Step 4: Wrapped](wrapped.md){ .md-button }
