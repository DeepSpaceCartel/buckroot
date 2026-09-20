<title>Status and roadmap</title>

# Status and roadmap

## What works

- **helloworld**: the full matrix, 2 variants x 4 modes, every cell's manifest identical
  to the golden; the image boots in QEMU. See [Results](results.md).
- **superduperbird** (Spotify Car Thing): golden build; `native` and `wrapped` local cells and the
  `native` local-cache cells (cold and warm) all with an identical manifest. The rest of the matrix is
  in progress; see [Results](results.md).
- The remote stack: cache, scheduler, worker with a pinned tool baseline, portal.

## Known limits

| Limit | Why | Way out |
|---|---|---|
| Global config symbols and any infrastructure edit rebuild everything | every slice contains the global symbols | split global symbols by who reads them (rootfs-only groups) |
| Ambient host tools are not in the cache key | `wrapped` actions call `gcc`, `perl`, `rsync`, and `configure` scripts probe the host (OpenSSH embeds the path of `xauth` if it finds one) | pin them in the worker image, and put a **baseline identity** into the key (a platform property, the hash of `runner/Dockerfile`) so a changed image is a cache miss; local execution can only declare a baseline, not verify it; see the [design note](../design/worker-environment-in-the-key.md) |
| Needs `CAP_SYS_ADMIN` | mount namespaces | a user-namespace variant, or a privileged runner |
| A package is a coarse unit | `wrapped` runs the whole `make <pkg>` | native rules; possibly a two-stage stepped variant, after a measurement (see [Stepped](../walkthrough/stepped.md)) |
| Package outputs are tarballs | one opaque blob per package: any change re-uploads all of it, identical files in different packages or projects are stored again, and every action unpacks its dependencies' tarballs | [directory-tree outputs](#directory-tree-package-outputs) (an idea, untested) |
| Static slicing can miss an indirect config read | text analysis of `.mk` files | `check-narrow.py` after every configuration change |
| A native rule reproduces a Buildroot make macro by hand | it can drift from Buildroot | `compare-pkg.py` against the wrapped artifact; recipes raise on configurations they do not implement |
| Numbers are from one 4-core machine | the worker shares the CPUs | repeat with separate worker hardware |

## Roadmap

Real projects, smallest first. Each is its own directory under `experiments/` with a
`project.json`, a golden build and a matrix.

| Project | Notes | State |
|---|---|---|
| helloworld | the toolkit's development example | done |
| Spotify Car Thing (superbird) | `BR2_EXTERNAL`, glibc, vendor kernel, Mesa, Rust host tools | matrix in progress |
| FunKey-OS | Buildroot submodule plus a `FunKey/` external tree, `funkey_defconfig` | next |
| Home Assistant OS | Buildroot submodule plus `buildroot-external` | planned |
| OpenVoiceOS, Batocera, Recalbox | larger, several boards each | planned |

Toolkit work:

- Keep each package's `make.log` as an addressable Buck2 output so a failure's log is
  one command away, on a remote worker too.
- A third, *stepped* variant that maps Buildroot's own step targets onto separate Buck2 actions. The
  [analysis](../walkthrough/stepped.md#the-state-problem-with-numbers) says five steps would move too much state; the
  candidate is a **two-stage** split (source preparation, then build), gated on a measurement.
- [Directory-tree package outputs](#directory-tree-package-outputs), below.
- Native rules for autotools and plain-`make` packages, not just install-only recipes.
- Importing Buildroot package data (patches, hashes, frozen option lists) into native targets, with
  Buildroot as a pinned source of package knowledge; see [Importing from Buildroot](../concepts/importing-from-buildroot.md).
- Trim oversized sources such as `googlefontdirectory` (965 MB for one 3 MB font family). Vendoring a trimmed archive would leave the image identical
  but needs a documented hash policy, since Buildroot's `.hash` file names the original archive. Not urgent: the cost is paid once per cache.
- Apply and measure the Kubernetes deployment (`terraform/`, `charts/`): written and validated, not yet run on a real cluster; see the [guide](../guides/kubernetes.md).
- Rename the internal `br2` names to `buckroot` (CLI, rules) once the interfaces settle.

## Directory-tree package outputs

*A note for later. This is an idea with supporting numbers, not a decision and not implemented.*

**Today** every package's result is one tarball: the files the package installed, plus its stamps. Buck2 stores it in the
cache as a single blob, and every action that depends on the package unpacks it into a scratch directory.

**The idea:** declare the result as a *directory* output instead, so the cache stores it as a tree of individually hashed files.

**What it would improve, for both `wrapped` and `native`:**

- *Deduplication.* Identical files across packages, across configurations and across projects are stored once. Any change to a
  package re-uploads only the files that changed, not the whole tarball. Today a rebuilt compiler package uploads all of its
  gigabytes again.
- *Cheaper consumption.* A worker can link an already cached tree into an action's input directory instead of unpacking a tarball
  per action. Measured cost of unpacking today: the 379 MB `helloworld` toolchain is unpacked for every action that depends on it,
  including a package that runs for about 7 seconds.
- *A cheaper two-stage stepped variant.* The per-stage state (a source tree, then a built tree) would share almost all of its files
  with the previous stage, so only new files would add bytes. See [Stepped](../walkthrough/stepped.md#how-the-state-cost-could-be-reduced).

**Evidence so far** (Car Thing and `helloworld`, measured; details on [Package output sizes](../concepts/package-output-sizes.md)): the largest package outputs are legitimate payload, not duplication
(`host-rust-bin` 751 MB of which about 30 MB is repeated content; the Bootlin toolchain 379 MB); ordinary host packages carry only
their own files; and source trees are 9 to 11 times larger than their archives (`gcc`: 84 MB to 758 MiB; `mesa3d`: 20 MB to
227 MiB). Across the 98 Car Thing actions the dependency tarballs to unpack add up to 5.0 GB, against 1.11 GB of distinct output. What is *not*
measured: how many bytes of tarballs are content shared between packages, and whether Buildroot's path-rewriting of inherited text
files explains the roughly 4 to 11 MB that packages with large closures carry.

**Risks to test first:**

1. **Hard links.** Buildroot's per-package directories rely on them (an inherited file shares an inode with the dependency's copy),
   and the current delta detection uses inode identity. Directory outputs may not preserve them.
2. **Dangling symbolic links.** Buck2 cannot see them as *inputs* (they are why the renderer records them as data), and it is not
   known how it treats them inside an *output* tree. Tarballs carry them without any trouble; that is one reason tarballs were used.
3. **Modes, owners and timestamps.** The image depends on file modes and (for `BR2_REPRODUCIBLE`) timestamps; the manifest must
   stay IDENTICAL.
4. **Writable copies.** A build needs to write into its scratch tree, while cached trees are read-only. The saving depends on a cheap
   copy-on-write step (hard-link farm, reflink or overlay); a plain copy would give back much of it.

**How to test it cheaply:** prototype on `helloworld` only, for the packages that carry the size (the toolchain, then the rest).
Compare, between the tarball and the tree version, (a) bytes uploaded in a cold `local-cache` run, (b) bytes downloaded in the warm run,
(c) action time, and (d) the manifest against the golden. Accept it only if (d) is IDENTICAL and (a) to (c) improve; then repeat on
the Car Thing before adopting it.

**Depends on / unblocks:** it is independent of the toolkit refactor phase, but a change to the artifact format touches most of
`pkg_action.py`, so it belongs after the characterization tests exist. It is a prerequisite for a two-stage stepped variant to be worth
building.
