<title>Importing from Buildroot</title>

# Importing from Buildroot

The long-term direction: stop *running* Buildroot, keep *using* it. Package builds become native
Buck2 targets, and Buildroot stays as a pinned source of package knowledge: versions, source URLs and
hashes, patches, dependencies, licenses. This page is the design sketch; it is not implemented as
described, and the [roadmap](../project/status.md) says where each part stands.

## What can be imported, and what cannot

| From Buildroot | Importable as data | Where it is today |
|---|---|---|
| version, download URLs, SHA-256/512 | yes | already in `golden/model.json` and `golden/sources.lock.json` |
| patches (`package/<pkg>/*.patch`, `BR2_GLOBAL_PATCH_DIR`) | yes, as files | applied by Buildroot inside wrapped actions; declared as view inputs |
| direct dependencies, virtual-package choices | yes | in the model; they become `deps` |
| licenses and license files | yes | reported by `show-info`; not yet emitted |
| `Config.in` symbols | yes, as ownership | used for [config slices](views-and-slices.md#config-slices) |
| `<PKG>_CONF_OPTS`, `_MAKE_OPTS`, `_CONF_ENV` as *evaluated for one configuration* | yes, frozen | not yet extracted; Buildroot can print them (`printvars`) |
| the recipe itself: hooks, `$(call ...)` macros, conditionals | no | stays in `.mk`; must be rewritten as rules or recipes |

The split is the design: **data imports, logic does not.** Buildroot's package infrastructure
(autotools, cmake, meson, kernel, toolchain) is a few dozen generic recipes plus per-package hooks. The
generic recipes become Buck2 rules once; the hooks are the long tail that the
[native](wrapped-and-native.md) variant is already replacing one package at a time.

## Sketch

1. **Buildroot as a pinned external cell.** Buck2 can fetch another repository as a cell
   (`[external_cells]`; the prelude is one). A pinned Buildroot tag, as a cell or as an `http_archive`
   of its release tarball, lets targets refer to patches by label instead of copying them:
   `patches = ["@buildroot//package/busybox:0001-fix.patch"]`. Upgrading Buildroot is changing the pin
   and regenerating. (The `git` origin for external cells is newer than `bundled`; the archive route
   works with what is proven here.)
2. **An importer.** `br2 import <pkg>` generates a native target from the model: an `http_archive` with
   the recorded hash, the imported patches, the dependencies as native labels, and one of the generic
   build-system rules with the *frozen* option lists as arguments. Buildroot is used as an
   **evaluator at generation time** (it already answers `show-info` and `printvars` for a configuration)
   and is not needed at build time.
3. **Overrides.** A project's own patches and version pins layer on top of the imported ones, in the
   experiment's `native/<pkg>/BUCK`, without editing anything imported.
4. **Oracle.** Each imported package is checked against the wrapped build of the same package with
   `compare-pkg.py` (files, modes, hashes, stamps), and the image against the golden manifest. That is
   how the [verification](verification.md) layers already work.
5. **Retire Buildroot per package.** When every package in a project is native, the wrapped variant
   and the mount-namespace views are no longer used. The Buildroot cell stays as data.

## What it costs

- **Frozen options go stale.** They are evaluated for one configuration, so a `defconfig` change means
  re-running the import; this is the same loop as `br2 extract` today.
- **Hooks do not import.** Post-install hooks, `sed` in `_POST_PATCH_HOOKS`, target-finalize steps:
  each needs a Buck2 rule or a recipe like the ones in `toolkit/br2/native/`. The
  [tuple bug](wrapped-and-native.md#the-artifact-format-is-an-interface) shows how a recipe written
  for one configuration fails on another, so recipes must raise on what they do not implement.
- **The tool baseline moves.** Wrapped actions rely on the pinned worker image for host tools; native
  ones must name their toolchains as Buck2 toolchains, which is more work and the actual hermeticity win.
- **Buildroot's own quirks come along** (`-dirty` versions, generated files with build paths) until each
  is reproduced or dropped deliberately.
