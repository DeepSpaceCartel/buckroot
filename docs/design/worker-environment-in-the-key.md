<title>Worker environment in the action key</title>

# Worker environment in the action key

*Status: proposed. Nothing on this page is implemented except the one-line workaround described under [Evidence](#evidence).*

## The problem

A cache key must cover everything that can change the result. For a wrapped action, the result depends on the **tools** the build calls
(`gcc`, `perl`, `rsync`, `bison`, `git`, ...) and on what those tools find on the machine. Neither is in the key today, so two machines with
different tools compute the same key and can produce different bytes, and a cache hit can serve a result built with a tool set that no longer
exists. Nothing fails; the result is simply wrong for the environment that asked.

This matters in every mode. Locally the tools are whatever is installed. Remotely they are whatever the worker image contains, and the image is
referenced by *name*.

## How a key is formed

In Buck2's remote execution model (the REAPI *action digest*), the key is the hash of:

| Part | Covers the tools? |
|---|---|
| the command line | only their names (`make`, `python3`) |
| the environment variables the action declares | only if a variable says something about them |
| the input root: every declared input file | no, unless the tools are inputs |
| the platform properties (`OSFamily`, `container-image`) | only if a property changes when the tools change |

The current platform property is `container-image: docker://buckroot-worker`, a name. Rebuilding the image does not change it.

## Evidence

| Observation | What it shows |
|---|---|
| Adding `git` to the worker image fixed a remote failure (Buildroot 2024.05's dependency check) and changed no key | the tool set is invisible to the key |
| Three OpenSSH binaries (`ssh`, `sshd`, `ssh-keysign`) differed between the golden build and the first two remote builds. Same size, different hash, identical across the two remote runs | an ambient tool leaked into the output. OpenSSH's `configure` searches the build machine for `xauth` and embeds the path it finds. The golden and local builds ran where `/usr/bin/xauth` exists, the worker had none. Adding `xauth` to the image was the workaround, and it worked: the next remote cell was IDENTICAL |
| `xauth` is not on any list of "tools the build needs"; `configure` found it by searching the filesystem | restricting `PATH` cannot fix this class |
| Every measured matrix cell has its own cache salt | the cells are not affected by stale hits, but only because of the salt, not because of anything about the environment |

## The requirement

A change to the environment that can change any output must change the key of every action it can affect, and an environment that does not
match what the key claims must be detected, not silently used.

## Options

### 1. An identity in the platform properties

Add a property, for example `baseline: <hash>`, where the hash is computed from `runner/Dockerfile` plus the resolved package versions (or
is the image digest instead of a tag). The worker advertises the same value, and Buildbarn routes an action only to a worker whose properties
match. Rebuilding the image changes the hash, and every key changes with it.

- Effort: small. A generated value in `platforms/BUCK` and in the worker configuration.
- Covers: remote execution, deliberate image changes.
- Does not cover: an image edited without a new hash, a worker started from the wrong image, or **local** execution (there is no image).
  It is a claim, not a check.

### 2. A lock file that is verified at run time

Ship a `tools.lock` as a declared input: each tool and a hash of its binary, or the package versions. The action verifies the environment against
it before running and fails on any mismatch. Because the lock is an input, its content is in the key.

- Effort: small to medium (the lock generator, the check in `br2-ns.sh`).
- Covers: drift of the *listed* tools on workers and on local machines alike (a local machine that does not match fails, or, in dev mode, warns).
- Does not cover: anything not listed. The `xauth` case is the counterexample: the file was never a tool anyone would list.

### 3. The tools as a declared input tree

Build a pinned tool root filesystem reproducibly (a Debian snapshot at a fixed date, or a Nix closure) and declare it as an input. The
namespace the action already runs in mounts it as `/usr`, `/bin` and `/lib`, so **nothing else on the machine is visible**. The environment is then in
the input digest by construction.

- Effort: large.
- Covers: everything. Local and remote produce the same bytes. The golden build can be made to run in it too, removing the accidental dependency
  on the developer's machine. This is also the shape Buck2 intends (tools as toolchain artifacts rather than `system_*` toolchains that read the host).
- Costs: a large input (several hundred MB, deduplicated by the cache), which must be linked into each action rather than unpacked (see
  [Directory-tree package outputs](../project/status.md#directory-tree-package-outputs), which it shares a prerequisite with); building the tree
  reproducibly; and going through the namespace script.

### Considered and set aside: a probe action

A probe that runs on the worker and reports tool versions, made an input to every package action, only works if the probe itself is not cached and
runs on the same worker that will run the packages. With more than one worker that cannot be guaranteed.

## Recommendation

1. **Options 1 and 2 first.** They are small and fix the dangerous case (a stale hit after an image change); a drifted or wrong worker becomes an
   immediate, named error. Keep the manifest comparison with the golden as the after-the-fact check for what they miss.
2. **Option 3 as the destination**, for projects where local and remote must agree byte for byte.

## Unknowns to settle before building

| Question | How to answer it |
|---|---|
| Does Buildbarn require exact equality of platform properties, or subset matching? | read the scheduler configuration and try a worker advertising extra properties |
| Does a property name the scheduler does not know break routing? | one worker, one action |
| How expensive is linking a large tool tree into each action? | time a directory of the size of the Debian build tools, hard-linked and copied |
| Is a Debian snapshot reproducible enough (package sets, timestamps, `ldconfig` caches)? | build it twice, compare digests |
| What else does a `configure` script embed from the host? | build each project's wrapped image on two different hosts and diff the manifests. `xauth` was found this way |
| Does an action running in the tool tree still see the toolchain wrapper paths the fixed-path namespace assumes? | run `helloworld` in it |

## Acceptance tests

Each of these must be automated before the change is called done:

1. Changing a tool in the baseline (add a package to the image, or edit the lock) changes the key of **every** wrapped action, and a `remote-cache`
   run after the change is fully cold.
2. Starting a worker from an image that does not match the advertised baseline makes the action fail with a message that names the difference.
3. `br2 build --mode remote` and `--mode local` produce identical manifests for `helloworld`, and for the Car Thing, **without** `xauth` on either
   machine (Option 3) or with it pinned in the baseline (Options 1 and 2).
4. Rebuilding the image without bumping the baseline is detected by a check in CI, not by a wrong result.

## Where it fits

It belongs after the matrices and after the characterization tests of the refactor phase, because it changes every key. Until it is built, the
rule in [ADR-0013](../decisions/0013-worker-image-is-the-tool-baseline.md) applies: the image is the definition of the remote environment, a change to it
is a deliberate event, and the cells of a measured matrix each carry their own salt.
