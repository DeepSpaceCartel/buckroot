#!/usr/bin/env python3
"""Tree manifest of a root filesystem image (ext2/3/4, tar, squashfs), and a diff of two manifests.

The manifest is the Tier 1 definition of "same filesystem": for every entry the
path, type, permission bits (incl. setuid/setgid/sticky), uid, gid, size and
sha256 (regular files), symlink target and device numbers. Timestamps, inode
numbers and directory sizes are deliberately not compared.

  fs-manifest.py scan  IMAGE [-o OUT.json] [--debugfs PATH]
  fs-manifest.py diff  A.json B.json          exit 0 identical, 1 differences

ext images are read with debugfs (no mount, no root); tar archives with tarfile; squashfs is
unpacked with unsquashfs as root into a temporary directory (owners and device nodes need it).
Stdlib only.
"""
import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

TYPES = {
    stat.S_IFDIR: "dir", stat.S_IFREG: "file", stat.S_IFLNK: "symlink",
    stat.S_IFCHR: "char", stat.S_IFBLK: "block", stat.S_IFIFO: "fifo",
    stat.S_IFSOCK: "socket",
}


def debugfs(debugfs_bin, image, command):
    r = subprocess.run([debugfs_bin, "-R", command, image],
                       capture_output=True, text=True, check=False)
    if r.returncode != 0:
        sys.exit(f"debugfs {command!r} failed: {r.stderr.strip()}")
    return r.stdout


def list_dir(debugfs_bin, image, path):
    """Yield (name, mode, uid, gid, size) for the entries of `path`."""
    # `ls -p -l` line: /inode/mode/uid/gid/name/size/   (dirs: .../name//)
    for line in debugfs(debugfs_bin, image, f'ls -p -l "{path}"').splitlines():
        if not line.startswith("/"):
            continue
        f = line.strip("/\n").split("/")
        ino, mode, uid, gid, name = f[0], int(f[1], 8), int(f[2]), int(f[3]), f[4]
        # skip . / .. and the empty slots mke2fs pre-allocates in lost+found
        if name in ("", ".", "..") or int(ino) == 0:
            continue
        size = int(f[5]) if len(f) > 5 and f[5] != "" else 0
        yield name, mode, uid, gid, size


def device_numbers(debugfs_bin, image, path):
    out = debugfs(debugfs_bin, image, f'stat "{path}"')
    for line in out.splitlines():
        if "Device major/minor number" in line:
            major, minor = line.split(":", 1)[1].split("(")[0].strip().split(":")
            return f"{int(major, 16)}:{int(minor, 16)}"
    return None


def scan(image, debugfs_bin):
    entries = {}
    with tempfile.TemporaryDirectory(prefix="fsmanifest-") as tmp:
        # One recursive extract gives file contents and symlink targets.
        debugfs(debugfs_bin, image, f'rdump / "{tmp}"')
        stack = ["/"]
        while stack:
            d = stack.pop()
            for name, mode, uid, gid, size in list_dir(debugfs_bin, image, d):
                path = d.rstrip("/") + "/" + name
                kind = TYPES.get(stat.S_IFMT(mode), "other")
                rec = {"type": kind, "mode": f"{stat.S_IMODE(mode):04o}",
                       "uid": uid, "gid": gid}
                local = os.path.join(tmp, path.lstrip("/"))
                if kind == "dir":
                    stack.append(path)
                elif kind == "file":
                    h = hashlib.sha256()
                    with open(local, "rb") as fh:
                        for chunk in iter(lambda: fh.read(1 << 20), b""):
                            h.update(chunk)
                    rec.update(size=size, sha256=h.hexdigest())
                elif kind == "symlink":
                    rec["target"] = os.readlink(local)
                elif kind in ("char", "block"):
                    rec["rdev"] = device_numbers(debugfs_bin, image, path)
                entries[path] = rec
    return {"entries": dict(sorted(entries.items()))}


