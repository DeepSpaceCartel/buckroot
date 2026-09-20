<title>ADR-0005</title>

# ADR-0005: Config slices by symbol ownership

Status: accepted
Date: 2026-09-20

## Context

The Buildroot `.config` is an input to every package. Declared whole, any change to
it - one new package - reruns every action. Worse, each action ran Kconfig's
`syncconfig` over the entire tree's `Config.in` files, which forced the whole tree into
every action's inputs.

## Decision

Each package receives a **slice** of the config: the lines whose symbol is global, owned
by the package's directory or its closure's, mentioned in its own `.mk`, referenced by the
infrastructure, or a `PROVIDES`/`HAS` option. Ownership comes from scanning every
`Config.in*` (`br2_owners`). Only `BR2_X=value` lines are kept. The slice ships with its
own `auto.conf`, so `syncconfig` never runs in a package action. The slice is a
deterministic tar, so an unchanged slice has an unchanged digest and Buck2's early cutoff
stops the invalidation there.

## Consequences

- **Easier**: adding a package, or flipping one package's option, rebuilds that package
  and the rootfs (measured: 43 s and 81 s against a 5 min cold build).
- **Easier**: no Kconfig, no `conf` binary and no `Config.in` files in a package action.
- **Harder**: the ownership rules are static analysis of Kconfig and `.mk` text, and can be
  wrong: a symbol read indirectly (through a make variable built by concatenation) is not
  seen. `check-narrow.py` validates the slices against the current configuration; it must
  be rerun after adding packages.
- **Deliberately conservative**: all global symbols reach every package. A change to
  the architecture or optimization level rebuilds everything. That is right, and
  refining it (rootfs-only symbol groups) is a possible optimization, not a soundness fix.
