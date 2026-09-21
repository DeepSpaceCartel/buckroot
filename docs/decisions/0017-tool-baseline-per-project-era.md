<title>ADR-0017</title>

# ADR-0017: A project names the tool baseline of its era

Status: accepted (extends [ADR-0013](0013-worker-image-is-the-tool-baseline.md))
Date: 2026-09-21

## Context

FunKey-OS pins the FunKey fork of Buildroot 2021.02. Its host packages predate glibc 2.34: `host-m4` 1.4.18 fails on any current host
(gnulib's `SIGSTKSZ` test), and Buildroot's own 2021.02.x stable series had to patch m4, bison and fakeroot for the same reason. The
golden build failed there on the cluster (ubuntu:24.04 worker image), and a `wrapped` Buck2 build would fail identically. Two ways out:
back-port host-package patches into the project (a global patch directory that every package action would have to see, which the
toolkit does not support, and a deviation from the project as published), or build the project with host tools of its own time.

## Decision

- The worker image is built in **variants** from one Dockerfile (`BASE`, and optionally a vendor SDK at its documented path): `latest` (ubuntu:24.04),
  `ubuntu20.04` (glibc 2.31, gcc 9) and `funkey` (ubuntu:20.04 plus the released FunKey SDK at `/opt/FunKey-sdk-2.1.0`, whose `.la` files name that
  path), published by CI as `buckroot-worker:<tag>`.
- A project may name its baseline in `project.json` (`"baseline": "funkey"`). `br2` then sends its remote actions to the **`legacy` worker
  pool** (instance-name prefix `legacy/`, workers running that image) and runs its golden Job in the same image, so golden and Buck2 builds
  still share one baseline (ADR-0013). Everything else is unchanged; no patches are applied to the project.
- The chart's pools take a per-pool `worker.image`; the `legacy` pool is enabled with zero replicas until a build needs it.

## Consequences

- Old projects build as published; the "vanilla" property of the golden is kept.
- A second image to maintain, and a second scheduler/pool. A project's era is declared, not detected: a wrong baseline shows up as a build failure.
- The baseline is still not part of the action key ([design note](../design/worker-environment-in-the-key.md)): two projects with different
  baselines must not share cache entries for the same action, which the instance-name prefix guarantees today only because the cache is
  keyed by content and the actions differ in inputs; the identity gap noted in ADR-0013 remains.
