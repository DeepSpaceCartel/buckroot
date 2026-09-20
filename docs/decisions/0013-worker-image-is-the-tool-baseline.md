<title>ADR-0013</title>

# ADR-0013: The worker image is the tool baseline

Status: accepted
Date: 2026-09-20

## Context

Wrapped actions run Buildroot's own `make`, which uses ambient host tools: `gcc`, `perl`, `rsync`,
`bison`, `git`. The action key does not cover them. Locally that is invisible, because every tool is on the
machine; on a remote worker it fails, or worse, differs quietly. The first remote Car Thing cells failed in
100 seconds because Buildroot 2024.05's dependency check wants `git` and the worker image had none.

## Decision

The runner image (`toolkit/infra/buildbarn/runner/Dockerfile`) is the *only* definition of what a remote
action can use, and it is pinned in the repository. A missing tool is fixed by adding it there and
recreating the runner, never by changing the action. The package list is the union of what the projects
in `experiments/` need; an addition should say which failure caused it (so far: `git`, for Buildroot 2024.05's
dependency check).

## Consequences

- **Easier**: one file answers "what does a remote action have?", and remote failures of this kind are
  a one-line change with an obvious test (rerun the cell).
- **Harder**: the image grows with every project's needs, and a change to it is not part of any action
  key. Two workers on different image versions could still disagree. The fix for that (put an image digest
  in the platform properties so the key covers it) is not done yet; see
  [Status and roadmap](../project/status.md).
- **Harder**: local execution has a larger, unpinned tool set, so a build can pass locally and fail
  remotely. The remote cells exist to catch exactly that.
