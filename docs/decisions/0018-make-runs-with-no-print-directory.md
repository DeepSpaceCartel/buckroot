<title>ADR-0018</title>

# ADR-0018: Every `make` of a build runs with `--no-print-directory`

Status: accepted
Date: 2026-09-21

## Context

The first golden build of Home Assistant OS failed twice, in the same package and at the same line: `rtl8821cu`, a kernel module,
stopped with `Makefile:243: *** multiple target patterns.  Stop.` Nothing else failed, so it was not a race.

Buildroot's kernel-module infrastructure passes the kernel release to the module's Makefile as `KVER=` followed by a backtick
command, `$(MAKE) ... -C <linux> --no-print-directory -s kernelrelease`, whose output the shell substitutes into the command line.
The `make` that runs `kernelrelease` inherits `MAKEFLAGS`, and a sub-make gets `w` (print directory) there whenever its parent prints
directories. GNU make 4.3 then prints `make: Entering directory ...` and `make: Leaving directory ...` to **standard output**, even
with `-s` and even with `--no-print-directory` on that command line. `KVER` therefore became three lines, and the words with a colon
(`make[1]:`) reached the kernel's Makefile as goals, which it reads as target patterns. Reproduced with a two-line Makefile in the
worker image.

Upstream builds do not hit this because they run the top-level `make` in a way that leaves `w` out of `MAKEFLAGS`. Both of ours
printed "Entering directory" (the golden script and the Buck2 action), so both would fail, on any project with such a module.

## Decision

The golden script and the package action (`br2/pkg_action.py`, `MAKE`) pass `--no-print-directory` to the top-level `make`. Sub-makes
inherit it through `MAKEFLAGS`, so none of them gets `w`. It changes only log output, not any file the build produces.

## Consequences

- **Easier**: kernel-module packages that capture `kernelrelease` build, in the golden and in an action.
- **Harder**: `MAKE` is an action input, so every action key changes once (the caches of earlier runs are not reused). The manifests
  do not change.
- **Not solved**: any other package that captures the output of a sub-make would be affected by the same class of stray output; this
  is the only one seen so far.
