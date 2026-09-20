<title>Remote cache and execution with Buildbarn</title>

# Remote cache and execution with Buildbarn

Run the bundled [Buildbarn](https://github.com/buildbarn) stack, then point
Buck2 at it for a shared cache, for remote execution, or both. The stack is trimmed from
`buildbarn/bb-deployments` (docker compose, one storage shard) and lives in
[`toolkit/infra/buildbarn/`](https://github.com/DeepSpaceCartel/buckroot/tree/main/toolkit/infra/buildbarn).

## 1. Create the state directories

```bash
export BB_VOLUMES=/var/lib/buckroot-buildbarn
mkdir -p $BB_VOLUMES/{storage-ac,storage-cas}/persistent_state \
         $BB_VOLUMES/worker/{build,cache/persistent_state} $BB_VOLUMES/{bb,runner-tmp}
chmod -R 0777 $BB_VOLUMES
```

State lives outside the project on purpose: the worker's build directories exhaust
the inotify limit of Buck2's file watcher if they are inside a Buck2 project.

## 2. Start it

=== "Remote cache only"

    ```bash
    cd toolkit/infra/buildbarn
    docker compose up -d frontend storage
    ```

    A REAPI cache (CAS and action cache) on `localhost:8980`.

=== "Cache and remote execution"

    ```bash
    cd toolkit/infra/buildbarn
    docker compose up -d --build
    ```

    Adds the `scheduler`, one `worker` and a privileged `runner` container built
    from `runner/Dockerfile` - the pinned host-tool baseline (gcc, perl, rsync, ...)
    that the wrapped actions use. `bb-portal` and Postgres come up too.

## 3. Point a build at it

`br2 build --mode ...` sets everything for you; underneath it is four `[br2]` switches
(see [Buck2 configuration](../reference/buckconfig.md)):

| Mode | Switches |
|---|---|
| `local` | none |
| `local-cache` | `remote_cache=true`, `cache_uploads=true` |
| `remote` | `remote_execution=true`, `local_execution=false` |
| `remote-cache` | both of the above |

By hand:

```bash
tools/buck2 build //:rootfs --config br2.remote_cache=true --config br2.cache_uploads=true
tools/buck2 build //:rootfs --config br2.remote_execution=true --config br2.local_execution=false
```

A read-only client - one that uses the cache but never writes - sets
`cache_uploads=false`. That is how untrusted branches should build; see
[Remote cache and execution](../concepts/remote-cache-and-execution.md#trust).

## Web UIs

Forward the ports from your devcontainer or host.

| UI | URL | What it shows |
|---|---|---|
| bb-scheduler | <http://127.0.0.1:7982/> | platform queues, workers, running and queued operations |
| bb-portal | <http://127.0.0.1:8081/> | browse the CAS and action cache; scheduler view; build event data |

`bb-browser` was removed from Buildbarn's reference deployment; `bb-portal` (with
Postgres, in the compose file) replaces it.

To inspect one action: `tools/buck2 log what-ran` prints its digest (`<hash>:<size>`).
Paste it into the browser page of bb-portal to see the command, environment, input
tree and - for executed actions - the output tree, stdout and stderr.

## If nothing seems to happen on the worker

- With `local_execution=true` and `remote_execution=false`, everything runs on
  Buck2's own machine and the containers stay idle, as they should: check the
  `Commands: N (cached, remote, local)` line at the end of the build.
- A `remote` build needs the `worker` and `runner` containers; `frontend` and
  `storage` alone are only a cache.
- Remote runs reuse your cache unless you use a fresh `instance_name` - and note that
  Buildbarn's local storage ignores instance names, which is why
  [each measured cell has its own salt](../decisions/0010-cache-salt-per-cell.md).

## Things that break, and what they look like

| Symptom | Cause | Fix |
|---|---|---|
| `No engine address` on upload | addresses lack the `grpc://` scheme | use `grpc://host:port` in `[buck2_re_client]` |
| Uploads rejected, large input roots | gRPC's 4 MiB default message limit | `maximumReceivedMessageSizeBytes` in the Buildbarn configs (already 64 MiB here) |
| Scheduler finds no worker | Buck2 leaves `Action.platform` empty | the `static` platform extractor in `scheduler.jsonnet` |
| `Failed to run command: error reading from server: EOF` | the runner died mid-action | an infrastructure error, not retried; restart the runner and rerun - completed actions are reused |
| `materialize_inputs_failed` when falling back to local | inputs exist only in the remote CAS | keep the cache reachable, or `--materializations=all` |
| `Blob is N bytes in size, while this backend is only capable of storing blobs of up to M bytes` (stage `remote_upload_error`) | the CAS block size is the largest blob it can hold: `sizeBytes` divided by the number of blocks (38 with the original config: 16 GiB gave 431 MiB) | enlarge `sizeBytes` or lower the block counts in `config/storage.jsonnet`, and recreate the storage directory (state written with another layout is not readable); see [Sizing the storage](#sizing-the-storage) |
| `g++: fatal error: Killed signal terminated program cc1plus` in a remote action | the worker's memory ran out: it runs `concurrency` actions at once, each with `make -jN` | lower `concurrency` in `config/worker.jsonnet` (1 on an 8 GB machine); see [Sizing the worker](#sizing-the-worker) |

## Sizing the worker

A `wrapped` action runs Buildroot's `make -jN`, so one heavy package (`host-gcc-initial`, `gcc-final`, the kernel, Mesa) already uses every core and
a large part of the memory. The worker's `concurrency` setting says how many actions it runs at the same time; each one starts its own `make -jN`.

Buck2's `weight` on the `heavy` packages does **not** help here: it is a *local* scheduling hint, and a remote action is scheduled by Buildbarn.
On the reference machine (4 cores, 7.7 GB) a `concurrency` of 2 was fine for `helloworld` and killed the Car Thing build the first time two heavy
compiles overlapped: the kernel's OOM killer ended `cc1plus` while compiling `host-gcc-initial`. The shipped configuration is therefore
`concurrency: 1`.

The consequence is that remote execution on **one** machine runs the graph one action at a time (each action still parallel inside). It stops
being a way to save time and remains a way to test the remote path, pin the tool baseline and populate a shared cache. Real parallelism needs
more worker capacity: more workers, each with its own memory, and `concurrency` sized to the memory of one heavy compile (measure it: a single `cc1plus`
process can use well over a gigabyte, and `make -jN` runs N of them).

## Sizing the storage

The content-addressable storage keeps its data in a fixed number of equally sized **blocks** (`oldBlocks + currentBlocks + newBlocks +
spareBlocks`), and **one blob has to fit in one block**. The block size is `sizeBytes` divided by that number. The original 16 GiB in 38 blocks
gave 431 MiB, and the third wrapped remote Car Thing build failed uploading a 965 MB source archive (the Google Fonts repository, an input
of `googlefontdirectory`). The shipped configuration is 28 GiB in 22 blocks (1.27 GiB per block).

Changing `sizeBytes` or the block counts changes the on-disk layout: stop the storage, delete its state directory
(`$BB_VOLUMES/storage-cas` and `storage-ac`), recreate the empty `persistent_state` directories and start it again. The cache is emptied by this.
Size the total for the working set of the cells you run (each Car Thing cold cell adds about 1 GB of outputs plus 2 GB of sources), and note that
the files are sparse, so the disk usage grows as blocks fill.
