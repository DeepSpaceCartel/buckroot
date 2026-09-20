#!/usr/bin/env python3
"""Write the artifact of a NATIVELY built package in the format the rootfs action expects
(the same layout pkg_action.pack_delta produces for a wrapped package):

  per-package/<pkg>/target/...   files the package installs into the target tree
  per-package/<pkg>/host/...     files it installs into the host tree (incl. the staging
                                 sysroot: host/<tuple>/sysroot/...)
  build/<pkg>-<ver>/.stamp_*     so `make` sees every step of the package as done
  build/<pkg>-<ver>/.files-list*.txt   what Buildroot records per package

  native_pkg.py --spec S.json --out pkg.tar

spec: {pkg, stamp_dir, stamps: [...], staging_dir: "host/<tuple>/sysroot",
       entries: [{tree: target|host|staging, dest, kind: file|link|dir, src?, mode?, target?}]}

The tar is deterministic (root:root, fixed mtime, sorted): equal inputs, equal digest.
"""
import argparse
import sys
import importlib.util
import io
import json
import os
import tarfile
from pathlib import Path

MTIME = 1_000_000_000
sys.dont_write_bytecode = True      # recipe.py must not leave __pycache__ in the Buck2-watched tree


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text())
    pkg, stamp_dir = spec["pkg"], spec["stamp_dir"]
    root = f"per-package/{pkg}"
    staging = spec["staging_dir"]

    def where(tree):                       # tree -> path below per-package/<pkg>
        return {"target": "target", "host": "host", "staging": staging}[tree]

    dirs = {"per-package", root, f"{root}/host", f"{root}/target", "build", stamp_dir}
    members = []                           # (path, kind, payload)
    lists = {"target": [], "host": [], "staging": []}
    entries = list(spec["entries"])

    def join(*parts):
        return "/".join(x.strip("/") for x in parts if x.strip("/"))

    for t in spec.get("trees", []):
        # Buildroot's SYSTEM_RSYNC: rsync -a --chmod=u=rwX,go=rX --exclude .empty, owner root.
        dest, tree = t["dest"], t.get("tree", "target")

        def add_file(rel, src, dest=dest, forced=t.get("mode"), tree=tree):
            exe = bool(os.stat(src).st_mode & 0o111)
            entries.append({"tree": tree, "dest": join(dest, rel), "kind": "file", "src": src,
                            "mode": forced or ("0755" if exe else "0644")})

        for item in t["srcs"]:
            rel, src = item["rel"], item["path"]           # rel: path below the tree's base dir
            if os.path.isdir(src):
                for dp, _, fns in os.walk(src):
                    sub = os.path.relpath(dp, src)
                    base = join(rel, "" if sub == "." else sub)
                    entries.append({"tree": tree, "dest": join(dest, base), "kind": "dir"})
                    for fn in sorted(fns):
                        full = os.path.join(dp, fn)
                        if fn == ".empty":
                            continue
                        if os.path.islink(full):
                            entries.append({"tree": tree, "dest": join(dest, base, fn),
                                            "kind": "link", "target": os.readlink(full)})
                        else:
                            add_file(join(base, fn), full)
            elif os.path.basename(rel) == ".empty":
                entries.append({"tree": tree, "dest": join(dest, os.path.dirname(rel)), "kind": "dir"})
            else:
                add_file(rel, src)
        for rel, target in t.get("links", {}).items():      # dangling symlinks, declared as data
            entries.append({"tree": tree, "dest": join(dest, rel), "kind": "link", "target": target})

    if spec.get("recipe"):
        # Package-specific logic Buildroot keeps in make macros (config-dependent symlinks,
        # sed edits...). apply(cfg, entries) may add entries or replace a file's content
        # with `data`. cfg holds only the symbols the package declared.
        cfg = json.loads(Path(spec["cfg"]).read_text()) if spec.get("cfg") else {}
        rs = importlib.util.spec_from_file_location("recipe", spec["recipe"])
        mod = importlib.util.module_from_spec(rs)
        rs.loader.exec_module(mod)
        mod.apply(cfg, entries, spec.get("inputs", {}))
    last = {}
    for e in entries:                       # a later entry for the same path wins (recipes may override)
        last[(e["tree"], e["dest"], e["kind"] == "dir")] = e
    entries = list(last.values())
    for e in entries:
        path = f"{root}/{where(e['tree'])}/{e['dest']}"
        parts = path.split("/")
        for i in range(2, len(parts)):
            dirs.add("/".join(parts[:i]))
        if e["kind"] == "dir":
            dirs.add(path)
            continue
        members.append((path, e))
        if not e.get("nolist"):             # e.g. the unpacked toolchain: not part of the install snapshot
            lists[e["tree"]].append(f"{pkg},./{e['dest']}\n")

    def add_dir(tf, name):
        ti = tarfile.TarInfo(name)
        ti.type, ti.mode, ti.mtime = tarfile.DIRTYPE, 0o755, MTIME
        tf.addfile(ti)

    def add_file(tf, name, data, mode=0o644):
        ti = tarfile.TarInfo(name)
        ti.size, ti.mode, ti.mtime = len(data), mode, MTIME
        tf.addfile(ti, io.BytesIO(data))

    with tarfile.open(args.out, "w", format=tarfile.GNU_FORMAT) as tf:
        for d in sorted(dirs):
            add_dir(tf, d)
        for path, e in sorted(members):
            if e["kind"] == "file":
                data = e["data"].encode() if "data" in e else Path(e["src"]).read_bytes()
                add_file(tf, path, data, int(e["mode"], 8))
            else:
                ti = tarfile.TarInfo(path)
                ti.type, ti.linkname, ti.mode, ti.mtime = tarfile.SYMTYPE, e["target"], 0o777, MTIME
                tf.addfile(ti)
        for s in spec["stamps"]:
            add_file(tf, f"{stamp_dir}/{s}", b"")
        add_file(tf, f"{stamp_dir}/.files-list.txt", "".join(lists["target"]).encode())
        add_file(tf, f"{stamp_dir}/.files-list-host.txt", "".join(lists["host"]).encode())
        add_file(tf, f"{stamp_dir}/.files-list-staging.txt", "".join(lists["staging"]).encode())
        add_file(tf, f"{stamp_dir}/.files-list-images.txt", b"")


if __name__ == "__main__":
    main()
