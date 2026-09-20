<title>ADR-0001</title>

# ADR-0001: One Buck2 target per Buildroot package

Status: accepted
Date: 2026-09-20

## Context

A Buildroot image is hundreds of packages, each with a build directory, dependencies
and an install step. Buck2 needs a unit of caching, scheduling and invalidation. The
candidates are the whole image (one action: a plain `make` in a box), one target per
*step* of every package (fetch, extract, patch, configure, build, install), or one target
per package.

## Decision

Every Buildroot package becomes one Buck2 target, generated from what Buildroot itself
reports (`make show-info`), placed in the directory where the package lives in the
Buildroot tree. Dependencies between targets are Buildroot's direct dependencies.
`//:rootfs` depends on all of them.

## Alternatives considered

- **One action for the whole image** - trivially correct, and useless: no reuse, no
  parallelism, any change rebuilds everything.
- **One target per package step** - the finest early cutoff, but Buildroot's steps share a
  mutable build directory, so every step would need to ship that directory between
  actions: a lot of data movement for tiny actions, and a much harder equivalence
  problem. Kept as a possible future *refinement* for selected packages (see
  [Wrapped and native](../concepts/wrapped-and-native.md)).

## Consequences

- **Easier**: the Buck2 graph mirrors Buildroot's, so a build failure names a package a
  Buildroot user already knows; `buck2 build //:rootfs` parallelizes across packages
  without Buildroot's experimental top-level parallel build.
- **Easier**: adding a package invalidates the new package and the rootfs, not existing
  packages (see [Architecture](../concepts/architecture.md#why-a-package-rebuilds-when-it-does)).
- **Harder**: a package is still a coarse unit. A one-line change in a large package
  reruns its whole `make`.
- **Harder**: the model is generated, so a change to Buildroot's package set means
  running `br2 extract` again; `br2 render --check` catches a stale model.
