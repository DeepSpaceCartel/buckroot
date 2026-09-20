<title>ADR-0009</title>

# ADR-0009: Dev mode versus strict mode

Status: accepted
Date: 2026-09-20

## Context

The toolkit's own scripts (`pkg_action.py`, `br2-ns.sh`) are inputs of every action: a
change to them must rebuild everything, or a cache hit would hide a behaviour change.
During development that is a two-hour penalty for editing a comment.

## Decision

Two modes. **Strict** (the default; always used by `br2 build` and `br2 matrix`): the
scripts are declared inputs. **Dev** (`br2 dev`, `br2.dev_tools=true`): the scripts are
referenced by path and are not inputs, so editing them changes no action key. Dev results
are never used as numbers, and a dev-mode success must be repeated strict before it is
trusted.

## Consequences

- **Easier**: a toolkit edit no longer rebuilds the compiler; the edit-and-retry loop on a
  single package is minutes.
- **Harder**: dev-mode results can be stale against a script change. Dev keys are also
  different from strict ones, so a dev build does not warm the cache a strict build will
  use.
- The separation is enforced by construction, not by discipline: `matrix` passes
  `dev_tools=false` itself.
