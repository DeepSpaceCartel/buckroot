<title>ADR-0016</title>

# ADR-0016: One node pool, one server type, no taints

Status: accepted (amends [ADR-0015](0015-buildbarn-on-kubernetes.md))
Date: 2026-09-21

## Context

ADR-0015 planned a pool per purpose: a static platform node, cheap and dedicated-CPU worker pools with a taint only worker pods tolerate, and a
workspace pool. The first apply ran into the Hetzner project's limits: 5 servers and 8 dedicated vCPU, and a new account is refused a limit
increase ("your account is too new"). With the control plane, the platform node and one workspace node taken, a matrix of four cells got one
worker, the dedicated node sat idle and unremovable, and the node view showed five servers mostly doing nothing.

## Decision

- One server type for everything (`cpx51`: 16 shared vCPU, 32 GB), including the control plane, which is made schedulable.
- One autoscaled pool, 0..4, with no taints and nothing that selects a pool: platform pods, Coder and its workspaces, and Buildbarn workers all
  land wherever they fit.
- Two workers per node, each with a memory **limit** of 14 GiB: the build actions size `make -jN` from the container's memory, so a worker runs
  `-j7` and cannot take the other worker's memory (the OOM kills of ADR-0015's context were one `make` taking the whole machine).
- The chart keeps a second pool (`pools.dedicated`, dedicated-CPU nodes, one worker per node) switched off, for clean timings once the limit is raised.
  Until then a clean timing is one cell at a time on the shared pool.

## Consequences

- Every server is usable by whatever the cluster is doing; a matrix of four cells gets four workers on two nodes.
- Timings on shared vCPU are noisy, and two workers on a node contend for CPU: numbers from this cluster are comparable with each other, not with the
  single-machine baseline.
- The control plane shares its node with builds; etcd latency under load is a risk accepted for a development cluster with one control node.
- Nothing pins the stateful pods (storage, Postgres) to a node; their volumes are network volumes (hcloud CSI), so a pod can move.
