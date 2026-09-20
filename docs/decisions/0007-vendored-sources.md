<title>ADR-0007</title>

# ADR-0007: Vendored sources

Status: accepted
Date: 2026-09-20

## Context

Buildroot fetches sources at build time, from mirrors and upstream URLs, into a
download directory. Buck2 wants fetched artifacts as explicit inputs with digests. Real
projects break the simple mapping: git sources, packages that ship only a SHA-512 hash,
URLs that no longer exist, and downloads whose result depends on the fetch tool.

## Decision

Sources reach Buck2 in one of two ways, chosen per project: `http` (plain URL with a
SHA-256 becomes a Buck2 `http_file`) or `vendored` (`br2 fetch` downloads every source
into `sources/` and records its digest in `golden/sources.lock.json`; the generated
`sources/BUCK` exposes them as files). Real projects use `vendored`.

## Consequences

- **Easier**: builds never touch the network, so a dead upstream URL cannot break a
  release and remote workers need no internet access.
- **Easier**: every source has a recorded digest.
- **Harder**: the vendored tree is large and is not committed; `br2 fetch` must be run
  once per checkout. The lock file is committed.
- **Harder**: a source that Buildroot itself cannot fetch (a dead URL) has to be supplied by
  hand.
