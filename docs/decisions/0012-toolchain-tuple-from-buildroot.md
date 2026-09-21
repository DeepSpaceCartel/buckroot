<title>ADR-0012</title>

# ADR-0012: The toolchain tuple comes from Buildroot

Status: accepted
Date: 2026-09-20

## Context

A Buildroot sysroot lives at `host/<tuple>/sysroot`, and the tuple depends on the configuration:
`aarch64-buildroot-linux-gnu` for an internal glibc toolchain, `aarch64-buildroot-linux-musl` for a musl
or Bootlin one, `arm-buildroot-linux-musleabihf` for FunKey. The first native rules were written against
`helloworld` and hard-coded the musl tuple. On the Car Thing (glibc), the native skeleton then created its
`lib64 -> lib` symlinks in a sysroot nobody used; glibc installed a real `usr/lib64`, and
`host-gcc-final` failed with `ld: cannot find crti.o` about fifty minutes into the build. Nothing
pointed at the cause.

## Decision

The tuple is data, not code. `br2 extract` asks Buildroot for `GNU_TARGET_NAME` and records it in
`golden/model.json`; `br2 render` writes `br2/generated/target.bzl` with `TARGET_TUPLE`, and native rules
load it. `render` refuses a model that has no tuple.

## Consequences

- **Easier**: a project with any toolchain gets correct sysroot paths without editing the toolkit; the value
  is checked into the model, so a stale model is caught by `render --check`.
- **Easier**: the mistake cannot recur silently: a missing tuple is an error at render time.
- **Harder**: an extra generated file, and the rules depend on the generated package `//br2/generated`.
- **Not solved**: other configuration assumptions in native recipes (glibc versus musl, merged `/usr`).
  Recipes raise on configurations they do not implement, and `compare-pkg.py` against the wrapped artifact is
  the check; it must compare the *native* target (`//br2/native/<pkg>`), not the wrapped label.

## Addendum, 2026-09-21: the sysroot's directory name is data too

The tuple was not the only assumption: the rules also wrote `sysroot` after it. Bottlerocket's SDK patches Buildroot
(`STAGING_SUBDIR = $(GNU_TARGET_NAME)/sys-root`), so the native `host-skeleton` and every `staging:` install went to
`host/<tuple>/sysroot`, and `host-gcc-final` failed again with `ld: cannot find crti.o`, this time in a project that
had the right tuple. `br2 extract` now also records `STAGING_SUBDIR` (`staging_subdir` in `golden/model.json`) and
`br2 render` writes it to `target.bzl` as `STAGING_SUBDIR`; `rules.bzl` and `host-skeleton` use it. A model without the field
falls back to `<tuple>/sysroot`, so no other project's rendered files or action keys change. The native
recipes of the Bootlin toolchain (`toolchain-external-bootlin`) still name the sysroot themselves; they describe one
fixed external toolchain, not a configurable one.
