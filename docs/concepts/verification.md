<title>Verification</title>

# Verification

"It builds" proves little: a Buck2 graph that quietly drops a file, an unstripped
binary or a missing symlink still produces an image. buckroot's claim is stronger - the
Buck2 root filesystem is **the same** as the one plain `make` produces - and it checks
that claim in several layers.

## The golden build

`br2 golden` runs plain `make` on the same Buildroot tree, in the same fixed-path
namespace, with the same configuration fragment (per-package directories and
reproducible timestamps, plus the project's `config_fragment`). It is the reference. It
writes:

- `golden/rootfs.manifest.json` - the [manifest](#the-manifest) of the resulting image;
- `results/golden.json` - how long the build took.

`br2 golden --vanilla` builds the project's defconfig untouched. That result is not what
Buck2 is compared with; it documents how far the instrumented configuration is from the
project's own.

## The manifest

`scripts/fs-manifest.py scan` reduces a root filesystem image to a JSON manifest, one
entry per path: type, mode, owner, symlink target, size and SHA-256 of the content. It
reads ext4 (through `debugfs`), squashfs and tar images.

`scripts/fs-manifest.py diff A B` reports `only in A`, `only in B` and `differs` (with the
fields that differ). `IDENTICAL` means no difference in any path.

Byte-identical *images* are deliberately not the criterion: filesystem images embed
inode numbers, allocation order and superblock timestamps that say nothing about the
contents. The manifest is what a user of the image can observe.

### Paths that are random on every build

A few files change on every build of the *golden itself*. The usual case is
`/etc/shadow` with `BR2_TARGET_GENERIC_PASSWD_METHOD="sha-256"`: `mkpasswd` uses a random salt,
so the hash - and even the file's length, as the salt length varies - differs from
run to run. List these in `manifest_ignore`. They are then compared by presence only, and
the ignored paths are part of the project's recorded deviations.

## Layers of evidence

| Layer | Tool | What it proves |
|---|---|---|
| A package's view is complete | `br2 preflight` | every package's extract and patch steps succeed in its view, with the same patches applied as in the golden |
| A view and slice change nothing | `scripts/check-narrow.py` | every make variable is identical between the full tree and the view; the view hides packages outside the closure |
| One native package equals the wrapped one | `scripts/compare-pkg.py` | files, modes, hashes, symlinks, stamps and `.files-list*` are equal |
| The root filesystem equals `make`'s | `scripts/fs-manifest.py diff` | every path, mode, owner and content hash |
| The image works | boot test (helloworld: QEMU) | it starts and runs the program |
| The graph is reproducible | `br2 render --check` | the checked-in `BUCK` files match the model |

## What the manifest caught

Each of these builds passed and *booted*; only the manifest showed them:

- **Missing dangling symlinks.** Buck2 cannot see a dangling symlink as an input, so it
  never reached a remote worker: the image silently lacked `/var/log`, `/dev/fd`,
  `/etc/mtab` and twelve more (15 of 369 entries). They are now declared as data.
- **Unstripped binaries.** The rootfs action's host tree lacked the cross `strip`, so
  every binary and shared library kept its symbols. `host-binutils` is not in Buildroot's
  `PACKAGES` and buckroot's per-package host trees are deltas rather than complete trees,
  so the merge missed it. The rootfs action now merges every package's host delta first.
- **Unapplied patches.** A patch directory outside the view meant a package built without
  its patches - visible only as a different binary.

## What it cannot see

- Behaviour that does not show up in the filesystem (a kernel that boots differently).
  The image must be booted for that; helloworld does it in QEMU, hardware targets
  need a device.
- Differences in the *host tools* used to build. See
  [Wrapped and native](wrapped-and-native.md#the-host-tools-are-not-in-the-key).
