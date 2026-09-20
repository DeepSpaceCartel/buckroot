<title>Buck2 configuration</title>

# Buck2 configuration

`.buckconfig` is generated from `toolkit/templates/buckconfig` and `project.json` by
`br2-sync`. Do not edit it; put project settings in `project.json` and per-run settings
on the command line (`br2 build --mode ...`, or `--config br2.<key>=<value>` to Buck2).

## `[br2]`

| Key | Default | Meaning |
|---|---|---|
| `remote_cache` | `false` | look results up in the Buildbarn cache |
| `cache_uploads` | `false` | upload results to it (leave off for untrusted builds) |
| `remote_execution` | `false` | run actions on the Buildbarn worker |
| `local_execution` | `true` | allow actions to run locally (set `false` with `remote_execution`) |
| `native` | empty | comma-separated packages built by Buck2 actions instead of `make <pkg>` |
| `native_project` | from `native/` | the subset of `native` that lives in this project's `native/` directory |
| `external` | from `project.json` | does the project have a `BR2_EXTERNAL` tree |
| `rootfs_image` | from `project.json` | the image the rootfs action copies out |
| `fragment` | from `project.json` | the config fragment applied after the defconfig |
| `dev_tools` | `false` | dev mode: the toolkit's scripts are referenced by path, not declared as inputs |
| `cache_salt` | empty | added to every action's environment; a different value is a fresh cache generation |

## `[buck2_re_client]`

| Key | Value |
|---|---|
| `engine_address`, `action_cache_address`, `cas_address` | `grpc://localhost:8980` (the scheme is required) |
| `tls` | `false` |
| `instance_name` | the project name, plus a suffix per mode (`br2 build` sets it) |

## Cells and the prelude

The project is a single cell (`root = .`) plus the `prelude` bundled with the pinned
`buck2` binary (`[external_cells] prelude = bundled`). The execution platform is
`root//platforms:default`, which reads the `[br2]` switches; the prelude's own default
hard-codes no remote.

## Watched paths

`[project] ignore` keeps Buck2's file watcher off `.git`, `buildroot-src/.git`,
`buildroot-src/output`, `buildroot-src/dl`, `out` and `tools`. Buildroot's output is
elsewhere on purpose; see [Debugging](../guides/debugging.md).
