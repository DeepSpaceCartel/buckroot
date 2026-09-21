<title>Finding what an action used</title>

# Finding what an action used

How much CPU and memory did a remote action use? You need this to size workers, to choose which packages are
heavy, and to tell whether an action was killed for lack of memory.

**Buck2 will not tell you.** The `execution_stats` in its event log are placeholders for remote actions
(`memory_peak: 0`, every CPU counter `null`; checked on 2,596 events in 23 logs). The numbers are in
**Buildbarn's action results**: the worker measures every action it runs and stores the usage next to the
result in the action cache.

## What is recorded

For every executed action the worker stores, in the `ActionResult`'s `execution_metadata`:

| Field | Meaning |
|---|---|
| `virtualExecutionDuration` | wall time of the command on the worker |
| `queuedTimestamp` … `outputUploadCompletedTimestamp` | when it queued, started, fetched inputs, ran and uploaded |
| `POSIXResourceUsage.user_time`, `system_time` | CPU seconds of the command and its children (`ru_utime`, `ru_stime`) |
| `POSIXResourceUsage.maximum_resident_set_size` | peak memory in bytes (`ru_maxrss`) of the **largest single process** |
| `POSIXResourceUsage.termination_signal` | `KILL`, `SEGV` and so on when the command ended on a signal; empty otherwise |
| page faults, block I/O, context switches | the rest of `struct rusage` |

