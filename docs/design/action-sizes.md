<title>Action sizes and execution platforms</title>

# Action sizes and execution platforms

*Status: proposed. Nothing on this page is implemented. The measurements and findings 1 to 3 under
[What Buck2 and Buildbarn allow](#what-buck2-and-buildbarn-allow) are verified on the running cluster; the rest is a plan.*

## The problem

Every Buildbarn worker is the same size: 4.5 vCPU and 9 GiB requested (`pools.shared.worker.resources`), one action at a time. Kubernetes places
pods by what they **request**, so three workers fill a 16 vCPU, 32 GB node while the cluster shows 30% CPU and 6% memory in use. Most actions
need a fraction of a worker, and a few need more than one.

## Evidence

2,513 actions from 5 projects, read from Buildbarn's action results ([how](../guides/action-resource-usage.md)). Cores are CPU seconds over wall
seconds while the action ran; memory is the largest single process.

| Action wall time | Actions | Share of wall time | Avg cores | p90 cores | Largest process |
|---|---|---|---|---|---|
| under 5 s | 1,633 | 2% | 0.91 | 0.98 | 0.09 GiB |
| 5 to 20 s | 535 | 22% | 1.29 | 2.03 | 0.33 GiB |
| 20 to 60 s | 258 | 30% | 1.91 | 3.31 | 0.23 GiB |
| 60 to 300 s | 79 | 37% | 5.78 | 9.11 | 1.33 GiB |
| over 300 s | 8 | 9% | 5.09 | 5.53 | 1.33 GiB |

- **Two populations.** 96.5% of actions run under a minute and average one to two cores. The other 87 take 46% of the running time and
  average 5 to 6 cores; 75 of them averaged more than the 4.5 cores a worker requests (`host-cmake`, `host-gcc-initial`, `host-gcc-final`, `glibc`).
- **Memory is not the constraint.** The largest single process was 1.33 GiB. One worker container peaked at 4.3 GiB (all its processes, `-j4`)
  and at 13 cores (no CPU limit, so it can burst).
- **Nothing was killed for memory** on this cluster: no `OOMKilled`, no `container_oom_events_total`, no action ended on a signal. The kills that
  set `concurrency: 1` happened on the old 7.7 GB machine ([ADR-0015](../decisions/0015-buildbarn-on-kubernetes.md)).
- The longest single action was 350 s. ADR-0015's "the compiler chain, about an hour" is the chain end to end, not one action.

Two shapes fit this: a **small** worker for almost everything and a **big** one for the compiler chain and a few others.

## What Buck2 and Buildbarn allow

Checked against the Buck2 release pinned in `fetch-buck2.sh` (2026-09-15) and the `bb-remote-execution` commit of the chart's scheduler image (`c48dcda`).

1. **Buck2 puts the platform in `Command.platform`, not in `Action.platform`.** Reading the stored `Action` and `Command` of a `host-gcc-final`
   action from the CAS: the Action has only `command_digest` and `input_root_digest`; the Command carries `OSFamily` and `container-image`.
   The properties of `br2_execution_platform.remote_execution_properties` therefore reach the server, but in the older place.
2. **The scheduler reads only `Action.platform`.** Its `platformKeyExtractor` is `action` (from the Action) or `static` (one fixed platform).
   The variant that fell back to the Command (`action_and_command`) is removed in this version. This is why
   [scheduler.jsonnet](../../charts/buckroot-buildbarn/files/config/scheduler.jsonnet) uses `static`, and it means that **per-action routing on a
   platform property does not work as configured**.
3. **Size classes cannot learn here.** The feedback-driven analyzer keys on an action's command line and environment. In this project both change
   for every measured cell: the environment carries `BR2_CACHE_SALT` (ADR-0010) and the arguments carry the isolation directory
   (`buck-out/wrapped-remote-cache/art/...`). Every cell would look new to the analyzer. It also needs an Initial Size Class Cache store that is
   not configured, and its fallback is to rerun a failed action on the largest class, which doubles a failing hour-long package.
4. **The scheduler can call out to a router.** `actionRouter: { remote: { grpcClient, initialSizeClassAnalyzer } }` sends every action to a gRPC
   service (`buildbarn.remoteactionrouter.ActionRouter/RouteAction`) that returns the action with any field changed, usually the platform, plus
   invocation keys. The request holds the Action (so the digests) and the request metadata (invocation ids; in the stored results Buck2's metadata carries only the tool name and the invocation id, no target or mnemonic).
5. **Buck2 can choose an execution platform per target**, with `exec_compatible_with` and a constraint. This is the standard mechanism; to be
   verified against the toolkit's prelude and the `br2_*` rules.

## Options

| | How the size reaches the worker | Verdict |
|---|---|---|
| A. Platform property, scheduler reads it directly | needs `Action.platform`, which Buck2 does not send | blocked by findings 1 and 2 |
| B. Feedback-driven size classes | the scheduler learns from timings | does not learn here (finding 3); no |
| C. **Router shim** | exec platforms in BUCK put `size` in `Command.platform`; a small service copies it to `Action.platform` | proposed |
| D. Router with its own table | the service maps package to size; BUCK files carry nothing | fallback if a size must stay out of the cache key |
| E. Two builds, heavy targets first, `--pool big` | the instance-name prefix selects a pool | a barrier in the graph, and action results are per instance; no |

## Proposal (option C)

**Sizes are decided in the project and written into the BUCK files; Buildbarn only routes them.** A size becomes a platform property, and a
small service makes Buildbarn see it.

### In `project.json` and the generated BUCK files

Reuse what exists: `heavy` already lists the packages that must not share a machine. Its meaning widens to "runs on the big shape":

```json
{ "heavy": ["host-gcc-initial", "host-gcc-final", "host-cmake", "glibc", "linux"] }
```

The toolkit defines the platforms once (today it defines one, in `platforms/BUCK` through `br2_execution_platform`):

```python
# toolkit platforms/BUCK (sketch)
constraint_setting(name = "size")
constraint_value(name = "small", constraint_setting = ":size")
constraint_value(name = "big", constraint_setting = ":size")

br2_execution_platform(
    name = "exec_small",
    size = ":small",                       # new attribute: adds the constraint to the platform's configuration
    remote_execution_properties = {"OSFamily": "linux", "container-image": "docker://buckroot-worker", "size": "small"},
    ...,                                   # the rest as today
)
br2_execution_platform(name = "exec_big", size = ":big", remote_execution_properties = {..., "size": "big"}, ...)

execution_platforms(name = "default", platforms = [":exec_small", ":exec_big"])   # small first: the default for unconstrained targets
```

`br2buck.py` emits one attribute for a heavy package, and nothing for the others:

```python
br2_package(
    name = "host-gcc-final",
    exec_compatible_with = ["root//platforms:big"],    # from project.json "heavy"
    weight = 8,                                       # unchanged: the local CPU-slot hint
    ...
)
```

`.buckconfig` keeps `execution_platforms = root//platforms:default`. Local runs ignore the property (it only matters in the remote properties).

### The router

A small stateless gRPC service in front of the scheduler: for each action it reads the `Command` from the CAS, copies
`Command.platform` into `Action.platform`, and returns it with an invocation key taken from the request metadata (so fairness between builds is
unchanged). It changes nothing else. Two replicas; it is in the path of every action, so it must stay up.

### Workers, chart and scaling

- The scheduler's `platformKeyExtractor` becomes `action: {}`. Workers register the same properties as the actions: `OSFamily`, `container-image`
  and `size`. The match is exact, so **every worker must advertise `size`**.
- Each pool splits into two Deployments on the same scheduler, `worker-shared-small` and `worker-shared-big`, with their own KEDA scaler. The
  queue-depth query already has a `platform` label, so each scaler filters on `platform=~".*size.*small.*"` (the exact expression to be tested).
- Starting shapes, to be checked in step 3 of the plan, not decided. Concurrency stays 1; `make -jN` keeps being derived from the memory limit
  (about 2 GiB per job, `br2/pkg_action.py`).

| Shape | CPU request | Memory request / limit | `-jN` | Fits on a 16 vCPU node |
|---|---|---|---|---|
| small | 1.5 vCPU | 2 GiB / 4 GiB | 2 | about 8 next to the platform pods |
| big | 6 vCPU | 8 GiB / 12 GiB | 6 | 2 |

CPU has no limit, as now, so a small worker can burst into an idle node and a big one to about the 9 to 13 cores measured.

## Consequences

- **Easier**: the reserved capacity follows the demand: about 96% of actions fit the small shape, which holds about eight to a node against three
  today, and the compiler chain stops running on less than it uses.
- **Easier**: sizes sit next to the rest of the project's definition (`project.json`, BUCK), not in cluster configuration.
- **Harder**: the platform properties are part of the action key, so changing a package's size invalidates its cache entries. Sizes should
  change rarely; option D avoids it at the cost of BUCK files that do not show where a package runs.
- **Harder**: a new service on the critical path of every action, and a chart with pools times shapes.
- **Harder**: two shapes means a package that is in the wrong one runs badly, not fails. Only the small shape can OOM; [finding](../guides/action-resource-usage.md#was-something-killed-for-memory) it with `termination_signal` and the container counters.
- Timings from before and after are not comparable, as with ADR-0016.

## Unknowns

1. Does the scheduler pass the router's `Action` through unchanged to the worker, and does the worker accept an Action whose platform differs
   from the digest it holds? (The worker fetches the original Action by digest; the scheduler queues by the router's platform.)
2. The invocation key: the response needs a non-empty `invocation_keys` list of `Any`; which message type the scheduler expects has to be read from
   its source before writing the service.
3. `exec_compatible_with` on the `br2_*` rules, and whether a second execution platform disturbs the local modes or the `wrapped`/`native` toolchain
   resolution.
4. The real per-package sizes: the 87 heavy actions come from five projects with different toolchains. The list is built from data, not by hand:
   `br2-usage.py` over the matrix logs gives the packages above about 4 cores or 60 s.
5. Whether the platform in `Command` changes any local cache key (it should not).

## Plan

1. **Prove the routing** on the cluster with throwaway pieces: the router, two worker Deployments with `size`, and a hand-edited platform. A
   build must run heavy actions on big workers. The result's `execution_metadata.worker` names the pod, which shows where each action ran.
2. **Buck2 side**: the platforms, `exec_compatible_with` from `heavy`, `br2buck.py`, and a check that local modes and golden manifests are unchanged.
3. **Chart and scaling**: pools times shapes, per-shape KEDA queries; start from the table above, adjust from a matrix run.
4. **Measure**: the same matrix before and after. Compare node-hours and requested versus used CPU (the guide's queries), and require no
   `OOMKilled` and no `KILL`.
5. **Record**: an ADR once step 4 holds, and the numbers in [Results](../project/results.md).

## Where it fits

After the worker environment work in [Worker environment in the key](worker-environment-in-the-key.md): both put a property into the platform, so
they should be designed together, and a `baseline` property would sit beside `size`. A first, independent step needs no design at all: lowering the
requests of the single shared worker (about 2 vCPU and 5 GiB, limit unchanged) roughly doubles what a node holds while this is built.
