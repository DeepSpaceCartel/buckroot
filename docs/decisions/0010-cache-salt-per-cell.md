<title>ADR-0010</title>

# ADR-0010: A cache salt per measured cell

Status: accepted
Date: 2026-09-20

## Context

The results matrix must have *cold* cells that are really cold. With `buck2 clean` between
cells the local state is gone, but the shared Buildbarn cache is not, and an earlier cell's
uploads would make the next one warm. Fresh REAPI instance names were the obvious fix:
in Buildbarn's local storage they do nothing, because the storage ignores the instance name.

## Decision

Each measured cell gets a unique **cache salt** (`variant-mode-timestamp`), passed as
`br2.cache_salt` and added to every action's environment. A different environment is a
different action key, so the whole graph misses once; the warm rerun inside the cell
reuses the same salt and hits. Individual packages can also take a `salts` entry in
`project.json` to force just that package to rebuild, and it is added only when non-empty
so an unused salt does not change any key.

## Consequences

- **Easier**: cold means cold, provably: the cold run's `cached` count is 0.
- **Easier**: measurements are repeatable without wiping the cache between cells.
- **Harder**: cells do not share work, so a full matrix costs one full build per cold cell.
  For a project that builds for two hours, a full matrix is a day of compute.
