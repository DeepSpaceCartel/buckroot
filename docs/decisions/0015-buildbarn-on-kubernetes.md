<title>ADR-0015</title>

# ADR-0015: Buildbarn on a dedicated Kubernetes cluster with autoscaled worker pools

Status: accepted
Date: 2026-09-20

## Context

Remote execution on one 4-core machine takes about two hours per cold Car Thing cell, one action at a time, and 8 hours for a matrix. The worker's `concurrency`
had to be 1 because a single `make -j5` of GCC can exhaust 7.7 GB of memory (the OOM counter reached 6 across the remote cells). Buck2's `heavy` weight is a local hint and does
not apply to a remote worker. The wait on `re_queued` is the symptom of there being one worker slot.

## Decision

Run Buildbarn on a Kubernetes cluster dedicated to buckroot, on Hetzner Cloud (cheap, hourly billing), with:

- **Autoscaled, scale-to-zero worker pools**, one worker per node, on a node sized to hold a whole GCC build. Two pools, chosen per build by the instance name: shared vCPU (cheap, noisy) and dedicated vCPU (consistent, for measured runs).
- **An always-on platform node** for what has state or must be reachable: storage (persistent volumes), frontend, schedulers, portal, Coder, KEDA, Prometheus.
- **KEDA plus the node autoscaler**, scaling worker pods on the scheduler's queue depth and nodes on pending pods. Scale-in picks idle workers (a pod-deletion-cost annotation set by an idle reporter), so a running action is not killed.
- **Coder on the same cluster** for workspaces, using Coder's stock template with minimal changes; workspaces use remote modes only.
- **Terraform and one Helm chart in this repository** (`terraform/`, `charts/`), following the layout of an existing Hetzner Talos cluster (separate cluster and platform states), with the toolkit's Buildbarn jsonnet reused unchanged.

## Consequences

- **Easier**: many actions run in parallel with no queue wall; idle capacity costs nothing; the four-cell matrix can run at once instead of one after another; workers are as large as the biggest build needs.
- **Easier**: one configuration serves Docker Compose and Kubernetes (`env.libsonnet`), and the chart is checked in CI against the toolkit's files.
- **Harder**: a critical path of serial packages (the compiler chain, about an hour on 4 cores) does not shrink with more workers; only larger nodes help. The gain is in the wide part of the graph and in running cells side by side.
- **Harder**: scale-from-zero has a cold start (a server, Talos boot, a large image pull), so the scheduler's no-workers timeout must exceed it; this is not measured yet.
- **Harder**: workers are privileged pods (mount namespaces), which needs a Pod Security exemption in one namespace.
- **Risk**: the design has not been applied to a real project. The checks that could fail, and how to detect each, are listed in the [Kubernetes guide](../guides/kubernetes.md#risks-to-check-on-the-first-apply).
- **Deferred**: public access and client authentication, internal cluster security, and the golden build as a Job.
