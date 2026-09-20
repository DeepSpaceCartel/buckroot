<title>ADR-0008</title>

# ADR-0008: Buildbarn as the remote backend

Status: accepted
Date: 2026-09-20

## Context

Buck2 speaks the Remote Execution API (REAPI). Candidates for a self-hosted server
include Buildbarn, BuildBuddy, Bazel Remote (cache only), and NativeLink. The
experiment needs a cache and a scheduler with workers, on one machine to start and
deployable on Kubernetes later, and with a per-action inspection UI.

## Decision

Use **Buildbarn**, in a docker-compose stack trimmed from `buildbarn/bb-deployments`:
`frontend` (REAPI endpoint), one `storage` shard, `scheduler`, one `worker`, a privileged
`runner` container built from a pinned tool-baseline image, `bb-portal` and its Postgres
for inspection. A static platform key routes every action to the one worker pool.

## Consequences

- **Easier**: the components are separately scalable: more workers are more containers
  that register with the scheduler; the same configuration maps onto Kubernetes.
- **Easier**: the runner image is the single place to pin the host tools the wrapped
  actions use; see [Wrapped and native](../concepts/wrapped-and-native.md#the-host-tools-are-not-in-the-key).
- **Harder**: more moving parts than a cache-only server; real traps
  ([Remote cache and execution](../concepts/remote-cache-and-execution.md#configuration-traps)):
  gRPC message limits, the empty `Action.platform`, and worker state directories that must
  live outside the Buck2 project.
- **Harder**: Buildbarn's local storage ignores instance names, which forced
  [ADR-0010](0010-cache-salt-per-cell.md).