Average cores are CPU seconds divided by wall seconds. Peak memory is **not** the total: a `make -j4` that runs
four compilers reports the biggest one. For a whole worker, use the container numbers in
[Per worker instead of per action](#per-worker-instead-of-per-action).

The message definitions are in
[`resourceusage.proto`](https://github.com/buildbarn/bb-remote-execution/blob/main/pkg/proto/resourceusage/resourceusage.proto).

## Before you start

1. **`grpcurl`.** Install it once, checking the checksum:

    ```bash
    V=1.9.3; cd "$(mktemp -d)"
    curl -sSfL -O https://github.com/fullstorydev/grpcurl/releases/download/v$V/grpcurl_${V}_linux_x86_64.tar.gz \
                -O https://github.com/fullstorydev/grpcurl/releases/download/v$V/grpcurl_${V}_checksums.txt
    grep linux_x86_64 grpcurl_${V}_checksums.txt | sha256sum -c -
    tar xzf grpcurl_${V}_linux_x86_64.tar.gz grpcurl && sudo install grpcurl /usr/local/bin/
    ```

2. **Reach the Buildbarn frontend.** From a machine with cluster access:

    ```bash
    kubectl -n buildbarn port-forward svc/frontend 8980:8980 &
    grpcurl -plaintext localhost:8980 list      # lists ActionCache, ContentAddressableStorage, Execution, ...
    ```

    From a Coder workspace or a tailnet machine, use the endpoint in `BR2_RE_ENDPOINT` instead of `localhost:8980`.

3. **The instance name.** Results are stored per REAPI instance name, and an empty name finds nothing. It is
   `instance_name` in the project's `.buckconfig`:

    ```bash
    grep instance_name experiments/qemu-x86_64/.buckconfig      # instance_name = qemu-x86_64
    ```

    `br2 build --pool P` prefixes the name with `P/` (see `instance()` in `scripts/br2`); pass the name the run used with `--instance`.

## Look at a build

`scripts/br2-usage.py` takes the remote actions of Buck2 event logs, looks each one up in the action cache and
prints a summary. It lives in the toolkit's `scripts/` (`toolkit/bin/br2-sync` copies it into an experiment). Run it from the
experiment directory; it reads the instance name from `.buckconfig` and the Buck2 binary from `tools/buck2`:

```bash
cd experiments/qemu-x86_64
scripts/br2-usage.py --log buck-out/wrapped-remote-cache/log/*_build_*_events.pb.zst
```

```
126 of 127 actions have a stored result | wall 0.45 h | cpu 1.84 h | average 4.08 cores while running

   wall time  actions  % of wall  avg cores  p90 cores  max RSS GiB
       0-5 s       78        2.1       0.92       0.98         0.07
      5-20 s       32       21.0       1.38       2.06         0.23
     20-60 s       11       23.4       2.16       3.26         0.18
    60-300 s        5       53.4       6.11       7.92         1.33

actions that ended on a signal: 0

longest 10:
id                               category         wall s  cores  RSS GiB  signal
host-gcc-final                   br2_package       254.1   5.65     1.33
host-cmake                       br2_package       212.0   7.92     0.50
...
```

Useful variations:

```bash
# only the long actions, more of them
scripts/br2-usage.py --log buck-out/*/log/*_build_*_events.pb.zst --min-wall 60 --top 25

# one action, from its digest (the hash:size in `buck2 log show`, see below)
scripts/br2-usage.py --digest f04db60544bca441beb77913dac56f1993b1068b8c799ecd18371dd3af582640:142

# raw rows for jq or a spreadsheet: the packages that averaged more than 4.5 cores
scripts/br2-usage.py --log buck-out/*/log/*_build_*_events.pb.zst --json \
  | jq -r '.[] | select(.cores > 4.5) | [.id, (.wall_s|round), (.cores*100|round/100), (.max_rss_gib*100|round/100)] | @tsv' \
  | sort -k2 -n -r | head
```

Logs are under `buck-out/v2/log/` and, for matrix cells, `buck-out/<variant>-<mode>/log/`. Each run
of `br2 matrix` has its own salt, so every cell has its own action digests; pass all the logs you want counted.

### Finding an action digest by hand

```bash
LOG=$(ls experiments/qemu-x86_64/buck-out/wrapped-remote-cache/log/*_build_*.zst | tail -1)
buck2 log show "$LOG" \
  | jq -r '.Event.data.SpanEnd.data.ActionExecution? // empty | select(.commands)
           | [.name.identifier, (.commands[0].details.command_kind.command.RemoteCommand.action_digest // "-")] | @tsv' \
  | head
```

### Reading the raw result

The tool is a thin decoder over one call, which you can make yourself:

```bash
grpcurl -plaintext -d '{"instance_name":"qemu-x86_64","action_digest":{"hash":"f04db605…2640","size_bytes":142}}' \
  localhost:8980 build.bazel.remote.execution.v2.ActionCache/GetActionResult | jq .executionMetadata
```

`grpcurl` cannot decode the `POSIXResourceUsage` entry (it does not know the message type) and prints it as
base64 in `@value`; `br2-usage.py` decodes it. `NotFound` means no result under that instance name.

## Per worker instead of per action

With `concurrency: 1` a worker pod runs one action at a time, so the container's own numbers are that action's
numbers, summed over all its processes (peak memory here **is** the total). Prometheus keeps 48 hours:

```bash
kubectl -n monitoring port-forward svc/prometheus-server 9090:80 &
q() { curl -s --data-urlencode "query=$1" localhost:9090/api/v1/query | jq -r '.data.result[] | [.metric.pod, (.value[1]|tonumber*100|round/100)] | @tsv'; }

# peak memory (GiB) of the busiest worker runners, last 3 hours
q 'topk(5, max_over_time(container_memory_working_set_bytes{namespace="buildbarn",container="runner"}[3h]) / 2^30)'

# peak CPU (cores, 1-minute rate) of the same
q 'topk(5, max_over_time(rate(container_cpu_usage_seconds_total{namespace="buildbarn",container="runner"}[1m])[3h:1m]))'
```

A worker's request is 4.5 cores and 9 GiB (`charts/buckroot-buildbarn/values.yaml`); compare.

## Was something killed for memory?

Check all three; each sees a different layer.

```bash
# 1. the action itself: a command that ended on a signal (KILL is the OOM killer)
scripts/br2-usage.py --log buck-out/*/log/*_build_*_events.pb.zst --json | jq '[.[] | select(.termination_signal != "")]'

# 2. the container: Kubernetes and the kernel's own counters
kubectl get pods -A -o json | jq -r '.items[] | .metadata as $m | .status.containerStatuses[]? | select(.lastState.terminated.reason == "OOMKilled") | [$m.namespace, $m.name, .name] | @tsv'
q 'sum(increase(container_oom_events_total{namespace="buildbarn"}[6h]))'

# 3. the client: the failure text of the action
buck2 log show "$LOG" | grep -c 'Killed signal terminated program'
```

Only actions with a stored result appear in (1): a failed action is not cached, so a kill shows first in (2)
and (3). The history of the OOM that led to `concurrency: 1` is in
[ADR-0015](../decisions/0015-buildbarn-on-kubernetes.md) and [Sizing the worker](buildbarn.md#sizing-the-worker).

## When the tool finds nothing

| Symptom | Cause | Fix |
|---|---|---|
| `no stored results found` for every action | wrong instance name, or the frontend is not reachable | `grep instance_name .buckconfig`; try `grpcurl -plaintext localhost:8980 list` |
| a few actions missing (`126 of 127`) | the result was evicted, or the action failed | ignore, or rerun the cell |
| everything missing for old logs | the cache is newer than the log: the cluster was rebuilt, or the storage is a different one | only logs from the current cluster's lifetime have results |
| `grpcurl not found` | not installed | [Before you start](#before-you-start) |
| `buck2 log show` fails | wrong Buck2 binary for the log | `--buck2 path/to/tools/buck2` |
