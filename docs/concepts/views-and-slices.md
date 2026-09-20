<title>Views and config slices</title>

# Views and config slices

Two mechanisms make a package's Buck2 cache key depend only on what the package can
actually use: an **enforced view** of the Buildroot tree, and a **slice** of the
configuration. Without them every action would declare the whole tree and the whole
`.config`, and any change - a new package, one defconfig line - would rerun every
action.

## Views

Buck2 runs local actions unsandboxed, so narrowing an action's *declared* inputs is
unsound on its own: the action could still read the whole checkout, and a change to a
file it read but did not declare would be a stale cache hit. buckroot therefore
narrows what the action *sees*.

Every package action runs `make` inside the private mount namespace of
`br2-ns.sh`. Inside it, `/mnt/src` (the Buildroot tree) and `/mnt/external` (the
`BR2_EXTERNAL` tree) are built from an allow-list:

- **infrastructure** - every entry of the tree except `package/<dir>/`, stray dot-config
  files, `.git`, `output` and `dl`;
- the **package directories** of the package's dependency closure and of the package
  itself;
- **links** and **extra view** entries, below.

Each is bind-mounted read-only. An undeclared read is `ENOENT`, never a stale hit. The
same mechanism is what makes remote execution sound, because a remote worker only has
the declared inputs anyway.

`make` parses with a subset of packages because Buildroot's top-level makefile does
`include $(sort $(wildcard package/*/*.mk))`: a package that is not in the view is
simply not seen. The dependencies of a package, which are all `make` walks, are.

### What the enforced view finds

Enforcement immediately exposes couplings Buildroot never declared:

- `busybox`'s `S02sysctl` is a symlink into `../procps-ng/`, a directory outside
  busybox's closure.
- Group directories (`package/gcc/`, `package/opengl/`) whose `.mk` is included by a
  makefile in the *parent* directory: the parent and its non-package subdirectories
  (patch directories) must be visible too. The renderer adds ancestors of
  directories with a group makefile automatically.
- Patches and hashes in directories the package itself does not own - the reason
  for `br2 preflight`.
- `.mk` files that read another package's directory (gettext-tiny reading gettext-gnu's
  patches, a rust package reading `package/rustc`): declared per project with
  [`extra_view`](../reference/project-json.md#extra_view).
- Dangling symlinks in the source tree: Buck2 cannot see them as inputs, so the renderer
  records them as data (`path -> target`) and the action recreates them in an
  overlay.

`scripts/check-narrow.py` finds the rest by construction, comparing every make variable
between the full tree and the view.

### `.git` is hidden

Buildroot asks git for `BR2_VERSION_FULL` (`-dirty` depends on the state of the
worktree) and for `SOURCE_DATE_EPOCH`. The namespace mounts an empty directory over
`.git` in both trees, so both fall back to fixed values from the Makefile and results do
not depend on who ran `git status` last. For a `BR2_EXTERNAL` tree a version string
embedded from its git state is hidden the same way.

## Config slices

The `.config` is an input to every package, and it is the coarsest one: any change to it
would rerun everything, and each action ran Kconfig's `syncconfig` over the whole tree.

**Ownership.** `br2_owners` scans every `Config.in*` under `package/` and records which
directory declares each `BR2_*` symbol. Of the 8,900 symbols a typical Buildroot tree
declares, roughly 2,900 are in a real `.config` and about 1,700 of those belong to a
package; the rest are global (architecture, toolchain, system, filesystem options).

**Slice.** A package's slice contains the `.config` lines whose symbol is

1. **global** (its owner is not under `package/`), or
2. **owned** by the package's directory, its ancestors, or the directories of its
   dependency closure, or
3. **mentioned** in the package's own `.mk` files (`\bBR2_[A-Z0-9_]+`; a trailing `_` makes
   it a prefix), or
4. referenced by the infrastructure makefiles (a couple of dozen package symbols,
   such as `BR2_PACKAGE_BASH`), or
5. a `BR2_PACKAGE_PROVIDES_*` / `BR2_PACKAGE_HAS_*` symbol: the choice of which package
   implements a virtual package (`libgles`, `libegl`, ...) is read by whichever package
   is built on it.

Dropped lines belong to packages this one cannot depend on. Adding
`BR2_PACKAGE_STRACE=y` flips one line that is in nobody else's slice.

Two details make the slices stable:

- **Only `BR2_X=value` lines are kept.** `# BR2_X is not set` lines and Kconfig comment
  blocks appear and disappear with the *visibility* of unrelated options, and leaked
  into every slice on the first attempt.
- **The slice ships its own `auto.conf`.** `auto.conf` is read only by the
  Makefile's `prepare` step, so seeding it makes `prepare` a no-op: no `syncconfig`, no
  Kconfig, no `Config.in` files and no `conf` binary in a package action.

The slice is a deterministic tar (sorted, fixed mtime and owner), so an unchanged slice
has an unchanged digest and Buck2's **early cutoff** stops the invalidation: a config
change reruns about thirty tiny slice actions, but a package rebuilds only if *its* slice
changed.

### Deliberately conservative

All global symbols go to every package. Changing the optimization level or the
architecture correctly rebuilds everything. Splitting them - for example, symbols that
only the rootfs uses - is a possible refinement, not a soundness need.

## Known limits

- Global config symbols and edits to any infrastructure file still rebuild everything.
- Slicing is static analysis, validated by `check-narrow.py` for the current
  configuration; rerun it after adding packages.
- The ambient host toolchain (gcc, perl, rsync, make) is not part of any key: see
  [Wrapped and native](wrapped-and-native.md#the-host-tools-are-not-in-the-key).
- The mount namespace needs `CAP_SYS_ADMIN`.
