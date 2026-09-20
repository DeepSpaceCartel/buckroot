<title>Status and roadmap</title>

# Status and roadmap

## What works

- **helloworld**: the full matrix, 2 variants x 4 modes, every cell's manifest identical
  to the golden; the image boots in QEMU. See [Results](results.md).
- **superduperbird** (Spotify Car Thing): golden build; Buck2 `wrapped` build with an
  identical manifest (dev mode, local cache). The matrix is in progress.
- The remote stack: cache, scheduler, worker with a pinned tool baseline, portal.

## Known limits

| Limit | Why | Way out |
|---|---|---|
| Global config symbols and any infrastructure edit rebuild everything | every slice contains the global symbols | split global symbols by who reads them (rootfs-only groups) |
| Ambient host tools are not in the cache key | `wrapped` actions call `gcc`, `perl`, `rsync` | pin them in the worker image; put a tool-baseline digest into the key |
| Needs `CAP_SYS_ADMIN` | mount namespaces | a user-namespace variant, or a privileged runner |
| A package is a coarse unit | `wrapped` runs the whole `make <pkg>` | native rules; a stepped variant for selected packages |
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
- A third, *stepped* variant that maps Buildroot's own step targets
  (`<pkg>-extract`, `-patch`, ...) onto separate Buck2 actions: finer early cutoff without
  reimplementing package logic.
- Native rules for autotools and plain-`make` packages, not just install-only recipes.
- Deploy the Buildbarn stack on Kubernetes with autoscaled workers.
- Rename the internal `br2` names to `buckroot` (CLI, rules) once the interfaces settle.
