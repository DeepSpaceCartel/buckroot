<title>Quickstart</title>

# Quickstart: build `helloworld` with Buck2, then rebuild it from the cache

Build the bundled `helloworld` experiment (a 61-action aarch64 musl image with one
local package) twice - once cold, once from a Buildbarn cache - and see that both
results match a plain `make` build. Every command below is real.

## Prerequisites

- A Linux host (x86-64) with about 8 GB of RAM, 20 GB of disk and 4 cores. The
  cold build takes about six minutes on 4 cores.
- `python3`, `git`, `rsync`, `gcc`/`make`/`perl`/`bc`/`bison`/`flex`, `cpio`,
  `unzip`, `wget` - the ordinary Buildroot host prerequisites. The list the
  remote worker image installs is in
  [`toolkit/infra/buildbarn/runner/Dockerfile`](https://github.com/DeepSpaceCartel/buckroot/blob/main/toolkit/infra/buildbarn/runner/Dockerfile).
- The ability to create mount namespaces (`CAP_SYS_ADMIN`, i.e. root or a
  privileged container). Every package action runs in one; see
  [Fixed-path mount namespace](../decisions/0004-fixed-path-namespace.md).
- Docker with the compose plugin, for the cache steps only.

!!! note "Where the outputs go"
    Build output and downloads live outside the experiment, in
    `~/.cache/br2/<name>` (override with `BR2_CACHE`). Buildroot's output tree
    inside the project would exhaust Buck2's file-watch limits.

## 1. Vendor the toolkit into the experiment

```bash
git clone https://github.com/DeepSpaceCartel/buckroot.git && cd buckroot
toolkit/bin/br2-sync experiments/helloworld
cd experiments/helloworld
```

`br2-sync` copies `scripts/`, `br2/`, `platforms/` and friends from the toolkit
into the experiment (they are git-ignored there), so an experiment directory is
self-contained and Buck2 sees the rules as part of its own cell.

## 2. Fetch, generate, and build the reference

```bash
scripts/br2 setup       # pinned buck2 binary + the Buildroot 2025.02.18 tree
scripts/br2 extract     # Buildroot's `show-info` -> golden/model.json -> BUCK files
scripts/br2 golden      # plain `make` with the same config; writes golden/rootfs.manifest.json
```

The *golden* build is what Buck2 has to reproduce, so it runs in the same
fixed-path namespace with the same configuration fragment (per-package
directories, reproducible timestamps). See
[Verification](../concepts/verification.md).

## 3. Build with Buck2, locally

```bash
scripts/br2 build --variant wrapped --mode local
```

`br2 build` stops the Buck2 daemon and cleans its state, builds `//:rootfs`, scans
the resulting image and compares it with `golden/rootfs.manifest.json`, then prints one
JSON result:

```json
{
  "variant": "wrapped", "mode": "local",
  "cold": {"ok": true, "seconds": 338.0, "commands": 61, "cached": 0, "remote": 0, "local": 61,
           "manifest": "IDENTICAL"}
}
```

## 4. Start the cache and build again

```bash
export BB_VOLUMES=/var/lib/buckroot-buildbarn
mkdir -p $BB_VOLUMES/{storage-ac,storage-cas}/persistent_state $BB_VOLUMES/worker/{build,cache/persistent_state} $BB_VOLUMES/{bb,runner-tmp}
chmod -R 0777 $BB_VOLUMES
docker compose -f ../../toolkit/infra/buildbarn/docker-compose.yml up -d frontend storage

scripts/br2 build --variant wrapped --mode local-cache
```

The cache modes build twice: a cold run that populates the cache, then - after
`buck2 kill` and `buck2 clean`, so nothing survives in Buck2's own state - a warm run
that can only be served from Buildbarn.

```json
{
  "cold": {"ok": true, "seconds": 363.8, "commands": 61, "cached": 0,  "local": 61, "manifest": "IDENTICAL"},
  "warm": {"ok": true, "seconds": 8.5,   "commands": 61, "cached": 61, "local": 0,  "manifest": "IDENTICAL"}
}
```

## 5. Everything at once

```bash
scripts/br2 matrix      # wrapped and native x local, local-cache, remote, remote-cache
```

Writes `results/matrix.md` (a table like the one in [Results](../project/results.md)).
The remote modes need the full stack (`docker compose up -d --build`); see
[Remote cache and execution with Buildbarn](../guides/buildbarn.md).

## Next

- [Add your own Buildroot project](../guides/adding-a-project.md).
- [Iterate faster](../guides/fast-iteration.md) than a six-minute loop.
- Understand what you just ran: [Architecture](../concepts/architecture.md).