def scan_tar(path):
    import tarfile
    entries, contents = {}, {}
    with tarfile.open(path) as tf:
        for m in tf.getmembers():
            name = "/" + m.name.lstrip("./").rstrip("/") if m.name not in (".", "./") else None
            if name is None or name == "/":
                continue
            rec = {"mode": f"{m.mode & 0o7777:04o}", "uid": m.uid, "gid": m.gid}
            if m.isdir():
                rec["type"] = "dir"
            elif m.issym():
                rec.update(type="symlink", target=m.linkname)
            elif m.isreg() or m.islnk():
                rec["type"] = "file"
                if m.islnk():
                    rec["_hardlink"] = "/" + m.linkname.lstrip("./")
                else:
                    h = hashlib.sha256()
                    f = tf.extractfile(m)
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                    rec.update(size=m.size, sha256=h.hexdigest())
                    contents[name] = rec
            elif m.ischr() or m.isblk():
                rec.update(type="char" if m.ischr() else "block", rdev=f"{m.devmajor}:{m.devminor}")
            elif m.isfifo():
                rec["type"] = "fifo"
            else:
                rec["type"] = "other"
            entries[name] = rec
    for name, rec in entries.items():                       # a hardlink is a file with its target's content
        target = rec.pop("_hardlink", None)
        if target and target in contents:
            rec.update(size=contents[target]["size"], sha256=contents[target]["sha256"])
    return {"entries": dict(sorted(entries.items()))}


def scan_tree(root):
    entries = {}
    for dp, dns, fns in os.walk(root):
        for n in sorted(dns + fns):
            full = os.path.join(dp, n)
            path = "/" + os.path.relpath(full, root)
            st = os.lstat(full)
            kind = TYPES.get(stat.S_IFMT(st.st_mode), "other")
            rec = {"type": kind, "mode": f"{stat.S_IMODE(st.st_mode):04o}", "uid": st.st_uid, "gid": st.st_gid}
            if kind == "file":
                h = hashlib.sha256()
                with open(full, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
                rec.update(size=st.st_size, sha256=h.hexdigest())
            elif kind == "symlink":
                rec["target"] = os.readlink(full)
            elif kind in ("char", "block"):
                rec["rdev"] = f"{os.major(st.st_rdev)}:{os.minor(st.st_rdev)}"
            entries[path] = rec
    return {"entries": dict(sorted(entries.items()))}


def scan_squashfs(path):
    with tempfile.TemporaryDirectory(prefix="fsmanifest-") as tmp:
        dest = os.path.join(tmp, "root")
        r = subprocess.run(["unsquashfs", "-no-progress", "-d", dest, path], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"unsquashfs failed: {r.stderr.strip()}")
        return scan_tree(dest)


def diff(a, b, ignore=()):
    ea, eb = a["entries"], b["entries"]
    problems = []
    for path in sorted(set(ea) | set(eb)):
        if path in ignore:
            continue
        if path not in eb:
            problems.append(f"only in A: {path}")
        elif path not in ea:
            problems.append(f"only in B: {path}")
        elif ea[path] != eb[path]:
            fields = sorted(k for k in set(ea[path]) | set(eb[path])
                            if ea[path].get(k) != eb[path].get(k))
            detail = ", ".join(f"{k}: {ea[path].get(k)!r} -> {eb[path].get(k)!r}"
                               for k in fields)
            problems.append(f"differs: {path}  ({detail})")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sc = sub.add_parser("scan")
    sc.add_argument("image")
    sc.add_argument("-o", "--out")
    sc.add_argument("--debugfs", default=shutil.which("debugfs") or "debugfs")
    df = sub.add_parser("diff")
    df.add_argument("a")
    df.add_argument("b")
    df.add_argument("--ignore", action="append", default=[], metavar="PATH",
                    help="skip this path (content that is random per build, e.g. /etc/shadow with a salted hash)")
    args = ap.parse_args()

    if args.cmd == "scan":
        img = args.image
        if img.endswith((".tar", ".tar.gz", ".tar.xz", ".tar.bz2", ".tgz")):
            manifest = scan_tar(img)
        elif img.endswith(".squashfs"):
            manifest = scan_squashfs(img)
        else:
            manifest = scan(img, args.debugfs)
        text = json.dumps(manifest, indent=1, sort_keys=True) + "\n"
        if args.out:
            with open(args.out, "w") as fh:
                fh.write(text)
            print(f"{len(manifest['entries'])} entries -> {args.out}")
        else:
            sys.stdout.write(text)
        return 0

    with open(args.a) as fa, open(args.b) as fb:
        problems = diff(json.load(fa), json.load(fb), set(args.ignore))
    for p in problems:
        print(p)
    print("IDENTICAL" if not problems else f"{len(problems)} difference(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
