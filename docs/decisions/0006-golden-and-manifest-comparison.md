<title>ADR-0006</title>

# ADR-0006: Golden build and manifest comparison

Status: accepted
Date: 2026-09-20

## Context

"The Buck2 build works" needs a definition. Booting is a weak one: an image without
`/var/log`, or with unstripped binaries, boots. Byte-identical images are too strict:
filesystem images embed inode numbers, allocation order and timestamps that are not
properties of the contents.

## Decision

The reference is a **golden build**: plain `make`, in the same namespace, with the same
configuration fragment. The criterion is **manifest equality**: a JSON manifest with every
path's type, mode, owner, link target, size and content hash, compared with
`fs-manifest.py diff`. Paths whose content is random on every build of the golden itself
(a salted password hash) are listed in `manifest_ignore` and compared by presence.

## Consequences

- **Easier**: a difference names a path. It caught missing dangling symlinks, unstripped
  binaries and unapplied patches, all in builds that passed and booted.
- **Easier**: the same manifest format handles ext4, squashfs and tar images.
- **Harder**: the golden build costs the full time of a plain build, once per configuration
  change.
- **Harder**: the criterion says nothing about behaviour that is not in the filesystem;
  a boot test complements it where a target can be booted.
- **Deviations are recorded.** The golden runs with the instrumentation's configuration
  fragment, which can differ from the project's own defconfig; `br2 golden --vanilla`
  and the `notes` field document by how much.
