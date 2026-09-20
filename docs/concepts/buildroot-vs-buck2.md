<title>Buildroot vs. Buck2</title>

# Buildroot vs. Buck2

Why moving a Buildroot project to Buck2 is not a syntax translation, and how each
Buildroot concept maps onto Buck2. This is the background to the design decisions;
[Architecture](architecture.md) is how buckroot puts it together.

## Buildroot's model

Makefile-driven, package-centric, operationally coarse. `package/*/*.mk` files are the
build logic per package; the steps run roughly `source -> depends -> extract -> patch ->
configure -> build -> install`. `output/host` holds host tools plus the target sysroot;
`output/staging` is a compatibility symlink to that sysroot; `output/target` is the
near-final root filesystem (not a deployable chroot); `output/images` holds the
deliverables. Patches come from package-local directories or `BR2_GLOBAL_PATCH_DIR`.

- Top-level parallel build is still an experimental mode with sharp edges.
- Incremental rebuilds are package-scoped and coarse: a dependency's *configuration*
  change does not reliably rebuild its dependents.
- Reproducibility leans on hashes, pinned sources and caches (`DL_DIR`, ccache), but the
  model underneath is still "mutable build trees plus convention".

## Buck2's model

Graph-first. `BUCK` files declare targets; Buck2 analyzes them into a dependency graph,
turns them into actions, and executes only what is needed, locally or remotely. A rule
transforms declared inputs into declared outputs, package boundaries are explicit,
the graph is acyclic, and toolchains and platforms are explicit rather than ambient host
state. **Configuration is part of a configured target's identity**, so variants coexist by
construction. The design leans on hermeticity, action digests, content-addressed storage
and action-cache hits; remote execution is first-class.

## The core mismatch

Buildroot lets a package rely, implicitly, on whatever earlier steps left in `host/`,
`staging/` or the target tree. Buck2 makes every dependency explicit - good for
correctness, but it exposes a great deal of hidden coupling that Buildroot tolerated
silently. For each package the migration question is: does this become a target, a rule,
an action, a toolchain, a configuration, or a generated artifact?

## Concept mapping

| Buildroot | Buck2 | The problem | Solution shape |
|---|---|---|---|
| `.mk` package file | `BUCK` target + rule | metadata, steps, side effects and conditionals in one file | generate one target per package; keep the `.mk` for the `wrapped` variant |
| `Config.in` | `.buckconfig`, platforms, constraints | menu-driven global config vs. graph-scoped, variant-aware config | [config slices](views-and-slices.md#config-slices) per package |
| `*_DEPENDENCIES` | `deps` | often means "must exist before I run", not "is an input" | dependencies become artifacts a package's action consumes |
| source -> patch -> configure -> build -> install | actions | Buck2 does not want a long imperative pipeline as one node | one action per package (wrapped), or one per step ([native](wrapped-and-native.md)) |
| `DL_DIR` | fetched artifacts with hashes | filesystem-based, package-level caching | [vendored sources](../decisions/0007-vendored-sources.md) with recorded digests |
| package patches | patch action / pre-patched source | search-path and ordering conventions | patch directories are declared inputs; verified by `br2 preflight` |
| `host-*` packages | exec tools / toolchain deps | host tools and target artifacts share a tree but differ in role | separate `host` and `target` trees in each package's artifact |
| `output/host` + sysroot | toolchain outputs | a shared mutable directory | per-package directories, merged only in the rootfs action |
| `output/staging` | none | a compatibility alias | dropped |
| `output/target` | rootfs action inputs | a partially finalized filesystem | explicit `br2_rootfs` action |
| `output/images` | final artifacts | maps cleanly | top-level deliverable |
| parallel build | native graph parallelism | Buildroot's is partial | let the graph drive it; weights for heavy packages |
| ccache, download cache | action cache + CAS | best effort | deterministic action keys, content addressing |
| hidden coupling through staging | explicit input edges | works because something else happened earlier | enforced [views](views-and-slices.md#views): fail loudly |

## Semantic differences that matter

- **Package-oriented vs. action-oriented.** One Buildroot package can become several
  Buck2 targets or actions.
- **Dependency declarations do not guarantee rebuilds** in Buildroot. In Buck2, if an
  action's inputs change, its key changes and it reruns. A distributed Buildroot cache
  needs exactly this discipline; Buck2 puts it in the graph instead of an external policy.
- **Shared directories vs. artifacts.** Buck2 does not care what is currently in a
  directory; the declared inputs and outputs are the contract.
- **Convention-based vs. modeled patching.** The question is where patch application
  lives in the graph and what its identity is.
- **Global vs. variant-driven configuration.** Buildroot asks "what is *the* system
  configuration"; Buck2 asks "what configuration produces *this* target variant".

## Migration problems and patterns

- **Dependency modelling** - separate build-time tools from runtime libraries, generated
  inputs and patch-time dependencies; make hidden coupling visible.
- **Package conversion** - thousands of packages cannot be converted one by one; classify
  them first (trivial, generator-heavy, patch-heavy, host-only, custom build logic,
  ambient-state-dependent) and migrate by class. buckroot's `wrapped` variant is the
  "convert everything at once, refine later" answer.
- **External sources** - explicit hashed artifacts; no unpinned mutable VCS state.
- **Cross-compilation** - separate execution tools from target toolchains.
- **Reproducibility and caching** - every action deterministic; any ambient filesystem
  dependency is a bug. Buildroot bakes absolute build paths into the rootfs, hence the
  [fixed-path namespace](../decisions/0004-fixed-path-namespace.md).
- **Remote-execution readiness** - hermetic, serializable actions; eliminate local
  paths and undeclared host tools.
- **Validation** - equivalence at several levels: package artifact, rootfs contents,
  image hashes, boot behaviour. See [Verification](verification.md).
- **Rollout** - both systems in parallel during the transition; the golden build stays
  the reference.
- **Debugging** - be able to inspect the exact command, inputs and outputs of every
  action. See [Debugging](../guides/debugging.md).
