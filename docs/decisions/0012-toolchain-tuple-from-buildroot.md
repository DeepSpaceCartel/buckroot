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
