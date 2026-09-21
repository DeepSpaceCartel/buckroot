<title>project.json</title>

# project.json

The only project-specific input of the toolkit. It lives at the root of an experiment
directory (`experiments/<name>/project.json`); the toolkit finds it by walking up from
the working directory.

```json
{
  "name": "superduperbird",
  "defconfig": "superduperbird_defconfig",
  "external": true,
  "external_repo": {"url": "https://github.com/nd-0r/superduperbird-buildroot", "commit": "fcc1ef9f..."},
  "buildroot": {"repo": "https://git.buildroot.net/buildroot", "ref": "2024.05.3"},
  "rootfs_image": "rootfs.tar",
  "sources": "vendored",
  "config_fragment": ["BR2_ROOTFS_POST_IMAGE_SCRIPT=\"\""],
  "extra_view": {"package/gcc/gcc-final": ["package/gcc"]},
  "heavy": ["host-gcc-final", "linux", "mesa3d"],
  "salts": {"linux": "retry-2"},
  "manifest_ignore": ["/etc/shadow"],
  "native": ["skeleton", "host-skeleton"]
}
```

## Keys

| Key | Type | Default | Meaning |
|---|---|---|---|
| `name` | string | required | experiment name: the cache directory (`~/.cache/br2/<name>`) and the Buildbarn instance name |
| `description` | string | - | free text |
| `defconfig` | string | required | a defconfig `make` understands (`configs/` of the tree or of the external tree) |
| `external` | bool | `true` | is there a `BR2_EXTERNAL` tree in `buildroot-external/`? |
| `external_repo` | `{url, commit, subdir?}` | - | where `br2 setup` gets `buildroot-external/` from, pinned to a commit. With `subdir`, only that directory of the repository is copied (a monorepo such as FunKey-OS or Home Assistant OS) and `EXTERNAL_PINNED_COMMIT.txt` records what was taken |
| `buildroot` | `{repo, ref, commit?}` | - | where `br2 setup` clones `buildroot-src/` from. `ref` is a tag or branch (a shallow clone); with `commit`, that exact commit is fetched instead (a vendor fork pinned by a git submodule) and `ref` is only a label |
| `native` | list of package names | `[]` | packages the `native` variant builds with Buck2 actions |
| `rootfs_image` | string | `rootfs.ext4` | the file of `output/images/` that is compared |
| `sources` | `"http"` or `"vendored"` | `"http"` | how downloads reach Buck2 |
| `config_fragment` | list of `BR2_*` lines | `[]` | overrides applied to golden and Buck2 builds, after the two required settings |
| `extra_view` | map | `{}` | see [below](#extra_view) |
| `heavy` | list of package names | `[]` | packages that run alone |
| `heavy_weight` | int | CPU count | the weight given to a `heavy` package |
| `salts` | map | `{}` | package to string; changing a value rebuilds that package only |
| `manifest_ignore` | list of paths | `[]` | paths compared by presence only |
| `notes` | string | - | deviations from the project's own defconfig, and why |

The two settings every build receives, before `config_fragment`: `BR2_PER_PACKAGE_DIRECTORIES=y`
and `BR2_REPRODUCIBLE=y`.

## Directory layout

Fixed names, so the generated Buck2 files are the same for every project:

| Path | Contents | In git |
|---|---|---|
| `project.json` | this file | yes |
| `buildroot-src/` | the Buildroot tree | no (fetched) |
| `buildroot-external/` | the `BR2_EXTERNAL` tree | project-dependent |
| `common/` | local package sources (`<PKG>_SITE_METHOD = local`), mounted at `/mnt/common` | yes |
| `native/<pkg>/BUCK` | project-specific native rules | yes |
| `golden/` | `model.json`, `rootfs.manifest.json`, `sources.lock.json` | yes |
| `results/` | matrix and golden timings | yes |
| `sources/` | vendored downloads | no |
| `scripts/`, `br2/`, `platforms/`, `toolchains/`, `infra/`, `tools/` | vendored from the toolkit by `br2-sync` | no |
| `BUCK`, `.buckconfig`, generated `BUCK` files | rendered | yes |

## `extra_view` { #extra_view }

A map from a package directory to the other directories that package's `.mk` files read
without being dependencies. They are added to the package's [view](../concepts/views-and-slices.md#views).
Keys and values are paths relative to the Buildroot tree:

```json
"extra_view": {
  "package/gettext-tiny": ["package/gettext-gnu"],
  "package/gcc/gcc-final": ["package/gcc"],
  "package/util-linux/util-linux-libs": ["package/util-linux"]
}
```

`scripts/check-narrow.py --apply` proposes entries.

## Old and forked Buildroot trees

`buildroot.commit` and `external_repo.subdir` exist for vendor forks pinned by a git submodule, where
the tree is not a release tag. The toolkit extracts trees as old as Buildroot 2021.02 (FunKey-OS):
it falls back to `make printvars` where `show-vars` does not exist (before 2023), reads `build_dir` where
`show-info` has no `stamp_dir`, and runs `make` with a 1 GiB stack limit because GNU make 4.3 overflows
the default stack on the old `printvars`. See [Projects](../project/projects.md) for what each project needed.

## `sources`

- **`http`**: a source with a plain HTTP URL and a SHA-256 becomes a Buck2 `http_file`;
  anything else is fetched by `br2 fetch`.
- **`vendored`**: every source is fetched by `br2 fetch` into `sources/` and recorded in
  `golden/sources.lock.json`, so a build never touches the network. Recommended for real
  projects; see [ADR-0007](../decisions/0007-vendored-sources.md).

## Patches to the fetched trees

`patches/buildroot/*.patch` and `patches/external/*.patch` in the experiment directory are applied by `br2 setup` (`patch -p1`, once,
right after each tree is fetched; the golden Job applies them too). They are deviations from the project as published, so each patch
says why in its header and the project's notes explain the difference. The first use: FunKey-OS's `PCSX-ReARMed` runs
`mksquashfs` from its host directory without depending on `host-squashfs`, which per-package directories (required by buckroot)
turn into a build failure; the patch adds the dependency and changes nothing in the image.
