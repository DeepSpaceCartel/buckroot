<title>ADR-0011</title>

# ADR-0011: project.json is the only project input

Status: accepted
Date: 2026-09-20

## Context

Each Buildroot project differs in defconfig, external tree, Buildroot version, package
quirks and layout. If the differences are scattered across the generator, the rules and
the scripts, adding a project means editing the toolkit, and the toolkit stops being
reusable.

## Decision

A project is a directory with one file, `project.json`. Everything else in an experiment
directory has a fixed name and a fixed meaning (`buildroot-src/`, `buildroot-external/`,
`common/`, `native/`, `golden/`, `results/`). The toolkit is copied in with `br2-sync`
(the copies are git-ignored), so each experiment is self-contained, and every generated
Buck2 file is the same shape everywhere. Project quirks are data: `extra_view`,
`heavy`, `salts`, `config_fragment`, `manifest_ignore`, `native`.

## Consequences

- **Easier**: a new project is a file and the loop `setup, extract, golden, dev, matrix`;
  no toolkit edits unless the project exposes a real toolkit gap, in which case the fix
  lands in the toolkit and every project benefits.
- **Easier**: the toolkit can be tested on a tiny project (`helloworld`) and applied to a
  large one unchanged.
- **Harder**: a quirk with no data field (a package needing a special action) has no home
  yet; `native/<pkg>/BUCK` is the escape hatch.
- **Harder**: vendoring by copy means an experiment can lag the toolkit; `br2-sync` is a
  one-line refresh.
