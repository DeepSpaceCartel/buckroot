#!/usr/bin/env python3
"""Compare a natively built package artifact with the wrapped (`make <pkg>`) one.

  scripts/compare-pkg.py WRAPPED.tar NATIVE.tar

Compares what the rootfs action consumes: regular files (path, mode, sha256), symlinks
(path, target), the build stamps and the `.files-list*.txt` contents. Directory entries are
reported separately: wrapped artifacts list every directory of the (merged) tree, including
ones inherited from dependencies, which is harmless in the rootfs. Exit 0 = equivalent.
"""
import hashlib
import re
import sys
import tarfile

# Files Buildroot rewrites in the toolchain sysroot for every package that depends on the
# toolchain (ppd-fixup-paths, per-package-directory path fixing). Not consumed by the rootfs.
BENIGN = re.compile(r"/sysroot/usr/(lib/libstdc\+\+\.so\.[0-9.]+-gdb\.py|share/buildroot/gdbinit)$")


def load(path):
    files, links, dirs, texts = {}, {}, set(), {}
    hard = {}
    with tarfile.open(path) as tf:
        for m in tf.getmembers():
            name = m.name.rstrip("/")
            if m.islnk():
                hard[name] = m.linkname          # a hardlink is a file with its target's content
            elif m.isdir():
                dirs.add(name)
            elif m.issym():
                links[name] = m.linkname
            elif m.isfile():
                data = tf.extractfile(m).read()
                if "/.files-list" in name or "/.stamp_" in name:
                    texts[name] = "".join(sorted(data.decode().splitlines(True)))   # order is not significant
                else:
                    files[name] = (oct(m.mode & 0o7777), hashlib.sha256(data).hexdigest()[:16])
    for name, target in hard.items():
        if target in files:
            files[name] = files[target]
    return files, links, dirs, texts


def main():
    a, b = load(sys.argv[1]), load(sys.argv[2])
    bad = 0
    for label, x, y in (("file", a[0], b[0]), ("symlink", a[1], b[1]), ("stamp/files-list", a[3], b[3])):
        for k in sorted(set(x) | set(y)):
            if label == "stamp/files-list" and "/.files-list-" in k and k in x and k in y and x[k] != y[k]:
                # host/staging lists cover the MERGED tree (dependencies' files too); the native
                # artifact only knows its own. Fine if it lists a subset of what the wrapped one does.
                xs, ys = set(x[k].splitlines()), set(y[k].splitlines())
                if ys <= xs:
                    print(f"note: {k.split('/')[-1]}: native lists {len(ys)} of {len(xs)} (rest inherited from dependencies)")
                    continue
            if BENIGN.search(k):
                continue
            if k not in y:
                print(f"only in wrapped: {label} {k}")
                bad += 1
            elif k not in x:
                print(f"only in native : {label} {k}")
                bad += 1
            elif x[k] != y[k]:
                print(f"differs: {label} {k}: wrapped={x[k]!r} native={y[k]!r}")
                bad += 1
    extra = sorted(a[2] - b[2])
    print(f"directories only in wrapped (inherited layout, informational): {len(extra)}"
          + (f" e.g. {extra[:2]}" if extra else ""))
    print("EQUIVALENT" if not bad else f"{bad} difference(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
