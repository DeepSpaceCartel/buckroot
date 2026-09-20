<title>ADR-0004</title>

# ADR-0004: Fixed-path mount namespace

Status: accepted
Date: 2026-09-20

## Context

Buildroot bakes absolute build paths into the root filesystem itself:
`/usr/lib/libstdc++.so.6.0.32-gdb.py`, `/bin/busybox`, libtool `.la` files. Two builds of
the same source at different paths produce different filesystems. That would make every
cache key depend on where the repository is checked out, and rule out any comparison
between a local and a remote build.

## Decision

Every Buildroot invocation - golden build included - runs in a namespace where its inputs
are at fixed absolute paths: `/mnt/src` (Buildroot), `/mnt/external`, `/mnt/common`,
`/mnt/dl`, `/mnt/out`. `.git` is masked with an empty directory so `BR2_VERSION_FULL` and
`SOURCE_DATE_EPOCH` fall back to fixed values.

## Consequences

- **Easier**: the same tree at another absolute path gets the same cache hits (measured:
  61 of 61); a remote worker and a local machine produce the same bytes.
- **Easier**: read-only sources turn any write into the source tree into a loud error.
- **Harder**: requires `CAP_SYS_ADMIN` (see [ADR-0003](0003-enforced-input-views.md)).
- **Harder**: outputs contain `/mnt/out/...` paths, so anything that inspects them must expect
  those, and debugging on the host means re-entering the namespace.
