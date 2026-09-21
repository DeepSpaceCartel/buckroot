# Toolkit review: ranked findings

*Written before the refactor phase, which has not started (see [Handover](handover.md)). Nothing here has been changed in the code yet, except where a line says fixed.*

Skills read: `core-principles` (SKILL.md, tie-breakers), `engineering-practices` (SKILL.md, refactoring.md, testing.md), from `~/.agents/skills/`.
Still to read when acting: dry, fail-fast, explicitness, separation-of-concerns, security-practices.

## Constraint that shapes every step
Every file under `toolkit/br2/` (pkg_action.py, slicing.py, native_pkg.py, rules.bzl, ...) is a declared input of the
actions, so ANY edit there changes every action key and empties every cache. `scripts/` (br2, br2buck.py,
fs-manifest.py, ...) is not an action input; it only changes keys if the BUCK it renders changes (`render --check`
proves that). Plan: do the `scripts/` refactors first (no key change), batch all `br2/` edits into one deliberate,
documented key change with a helloworld matrix + one real project verification after it.

## Ranked by value / risk

| # | Finding | Principle / practice | Value | Risk |
|---|---|---|---|---|
| 1 | The repository has no tests at all. Pure logic (slice_config, make_keep, scope_dirs, label/dep_label/bzl_list/bzl_dict, normalize_pkg_dir, parse_hash_file, urls_for, fs-manifest diff and scan_tree, config_flags/instance/render_md, parallel_jobs, view_entries) is only checked by 30-minute builds. | testing (characterization first), refactoring (safety net) | very high | none (additive; `render --check` on helloworld and each real project's committed BUCK files is the existing snapshot for model rendering) |
| 2 | `golden_job` (scripts/br2) mixes shell-script text, Job manifest, kubectl I/O and result extraction in one 63-line function; the Job spec cannot be tested without a cluster. Split: pure `render_job(...)` (unit-testable, dry-run already prints it) + thin apply/collect. | separation of concerns | high | low (scripts/, no key change) |
| 3 | `golden_job` takes `git remote get-url origin` verbatim into the Job spec and logs; a remote URL with an embedded token would leak into the cluster object and pod log. Strip userinfo (or refuse). | least privilege / security-practices (secrets) | high | low |
| 4 | scripts/br2 keeps run configuration in module globals mutated by argument parsing (`POOL`, `RE_ENDPOINT`); `instance()` and `config_flags()` read them implicitly. Pass a small config object (or explicit args). | explicitness, low coupling | medium | low; covered by the tests from #1 (flags printed by `--dry-run` are the characterization output) |
| 5 | Actions read `BR2_JOBS`, `BR2_WORK_DIR`, `BR2_KEEP_WORK` from the environment inside pkg_action.py: hidden inputs not in the action key; `int(os.environ["BR2_JOBS"])` fails with a bare ValueError. Output is unaffected (Buildroot is reproducible), so keep the inputs but validate (fail fast, clear message) and document them as non-key inputs. | explicitness, fail fast | medium | changes key (br2/): batch |
| 6 | Same fact in several places: `_project_root()` copy in pkg_action.py and slicing.py; `MTIME`/`FIXED_MTIME` (1_000_000_000) in slicing.py and native_pkg.py; tree-root names `buildroot-src`/`buildroot-external` and the `SRC`/`EXT` mapping in br2buck.py, pkg_action.py, slicing.py. A shared `br2/common.py` would remove them, but each action would then need one more declared input. Rule of three: `_project_root` and MTIME have only two copies each: leave, comment the pairing. Tree roots (three files): candidate. | dry (wrong-abstraction warning), high cohesion | low-medium | changes key (br2/): batch |
| 7 | Long functions: `br2buck.extract` (68 lines), `check-narrow.check` (82), `render_pkg_dir` / `outward_links` (48 each). Extract Function only where tests from #1 pin the behaviour first. | refactoring (long function) | low-medium | low for scripts/ |
| 8 | Three unrelated `sh()` helpers (print+cwd, check=True, ...). Different semantics, each 2 lines: not duplication worth a shared module. Rejected. | dry (wait for third occurrence with same semantics) | - | - |
| 9 | Performance: nothing measured to justify work; the dominant costs are Buildroot builds. Not touched. | performance (measure first) | - | - |

## Rejected up front
- A shared module/interface for `sh`, an abstraction over Buck2 vs Buildroot back-ends, or a plugin system for variants (yagni, one implementation each).
- Restructuring rules.bzl (604 lines): every step changes all action keys; refactor only with a behavioural reason.
- Type-annotation or formatting sweeps (no behaviour value; large diffs).

## Proposed step order (one commit each, Conventional Commits, checks after each)
1. test: characterization tests for scripts/ pure logic + `render --check` wired as a test on helloworld (no code change).
2. fix(br2): golden --k8s strips credentials from the remote URL (#3), with a test.
3. refactor(br2): extract pure `render_job` (#2), Job JSON unchanged (test compares before/after).
4. refactor(br2): explicit run configuration instead of module globals (#4), flags unchanged (test).
5. [one deliberate key change] refactor(br2): validate env inputs, single tree-root definition (#5, #6); ADR; helloworld matrix + Car Thing wrapped/native local-cache after.
6. refactor(br2buck/check-narrow): split the long functions (#7), pinned by step 1 tests.
Full re-verification at the end: helloworld matrix (8 cells) + one real project, wrapped and native local-cache; needs CPU or the cluster.

## Added while testing (2026-09-20 and 2026-09-21)
- render is not idempotent on a fresh tree: `br2buck.py render` run twice differs in buildroot-src/BUCK (util-linux-libs edge: generated subdir
  target `//buildroot-src/package/util-linux/util-linux-libs:inputs` on pass 1, `//buildroot-src/package/util-linux:file.util-linux-libs` on pass 2).
  Rendered BUCK files are generated (not committed), so two machines can end up with different action inputs/keys. Value: high (cache identity);
  fix: make the first pass see the state the second one sees, and add a characterization test (render twice, expect no change).
- br2 setup fetched buck2 with a tool (zstd) the worker baseline lacks -> golden --k8s needed --no-buck2 (done).
- golden results go through the pod log as a base64 tar; fine for manifests (KBs), not for images.
- `br2 preflight` before `br2 golden` dies with a FileNotFoundError traceback on `<cache>/golden/.config` (2026-09-21, FunKey-OS). Fail fast at the
  boundary: check the prerequisite and say "run `br2 golden` first". Same class as the missing-view exit-97 fix.
- KEDA (2026-09-21): bb-scheduler's Prometheus metrics are counters (`buildbarn_builder_in_memory_build_queue_tasks_scheduled_total{assignment="Queue"|"Worker"}`,
  `workers_created_total`...), no queued/executing gauge. Options: scale on `increase(tasks_scheduled_total{assignment="Queue"}[2m])` (demand proxy),
  or a tiny exporter reading BuildQueueState (port 8984) for the real queue length. Worker count is manual (`worker_replicas`) until then.
- idle reporter (chart, 2026-09-21): pod-deletion-cost said busy for 2 of 7 workers while CPU showed 3 executing (4.2 and 3.1 cores on
  "idle" pods); either the "non-empty /worker/build" test misses a phase (inputs being fetched, or a build dir path per size class) or it lags.
  Scale-in trusts this annotation: verify against the scheduler's worker state before relying on it (a wrong "idle" kills a running action).
- Operations (2026-09-21): a `terraform apply` that changes the Buildbarn chart rolls the frontend pods; a Buck2 client streaming an action
  through them gets "RE channel error: unavailable / EOF" and the cell fails (Car Thing wrapped remote-cache, at the last action). Never apply
  platform changes while cells run; longer term, the frontend Deployment should roll one pod at a time with a readiness gate (maxUnavailable 0),
  and Buck2 could retry infrastructure errors. Also: my pgrep-based waiters matched their own command line (anchor the pattern: `^python3 ...`).
- `br2 viewcheck` (2026-09-21, FunKey on the legacy pool): buck2 failed before any action ran and the CLI printed only "FAILED 143 packages";
  failures are reported through the parsed "Action failed" blocks, so an analysis/daemon/routing error is swallowed. Print buck2's tail when
  the exit is non-zero and no action failure was parsed (same for `br2 dev` and `build`: check `failures()` callers).
- `br2 viewcheck`/`build`/`dev` in an experiment without tools/buck2 (setup --no-buck2 was used) die with a FileNotFoundError traceback from subprocess:
  check for the binary once at startup (`BUCK2` missing -> "run `br2 setup`") for every command that needs it (fail fast, least surprise). (2026-09-21)
- `br2 fetch` without golden/model.json (a new experiment: the order is setup, extract, fetch) dies with a FileNotFoundError traceback; say "run `br2 extract` first"
  (same class as viewcheck without tools/buck2). Also document the new-experiment order in docs/reference/project-json.md. (2026-09-21)
- UNEXPLAINED golden vs Buck2 difference (2026-09-21, FunKey host-cmake 3.15.5): the same source, compiler (gcc 9.4) and flags (-std=gnu++17) compile
  cmWorkerPool.cxx in the golden (also under the action's exact env: env -i, BR2_NS_NET=off) but fail in the wrapped action with `std::int64_t does not name
  a type` (the header includes only <stdint.h>). Something in the action's view or config slice changes what the file sees (cmConfigure.h is generated at
  configure time). Worked around with a package patch (both builds get it); the cause deserves a look: it is exactly the class of difference the
  project exists to find. Method that would settle it: keep the action's work dir (BR2_KEEP_WORK reaches only local actions) and diff the two build trees.
- Native recipes assume a Buildroot layout (2026-09-21): `skeleton` requires skeleton-init-sysv (fails for no-init and systemd configs) and `urandom-scripts` installs
  S01seedrng (a newer file; a 2021 tree has S20urandom). The failure is a Buck2 analysis error deep in a dependency chain. Fail fast where the list is read:
  validate `native` against each recipe's declared requirements at `br2 extract`/`build` and say which package cannot be native and why.
- render: symlinks to directories inside a carved package dir needed an export target (`package/go/go-src -> ../go-bin`); the generator only exported plain files.
- FIXED (2026-09-21): native recipes hard-coded the sysroot directory name (`sysroot`; Bottlerocket's SDK uses `sys-root`): now `STAGING_SUBDIR` from the model
  ([ADR-0012](../decisions/0012-toolchain-tuple-from-buildroot.md)). `stamp_dir` included a package's SUBDIR on an older Buildroot: fixed in `br2buck.stamp_dir`.
  Both were found by real projects; neither has a characterization test yet: add one each (a model with `build/host-lzo-2.10//buildroot-build` must render `build/host-lzo-2.10`).
- **Failure output is thrown away twice** (value: high, risk: low for the CLI part): `pkg_action.py` prints only the last 100 lines of a failing `make`, and warnings fill them, so the line that
  says why (`FAILED: ...`, `error:`) is missing (qemu `host-libglib2` cost hours). And `br2`'s failure summary (`failures()`) prints "Waiting on ..." progress lines instead of the
  action's stderr. The real stderr is in `buck2 log show` (JSONL, the `ActionError` events); the action work directory survives only with `BR2_KEEP_WORK=1` and local execution.
  Fix: print the first `error`/`FAILED` context plus the tail, keep the whole `make.log` as an output of a failed action (roadmap item), and have `failures()` read `ActionError`.
- `br2 matrix` used to overwrite `results/matrix.*` on every partial run: now a partial run keeps the other cells (fixed in the commit `fix(toolkit): sysroot directory name comes from Buildroot ...`; see `cmd_matrix`). Still untested.
- `render` after `extract` changes several `BUCK` files each time toolkit or model changed (`render --check` lists them); after a `br2-sync` an experiment can carry stale generated files
  (this cost a failed run: `STAGING_SUBDIR` missing from a stale `target.bzl`). `br2-sync` should re-render, or `render --check` should be part of every command that needs the files.
- A shared `br2/pkg_action.py` change (ADR-0018, `--no-print-directory`) invalidated every cache once. Batch further `br2/` edits with it, or rather: the next `br2/` change should carry a
  cache-key version note in the ADR so the cost is a decision, not a surprise.
- The golden of a project is not proven reproducible: FunKey's golden rebuilt after a legitimate patch also changed `/boot/zImage` and `/etc/shadow`. Build the golden twice on the same
  commit and compare before trusting one (a `br2 golden --k8s --twice`, or just a second run) and list what legitimately varies in `manifest_ignore`.
- Meson packages ignore `PARALLEL_JOBS` (`NINJA_OPTS` has no `-j`): ninja uses every visible CPU (16 on a worker node). Not the cause of the libglib2 failure (no OOM was recorded), but a hidden
  input to memory use; pass `NINJA_OPTS=-j$PARALLEL_JOBS` in the same `br2/` batch.

