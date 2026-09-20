<title>buckroot</title>

# buckroot

Builds a [Buildroot](https://buildroot.org/) project with [Buck2](https://buck2.build/):
one Buck2 target per Buildroot package, cacheable and remotely executable, and
checked against a plain `make` build of the same configuration. You keep your
`defconfig`, your `BR2_EXTERNAL` tree and Buildroot's own `.mk` files; buckroot
adds the build graph, the input isolation and the cache keys that Buildroot
itself does not have.

## The whole idea, in one experiment

An experiment is a directory with one file that names a Buildroot project,
`project.json`:

```json
{
  "name": "helloworld",
  "defconfig": "helloworld_qemu_aarch64_musl_defconfig",
  "external": true,
  "buildroot": {"repo": "https://git.buildroot.net/buildroot", "ref": "2025.02.18"}
}
```

Everything else is generated from it:

```console
$ scripts/br2 setup      # Buck2 binary, the Buildroot tree
$ scripts/br2 extract    # defconfig -> package model -> BUCK files
$ scripts/br2 golden     # plain `make`, the reference result
$ scripts/br2 build --variant wrapped --mode local-cache
{ "cold": {"ok": true, "seconds": 363.8, "commands": 61, "cached": 0,  "local": 61, "manifest": "IDENTICAL"},
  "warm": {"ok": true, "seconds": 8.5,   "commands": 61, "cached": 61, "local": 0,  "manifest": "IDENTICAL"}, ... }
```

The warm run is the point: a whole 61-package Buildroot image, rebuilt from
the shared cache in eight seconds, with a root filesystem whose file list, modes,
owners and content hashes are identical to what `make` produced. What happened in
between is covered in [Architecture](../concepts/architecture.md).

## Two variants, four modes

| | local | local + cache | remote | remote + cache |
|---|---|---|---|---|
| **wrapped** | Buck2 runs each `make <pkg>` on this machine | ...and shares results through a Buildbarn cache | each `make <pkg>` runs on a Buildbarn worker | ...and its results are cached |
| **native** | Buck2 actions do the package's work themselves | same | same | same |

`wrapped` is the default and works for every Buildroot package. `native` replaces
selected packages with Buck2 actions that do not call `make` at all, for finer
early cutoff. Both variants and all four modes are measured for every project in
[Results](../project/results.md).

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Quickstart**

    ---

    Build the bundled `helloworld` image with Buck2, then rebuild it from the
    cache.

    [:octicons-arrow-right-24: Quickstart](quickstart.md)

-   :material-plus-box:{ .lg .middle } **Your own project**

    ---

    Write a `project.json`, generate the graph, and get to an identical
    manifest.

    [:octicons-arrow-right-24: Adding a project](../guides/adding-a-project.md)

-   :material-lightbulb-on:{ .lg .middle } **How it works**

    ---

    Views, config slices, the fixed-path namespace and why a package rebuilds
    when it does.

    [:octicons-arrow-right-24: Architecture](../concepts/architecture.md)

-   :material-scale-balance:{ .lg .middle } **Decisions**

    ---

    Why each design choice was made, and what it costs.

    [:octicons-arrow-right-24: Decision log](../decisions/index.md)

</div>

## What is in the repository

- [`toolkit/`](https://github.com/DeepSpaceCartel/buckroot/tree/main/toolkit) - the
  reusable part: Starlark rules, Python actions, the `br2` CLI, the Buildbarn
  compose stack, the execution platform.
- [`experiments/`](https://github.com/DeepSpaceCartel/buckroot/tree/main/experiments) -
  one directory per real project, each with only a `project.json`, its golden
  reference and its results. `helloworld` is the small one used to develop the
  toolkit; `superduperbird` is the Spotify Car Thing firmware (a Buildroot 2024.05
  `BR2_EXTERNAL` tree with Mesa, a vendor kernel and Rust host tools).
