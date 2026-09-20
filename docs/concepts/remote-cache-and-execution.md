<title>Remote cache and execution</title>

# Remote cache and execution

What was measured and learned running buckroot against a real
[Buildbarn](https://github.com/buildbarn) deployment, and why the setup looks the way it
does. The how-to is [Remote cache and execution with Buildbarn](../guides/buildbarn.md).

## Vocabulary, precisely

- **Action key** - a digest over the action's definition and every declared input.
- **CAS** - content-addressable storage: blobs and directory trees by hash.
- **Action cache (AC)** - action key to the metadata of a previous result.
- **Remote cache** - AC and CAS served over the Remote Execution API (REAPI).
- **Remote execution (RE)** - a scheduler hands actions to workers, which fetch inputs
  from the CAS and return outputs there.

In the intended design the client never "builds files": it computes the graph, hashes
actions and inputs, asks the cache, and either reuses outputs or schedules execution.

## The four modes

| Mode | Cache lookups | Where actions run |
|---|---|---|
| `local` | none | this machine |
| `local-cache` | Buildbarn | this machine, on a miss |
| `remote` | none (fresh instance name) | the Buildbarn worker |
| `remote-cache` | Buildbarn | the worker, on a miss |

## Remote cache

Buildbarn is a `frontend` speaking REAPI (CAS and AC, completeness-checked, so an
evicted blob is a *miss*, not a broken hit) in front of one `storage` shard on
block-device files. On the Buck2 side there is a custom execution platform - the
prelude's default hard-codes no remote - with `remote_cache` and `cache_uploads`
toggled from `[br2]` in `.buckconfig`, and `[buck2_re_client]` naming the endpoint.

Measured on the 61-action `helloworld` image: cold build 5 min 59 s and 435 MiB
uploaded; after `buck2 kill` and `buck2 clean` the same graph is **61/61 cache hits in
37 s**, with the manifest still identical to the golden. (A later, cleaner
measurement is in [Results](../project/results.md).)

**Key stability.** The same tree copied to a different absolute path also hits 61/61,
because commands, specs and inputs are all project-relative and actions run at the fixed
`/mnt/...` paths of the namespace. Nothing about the checkout location leaks into a key.

### Trust { #trust }

A client with `cache_uploads=false` still reads the cache but writes nothing. An edited
`hello.c` built read-only in one checkout was a miss in a second checkout, and reverting
it hit again. A shared cache is only as trustworthy as whoever can write action results:
untrusted branches get read-only clients (in Buildbarn: no `putAuthorizer` for them), and
only trusted CI populates the cache.

### What the key does not cover

The key hashes the command, the declared inputs and the declared environment - not
the ambient host tools the wrapped actions use. A hit is unsound, rather than failing, if
two machines differ. Pinning the tools in the worker image is the answer
([Wrapped and native](wrapped-and-native.md#the-host-tools-are-not-in-the-key)).

### The cost of a hit

A cache hit is not free of transfer. A 2-action rebuild of `hello` pulled 405 MiB down,
because its inputs include the toolchain artifact; per-package tarballs of the
whole toolchain overlay are the bandwidth hot spot.

## Remote execution

The same stack plus a `scheduler`, a hardlinking `worker` and a privileged `runner`
container built from the pinned tool baseline. With
`br2.remote_execution=true br2.local_execution=false` all 61 actions run on the worker
(none locally), the manifest is identical to plain `make`, and the image boots.

### Everything that read the checkout instead of the inputs failed

One at a time, on the first remote run - local execution had masked all of them because the
whole checkout is on disk:

- **Root discovery via a marker file.** A remote input root has none; the working
  directory is the only definition valid in both places.
- **The namespace script located by path**, while the declared artifact lives under
  `buck-out`.
- **A source directory read from `common/`** instead of the filegroup output.
- **`python3`.** Buck2 sends an empty environment and the runner resolves executables
  through the command's own `PATH`, so `PATH` became part of the action.
- **Dangling symlinks** (see [Verification](verification.md#what-the-manifest-caught)).

### Configuration traps

- gRPC's 4 MiB default message limit rejects Buck2's input-root uploads: raise
  `maximumReceivedMessageSizeBytes`.
- Buck2's client leaves `Action.platform` empty, so Buildbarn's `action` platform
  extractor finds no worker: use the `static` extractor.
- Worker build directories inside the project exhaust Buck2's inotify watch limit:
  keep the state outside it.
- `[buck2_re_client]` addresses need the `grpc://` scheme; without it uploads fail with a
  misleading `No engine address`.
- Buildbarn's local storage **ignores instance names**, so a fresh instance name does
  not make a cold cache. See
  [ADR-0010](../decisions/0010-cache-salt-per-cell.md).

### Failure semantics observed

- **Killing the runner mid-action** surfaces as an *infrastructure* error (`Failed to run
  command: error reading from server: EOF`, stage `remote_call_error`) that fails the
  build at once, with no automatic retry. A rerun after the runner restarts succeeds
  and reuses everything already done.
- **The whole remote side down**, with local fallback allowed: the action tries to run
  locally and fails with `materialize_inputs_failed`, because its inputs were produced
  remotely and exist only in the remote CAS. Local fallback needs a reachable CAS (or
  `--materializations=all`).

### Performance, honestly

On one machine the "remote" worker shares the same four cores, and every action pays for
input upload and materialization: a cold `helloworld` build took 7 min remotely against
5 min 16 s locally in the first measurement. Remote execution buys isolation, a pinned
toolchain image and scale-out, not speed on one machine. The cache modes cost 5-15 % on
a cold run for uploading results, and repay it the first time anything is rebuilt.

## Scaling out

Nothing in the design ties the worker to the same machine. The scheduler is a queue keyed
on platform; adding workers (containers or nodes) that register with it adds capacity, and
the cache is shared by construction. Heavy packages carry a *weight*, which keeps Buck2 from scheduling the compiler, the kernel and Mesa
at the same time; a worker's own concurrency limit does the same on the remote side.
