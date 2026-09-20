<title>Iterating fast</title>

# Iterating fast

A cold build of a real project is hours; a debugging loop cannot be. These are the
tools that make it minutes, and the one rule that goes with them.

!!! warning "Numbers only from strict runs"
    Everything on this page changes what a build measures. `br2 matrix` and
    `br2 build` always run strict, with a clean state; never quote a timing from
    `br2 dev`.

## Build only what you are debugging

```bash
scripts/br2 dev --pkg libopenssl
```

Builds `libopenssl` and its dependencies, not the whole image. `--target` takes an
arbitrary Buck2 label and `--mode` any of the four modes (default `local-cache`, so
whatever was already built anywhere is reused).

## See every failure at once

`br2 dev` builds with `--keep-going`: independent failures all show up in one run, each
with the last lines of its own output, instead of the first one stopping the
build and hiding the rest.

## Do not rebuild GCC because you edited a script

In dev mode the toolkit's own scripts (`pkg_action.py`, `br2-ns.sh`, ...) are
referenced by path instead of being declared action inputs, so editing them does not
change any action key:

```bash
scripts/br2 dev --strict     # the opposite: scripts are inputs (what a measured run does)
```

The price is that a dev-mode cache hit can be stale with respect to a script change.
Rebuild strict before trusting a result. See
[ADR-0009](../decisions/0009-dev-mode-vs-strict.md).

## Check patches and views in minutes

```bash
scripts/br2 preflight                    # every package
scripts/br2 preflight --pkg mesa3d       # one
```

Runs each package's extract and patch steps in its view and compares the applied
patches with the golden's. It catches an `extra_view` you still need before you
spend an hour compiling.

## Keep a heavy package from taking the machine

Some packages (the compiler, the kernel, Mesa, host Python) use all cores and a lot
of memory. Buck2 runs several actions in parallel, so two of them at once can
be killed by the OOM killer. Give them a weight:

```json
"heavy": ["host-gcc-initial", "host-gcc-final", "gcc-final", "linux", "mesa3d"],
"heavy_weight": 4
```

An action with a weight of the machine's core count runs alone. `heavy_weight`
defaults to the CPU count.

## Rebuild exactly one package

`salts` is a package-to-string map. Changing a value changes that package's action key
and nothing else's:

```json
"salts": {"linux": "retry-2"}
```

## Iterate on a cut-down config

```bash
toolkit/bin/br2-new myboard-lite --like experiments/myboard \
    --fragment 'BR2_PACKAGE_MESA3D=n' --drop-heavy
```

Creates a sibling experiment with its own model, golden and Buck2 state that
hard-links the Buildroot tree, `dl/` and `sources/` (no second download). A lite
configuration turns a two-hour debugging loop into minutes; the toolkit fixes you
find there apply to the full one.

## Look at what an action can see

```bash
scripts/show-inputs.py libopenssl            # the view entries
scripts/show-inputs.py libopenssl --config   # ... and the sliced .config lines
```

Same code as the Buck2 rules, so it is the truth.
