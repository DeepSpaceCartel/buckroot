# buckroot

Build [Buildroot](https://buildroot.org/) projects with [Buck2](https://buck2.build/):
one cacheable, remotely executable Buck2 target per Buildroot package, with the root
filesystem checked against a plain `make` build of the same configuration.

You keep your `defconfig`, your `BR2_EXTERNAL` tree and Buildroot's own `.mk` files.
buckroot generates the build graph from what Buildroot reports about your configured
project, isolates every package action so its cache key covers only what it can read, and
lets Buck2 schedule, cache and distribute the work - locally, with a shared cache, on a
remote worker, or both.

Full docs: <https://deepspacecartel.github.io/buckroot/>

```console
$ cd experiments/helloworld
$ ../../toolkit/bin/br2-sync .
$ scripts/br2 setup && scripts/br2 extract && scripts/br2 golden
$ scripts/br2 build --variant wrapped --mode local-cache      # cold, then warm from the cache
{ "cold": {"seconds": 363.8, "commands": 61, "cached": 0,  "manifest": "IDENTICAL"},
  "warm": {"seconds": 8.5,   "commands": 61, "cached": 61, "manifest": "IDENTICAL"} }
```

## Layout

- [`toolkit/`](toolkit) - the reusable part: Starlark rules and Python actions, the `br2`
  CLI, the fixed-path mount namespace, the Buildbarn compose stack and the execution
  platform.
- [`experiments/`](experiments) - one directory per project, each with a `project.json`,
  its golden reference and its results:
  - [`helloworld`](experiments/helloworld) - a minimal aarch64 musl image; the toolkit's
    development example.
  - [`superduperbird`](experiments/superduperbird) - the Spotify Car Thing firmware
    (Buildroot 2024.05, `BR2_EXTERNAL`, glibc, Mesa, a vendor kernel).
- [`docs/`](docs) - the documentation site (MkDocs Material).

## Two variants, four modes

| | local | local + cache | remote | remote + cache |
|---|---|---|---|---|
| `wrapped` (Buildroot's own `make <pkg>` in each action) | yes | yes | yes | yes |
| `native` (selected packages built by Buck2 actions) | yes | yes | yes | yes |

Results per project, with the manifest comparison against `make`, are in the
[Results](https://deepspacecartel.github.io/buckroot/project/results/) page.

## Documentation

```bash
pip install -r docs/requirements.txt
mkdocs serve
```
