<title>ADR-0003</title>

# ADR-0003: Enforced input views instead of declared inputs alone

Status: accepted
Date: 2026-09-20

## Context

To make a package's cache key depend only on what it uses, its declared inputs must be
narrow: its own directory and its dependencies', not the whole Buildroot tree. But Buck2
executes local actions unsandboxed. A narrow *declaration* proves nothing: the action
can still read the whole checkout, and a change to a file it read but did not declare is a
stale cache hit that produces a wrong image with no error.

## Decision

Package actions run in a private mount namespace where the Buildroot tree, the external
tree and `common/` are **built from an allow-list**: infrastructure plus the package
directories of the closure, each bind-mounted read-only. An undeclared read is `ENOENT`.
The same declaration feeds the Buck2 input list, so the enforced view and the
declared inputs cannot drift apart.

## Consequences

- **Easier**: soundness is checked by the system: hidden cross-package references
  (`busybox` reading `procps-ng`, `gettext-tiny` reading `gettext-gnu`) fail loudly the
  first time instead of going stale; `br2 preflight` and `check-narrow.py` find them in
  minutes.
- **Easier**: the same view is what a remote worker has, so a build that passes locally
  has already proven its inputs are sufficient for remote execution.
- **Harder**: each hidden reference has to be declared (`extra_view`), one project at a
  time.
- **Harder**: the namespace needs `CAP_SYS_ADMIN`, which rules out unprivileged CI
  runners and some container setups.
