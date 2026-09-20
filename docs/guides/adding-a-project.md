<title>Adding a Buildroot project</title>

# Adding a Buildroot project

Take an existing Buildroot project (upstream defconfig, or a `BR2_EXTERNAL` tree such
as a board vendor's) and get `buck2 build //:rootfs` to produce the same root
filesystem as `make`. The [Quickstart](../home/quickstart.md) is the prerequisite.

## 1. Create the experiment directory

```bash
mkdir experiments/myboard && cd experiments/myboard
```

Write `project.json`. The minimum is a name, a defconfig and the Buildroot version:

```json title="project.json"
{
  "name": "myboard",
  "defconfig": "myboard_defconfig",
  "external": false,
  "buildroot": {"repo": "https://git.buildroot.net/buildroot", "ref": "2024.05.3"}
}
```

The other keys are [documented in the reference](../reference/project-json.md); you
will add most of them as the steps below turn up problems.

=== "Upstream defconfig"

    Leave `external` as `false`. `defconfig` is a file from Buildroot's own
    `configs/`.

=== "BR2_EXTERNAL tree"

    Set `external` to `true` and put the external tree in `buildroot-external/`
    (clone it there, or use `external_repo` with a URL and a commit). `defconfig` is a
    file from the external tree's `configs/`.

=== "A vendor fork of Buildroot"

    Point `buildroot.repo` at the fork (any git URL) and keep `ref` pinned to a tag
    or commit; `br2 setup` clones it to `buildroot-src/`.

Pin a **release tag**, not a branch: every cache key is derived from the tree.

## 2. Vendor the toolkit and fetch

```bash
../../toolkit/bin/br2-sync .
scripts/br2 setup
```

## 3. Deal with your defconfig

The instrumentation appends two settings to every build, golden included:
`BR2_PER_PACKAGE_DIRECTORIES=y` and `BR2_REPRODUCIBLE=y`. Anything else in the
defconfig that cannot run inside a read-only, fixed-path namespace goes into
`config_fragment`, an overriding list of `BR2_*` lines applied to *both* the golden
and the Buck2 builds. The usual offenders:

| Symptom | Fragment |
|---|---|
| A `BR2_ROOTFS_POST_IMAGE_SCRIPT` that writes outside `$BINARIES_DIR` or loop-mounts an image | `"BR2_ROOTFS_POST_IMAGE_SCRIPT=\"\""` |
| A kernel config file that does not build at the pinned commit | point `BR2_LINUX_KERNEL_CUSTOM_CONFIG_FILE` at one that does |
| A hook that expects a setting the default defconfig lacks | add that setting |

Record *why* in `notes` - the deviation from the project's own defconfig is part of
the result. `br2 golden --vanilla` builds the untouched defconfig for reference.

The image the comparison scans is `rootfs_image`: `rootfs.ext4` by default, or
`rootfs.tar`, `rootfs.squashfs` and so on if that is what your defconfig produces.

## 4. Extract the package graph

```bash
scripts/br2 extract
```

This asks Buildroot itself (`make show-info`, no build needed) for every package,
its version, direct dependencies, source URL, hashes and patches, writes
`golden/model.json`, and renders one `BUCK` file per package directory. Commit
`golden/model.json`.

## 5. Fetch sources Buck2 cannot download

```bash
scripts/br2 fetch
```

Buck2's `http_file` covers plain HTTP downloads with a SHA-256. Git sources,
SHA-512-only hashes and dead upstream URLs are downloaded by `br2 fetch` into
`sources/` and recorded in `golden/sources.lock.json`. Set `"sources": "vendored"`
when a project has any of these (most real ones do) so that *every* source goes that
way and the build never depends on the network. See
[ADR-0007](../decisions/0007-vendored-sources.md).

## 6. Build the golden reference

```bash
scripts/br2 golden
```

Plain `make` in the same namespace. It takes as long as your project takes (a few
minutes for a small image, over two hours for one with Mesa and a vendor kernel on
four cores) and writes `golden/rootfs.manifest.json`. Commit it.

## 7. Run preflight and the narrowing check

```bash
scripts/br2 preflight
scripts/check-narrow.py
```

`preflight` extracts and patches every package in its own narrowed view and compares
the list of applied patches with the golden build's - in minutes instead of after a
multi-hour compile. `check-narrow.py` compares every make variable between the full
tree and the view. Both find *hidden cross-package references*: a `.mk` that reads a
file from a package that is not its dependency, like `busybox` installing a
symlink into `../procps-ng/`. Fix each with `extra_view`:

```json
"extra_view": {
  "package/gettext-tiny": ["package/gettext-gnu"],
  "package/gcc/gcc-final": ["package/gcc"]
}
```

`scripts/check-narrow.py --apply` suggests and writes the entries it can prove. Run
`scripts/br2 extract` again afterwards. Background:
[Views and config slices](../concepts/views-and-slices.md).

## 8. Build with Buck2

```bash
scripts/br2 dev                  # iterate: keep going, report every failure at once
```

Failures are usually one of: an `extra_view` entry you have not written yet, an
action that runs out of memory (list the package in `heavy`, see
[Iterating fast](fast-iteration.md)), or something the golden build did that a
read-only source tree does not allow. [Debugging a failing package](debugging.md)
covers each.

## 9. Get to an identical manifest

```bash
scripts/br2 build --variant wrapped --mode local
```

The result's `manifest` field is either `IDENTICAL` or the first 20 differences.
Content that is random on *every* build, golden included (a salted password hash in
`/etc/shadow`), goes into `manifest_ignore`; everything else is a real difference -
see [Verification](../concepts/verification.md) for how to read one.

## 10. Choose the native list and run the matrix

`native` lists the packages the `native` variant builds with Buck2 actions instead of
`make`. Start with the generic ones the toolkit ships in `toolkit/br2/native/`
(`skeleton`, `host-skeleton`, `initscripts`, `urandom-scripts`, ...) that your
configuration uses. Then:

```bash
scripts/br2 matrix --variants native wrapped
```

Each cell cleans Buck2's state first, runs cold (and for the cache modes, warm), and
compares its manifest with the golden. Results land in `results/matrix.md`.
