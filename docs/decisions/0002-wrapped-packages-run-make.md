<title>ADR-0002</title>

# ADR-0002: Wrapped packages run Buildroot's own make

Status: accepted
Date: 2026-09-20

## Context

Buildroot's package infrastructure (`autotools-package`, `cmake-package`, kernel and
toolchain packages, hooks, patches, `_POST_INSTALL_TARGET_HOOKS`) is thousands of lines
of make that encode years of accumulated build knowledge. A Buck2 rule set that
reimplements it will always trail Buildroot, and a project's own `.mk` files use all of
it.

## Decision

The default variant, `wrapped`, runs `make <pkg>` inside the Buck2 action, in a scratch
output tree seeded with the package's dependencies' outputs and its config slice. Buck2
owns the graph, ordering, parallelism, caching and remote execution; Buildroot owns *how* a
package is built. A `native` variant replaces selected packages with Buck2 actions that do
the work themselves, behind the same target label and artifact format, so the two
variants can be mixed per package and compared.

## Consequences

- **Easier**: every Buildroot package works on day one, including Mesa, vendor kernels and
  Rust host tools; the project's `.mk` files and hooks run unchanged.
- **Easier**: the `native` variant has an oracle. A native package's artifact is compared
  with the wrapped one (`compare-pkg.py`).
- **Harder**: the action is a black box to Buck2. Early cutoff is per package, and the
  action reads ambient host tools (`gcc`, `perl`, `rsync`) the cache key does not cover.
  Remote execution therefore needs a pinned worker image; see
  [ADR-0008](0008-buildbarn-backend.md).
- **Harder**: a wrapped action needs everything Buildroot's `make` expects to find: a
  configured output tree, stamps, the per-package directories. Faking that consistently is
  most of `pkg_action.py`.
