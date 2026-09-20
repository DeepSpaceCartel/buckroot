<title>Decision log</title>

# Decision log

Architecture Decision Records: each captures a single real design decision, the
context that led to it, and its honest trade-offs, so nobody has to reconstruct "why
did we do it this way?" from git blame later. See [adr.github.io](https://adr.github.io/)
for the convention this follows. Numbers are sequential and never reused, even for a
rejected or superseded decision.

An ADR is a record of a decision *already made*, kept accurate after the fact
(superseded by a new ADR when circumstances change, never rewritten in place). The
first eleven were written down once the design had settled, from the decisions made while
building it.

| # | Decision | Status |
|---|---|---|
| [0001](0001-one-target-per-package.md) | One Buck2 target per Buildroot package | accepted |
| [0002](0002-wrapped-packages-run-make.md) | Wrapped packages run Buildroot's own make | accepted |
| [0003](0003-enforced-input-views.md) | Enforced input views instead of declared inputs alone | accepted |
| [0004](0004-fixed-path-namespace.md) | Fixed-path mount namespace | accepted |
| [0005](0005-config-slices.md) | Config slices by symbol ownership | accepted |
| [0006](0006-golden-and-manifest-comparison.md) | Golden build and manifest comparison | accepted |
| [0007](0007-vendored-sources.md) | Vendored sources | accepted |
| [0008](0008-buildbarn-backend.md) | Buildbarn as the remote backend | accepted |
| [0009](0009-dev-mode-vs-strict.md) | Dev mode versus strict mode | accepted |
| [0010](0010-cache-salt-per-cell.md) | A cache salt per measured cell | accepted |
| [0011](0011-project-json.md) | project.json is the only project input | accepted |
| [0012](0012-toolchain-tuple-from-buildroot.md) | The toolchain tuple comes from Buildroot | accepted |
| [0013](0013-worker-image-is-the-tool-baseline.md) | The worker image is the tool baseline | accepted |
| [0014](0014-view-entries-are-declared-inputs.md) | Every view entry is a declared input, and remote execution proves it | accepted |
| [0015](0015-buildbarn-on-kubernetes.md) | Buildbarn on a dedicated Kubernetes cluster with autoscaled worker pools | accepted |
