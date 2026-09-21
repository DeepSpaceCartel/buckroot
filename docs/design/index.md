<title>Design</title>

# Design

Proposals and open problems that are **not implemented**. Each page states the problem with the evidence gathered so far, the options, what
is unknown, and how to decide. They are the place to read before changing the design; when one is built, its decision moves to an
[ADR](../decisions/index.md) and the page says so.

| Note | Problem | State |
|---|---|---|
| [Worker environment in the action key](worker-environment-in-the-key.md) | the tools a wrapped action uses (compiler, `perl`, `configure` probes) are not part of its cache key | proposed, not started |
| [Action sizes and execution platforms](action-sizes.md) | every worker is the same size; 96% of actions need a third of it, a few need more | proposed, routing not yet proven |
| [Directory-tree package outputs](../project/status.md#directory-tree-package-outputs) | package results are one tarball each: no file-level deduplication, unpacked per action | idea, untested |
| [Stepped variant](../walkthrough/stepped.md) | one action per Buildroot step | design; gated on a measurement |
| [Importing from Buildroot](../concepts/importing-from-buildroot.md) | leaving Buildroot's `make` while keeping its package data | sketch |
