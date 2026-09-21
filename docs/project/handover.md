<title>Handover</title>

# Handover

Written on 2026-09-21, when the machine that ran this work and the Kubernetes cluster were destroyed. Everything below is what a new
session needs; the code, the results and the decisions are in this repository. The per-project state is in [Results](results.md#status-when-testing-paused-2026-09-21).

## What exists and what does not

| Thing | State |
|---|---|
| Repository (`toolkit/`, `experiments/`, `docs/`, `terraform/`, `charts/`) | on `origin/main`; history was rewritten once on 2026-09-21 to remove two committed credential files, so old clones must `git fetch && git reset --hard origin/main` |
| Kubernetes cluster (Hetzner, Talos) and everything on it (Buildbarn, KEDA, Coder, caches, download volumes) | **destroyed**; `terraform/` recreates it (below) |
| `terraform/tailscale/` state (the tailnet policy file) | **not destroyed**: it owns the whole policy, and destroying it resets the tailnet to Tailscale's default |
| Golden manifests, models, results of every experiment | committed |
| Downloaded sources (`buildroot-src/dl`), Buck2 caches, build outputs, container images | gone; `br2 fetch` and a golden Job recreate them |

## Order of work that was planned

1. **Finish the testing phase** (scope: [Results](results.md)): Car Thing and helloworld are complete; still open are FunKey-OS, Home Assistant OS, and (extra projects) Bottlerocket SDK and qemu-x86_64.
   - **Home Assistant OS**: the golden failed at `rtl8821cu` because `make` printed directories into a captured `KVER` ([ADR-0018](../decisions/0018-make-runs-with-no-print-directory.md)). The fix is committed
     but the golden was never re-run. Run `br2 golden --k8s` (or plain `make` in the worker image), then `br2 viewcheck --mode remote`, then the matrix. Local cells need an idle machine with disk for a large build.
   - **FunKey-OS**: fixes since its last run: `patches/buildroot/0002` (libvorbis `.la`), `stamp_dir`, `extra_view` for gettext-tiny. Re-run the local wrapped cell and the matrix. The golden was rebuilt after the libvorbis patch and
     differs from the first one in `/boot/zImage` and `/etc/shadow` (unexplained): build it a second time on the same commit before comparing anything to it. Its remote cells need the `legacy` worker pool
     ([ADR-0017](../decisions/0017-tool-baseline-per-project-era.md)).
   - **Bottlerocket SDK**: wrapped remote cells are done; native cells need a re-run after the `STAGING_SUBDIR` fix (a native remote dev build passed); local and local-cache cells were not run.
   - **qemu-x86_64**: `host-libglib2` fails in the remote action after about 100 seconds and the cause is not known (not memory: `oom_kill 0`). Reproduce it in the worker image with local execution and `BR2_KEEP_WORK=1`, then read
     the kept `make.log` (the CLI shows only the last 100 lines of an action's output, and warnings fill them).
2. **Only then the refactor phase**: [Toolkit review](toolkit-review.md) has the ranked findings; the plan there (tests first, `scripts/` before `br2/`, one deliberate cache-key change) still stands.
   All action keys changed once with ADR-0018, so earlier cache contents and the numbers in [Results](results.md) predate that change; the refactor's final verification (helloworld matrix and one real project, wrapped and native, local-cache) covers it.
3. Optional after that: Batocera, Recalbox, OpenVoiceOS (see [Projects](projects.md)).

The full task statement, as given: test on real projects smallest first; per project a plain-Buildroot golden and both Buck2 variants in local, local-cache, remote and remote-cache (cold and warm for the cache modes) with every manifest IDENTICAL
to the golden or the difference explained in that project's docs; commit and push per phase; then refactor `toolkit/` with `~/.agents/skills/core-principles` and `engineering-practices` (findings ranked first, characterization tests before restructuring,
manifests IDENTICAL and action keys unchanged unless deliberate and documented, one Conventional Commit per step, ADRs for decisions), end with a short report (measured, refactored and why, rejected, remaining).

## Recreating the cluster

`terraform/README.md` is the procedure: `cluster/`, then `platform/`, then `coder-templates/` (needs a Coder session token). Secrets are 1Password references (`terraform/.env*1password`); the S3 state backend and the Hetzner token come from there.
Use a saved plan for every change (`terraform plan -out=<file>`, then `terraform apply <file>`; for teardown `plan -destroy -out`), never `-auto-approve`. What to know:

- The Hetzner project allows 5 servers and 8 dedicated vCPU and a new account is refused an increase ([ADR-0016](../decisions/0016-one-node-pool.md)): one schedulable control node plus one autoscaled pool of up to 4 nodes.
- The worker image must be published (`runner-image` workflow) and its digest set before `platform/` is applied; the `funkey` image feeds the `legacy` pool.
- A `platform/` apply that changes chart config rolls the Buildbarn frontend and fails any cell streaming through it: never apply while cells run.
- `br2 golden --k8s` needs a pushed commit and one golden Job per download claim (`golden-dl`, `-b`, `-c`, `-d` are `ReadWriteOnce`).
- Scale-from-zero works only because the scheduler's platform queue is predeclared; scale-in is safe only because workers drain first (`charts/buckroot-buildbarn/files/drain.sh`). Both are described in the [Kubernetes guide](../guides/kubernetes.md#how-autoscaling-works).
  The idle-reporter must trap SIGTERM (fixed) or drained pods linger until SIGKILL.

## Habits that saved time

- Run anything longer than a few minutes detached (`setsid nohup ... & disown`) and wait on a marker file or a pid (`kill -0`), not on the shell. A restarted session kills its children.
- Never `pkill -f <pattern>` or `pgrep -f <pattern>` in a shell whose own command line contains the pattern; anchor it (`^python3 scripts/br2 ...`).
- After `toolkit/bin/br2-sync <experiment>`, run `scripts/br2buck.py render`; never sync into an experiment while a build runs in it.
- The real error of a failed Buck2 action is in `buck2 log show` (the `ActionError` events), not in `br2`'s summary; `BR2_KEEP_WORK=1` with local execution leaves the action's work directory and `make.log`.
- Before a long remote run of a new project: `br2 viewcheck --mode remote`; before a long golden: `br2 preflight`.
- Each cell of a matrix is clean and strict; anything else (`br2 dev`, `--make-args=-k`, a second job on the same nodes) is for diagnosis only and gives no numbers.
- Do not name the private repositories this work grew out of anywhere in this repository or its commits.
