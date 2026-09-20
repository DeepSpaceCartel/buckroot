#!/usr/bin/env python3
"""Config slicing for narrow action inputs (used by the `owners` and `slice` Buck2 actions).

  slicing.py owners --spec S.json --out owners.json
  slicing.py slice  --spec S.json --out pkg.slice.tar

Kept apart from pkg_action.py on purpose: that script is an input of every package action,
so editing it rebuilds everything. Slicing logic may change freely: a changed slice is
detected by its digest, and only packages whose slice really changed are rebuilt.

`owners`: which directory's Config.in declares each Kconfig symbol, plus the symbols
Buildroot's own (non-package) make files read directly.
`slice`: the part of .config one package can read (see make_keep). Only `BR2_X=value`
lines are kept. `# BR2_X is not set` lines and Kconfig `comment` blocks are comments to
make and are equivalent to an absent symbol, but they appear and disappear with the
visibility of unrelated options, so keeping them would leak unrelated changes.
"""
import argparse
import io
import json
import os
import re
import sys
import tarfile
from pathlib import Path


def _project_root():
    # Buck2 runs actions with cwd = the project root, locally (`env -C <root>`) and remotely
    # (the input root), and the declared inputs sit below it. A `.buckroot` marker does not
    # exist in a remote input root, so cwd is the only definition that works in both.
    return Path.cwd()


HERE = _project_root()

CONFIG_DECL = re.compile(r"^\s*(?:menu)?config\s+(BR2_[A-Za-z0-9_]+)")
CONFIG_LINE = re.compile(r"^(?:# )?(BR2_[A-Za-z0-9_]+)(?:=| is not set)")
BR2_TOKEN = re.compile(r"\bBR2_[A-Z0-9_]+")
# Symbols declared under <tree>/package/<something> belong to that package (or group)
# directory; everything else (arch, toolchain, system, fs, boot, linux, top level) is global.
SCOPED_DIR = re.compile(r"^(?:buildroot-src|buildroot-external)/package/.+")
# Trees whose files Buildroot's make never reads while building one package.
NOT_INFRA = ("output", "dl", ".git", "docs", "configs", "board", "utils", ".github",
             ".gitlab", "support/testing", "support/config-fragments")
INFRA_FILES = re.compile(r"(^|/)(Makefile|Makefile\.in|[^/]+\.mk|[^/]+\.sh|[^/]+\.py)$")
FIXED_MTIME = 1_000_000_000          # 2001-09-09: valid for make (0 is not), same for both files


def _walk_tree(root, skip):
    """(rel_dir, files) for a tree, pruning `skip` prefixes (relative to `root`)."""
    for dp, dns, fns in os.walk(root):
        rel = os.path.relpath(dp, root)
        rel = "" if rel == "." else rel
        dns[:] = sorted(d for d in dns if not any(
            (f"{rel}/{d}" if rel else d) == s or (f"{rel}/{d}" if rel else d).startswith(s + "/")
            for s in skip))
        yield rel, sorted(fns)


def cmd_owners(spec, dest):
    """Which directory declares each Kconfig symbol, plus the symbols that Buildroot's own
    (non-package) make files read directly. The whole answer is one deterministic file, so
    a rerun that changes nothing leaves every downstream slice untouched."""
    owners, infra_refs = {}, set()
    for tree in ("buildroot-src", "buildroot-external"):
        root = HERE / tree
        for rel, files in _walk_tree(root, ("output", "dl", ".git")):
            d = f"{tree}/{rel}" if rel else tree
            for f in files:
                if f.startswith("Config.in"):
                    for line in (root / rel / f).read_text(errors="replace").splitlines():
                        m = CONFIG_DECL.match(line)
                        if m:
                            owners.setdefault(m.group(1), set()).add(d)
    root = HERE / "buildroot-src"
    for rel, files in _walk_tree(root, NOT_INFRA):
        if re.match(r"package/[^/]+(/|$)", rel):
            continue                                  # a package directory, not infrastructure
        for f in files:
            path = f"{rel}/{f}" if rel else f
            if INFRA_FILES.search(path) and not (root / path).is_symlink():
                infra_refs |= {t for t in BR2_TOKEN.findall((root / path).read_text(errors="replace"))
                               if not t.endswith("_")}      # dynamic names: own package's, covered by scope
    infra_refs |= set(BR2_TOKEN.findall((HERE / "buildroot-external" / "external.mk").read_text()))
    Path(dest).write_text(json.dumps(
        {"infra_refs": sorted(infra_refs),
         "owners": {k: sorted(v) for k, v in sorted(owners.items())}}, indent=0, sort_keys=True) + "\n")


def scope_dirs(dirs):
    """Directories whose package symbols a package may legitimately read: its own, its
    closure's, and the group directories above them (package/x11r7, package/gstreamer1...)."""
    out = set(dirs)
    for d in list(dirs):
        if "." in d.rsplit("/", 1)[-1]:                    # a file entry (package/gcc/gcc.mk): its directory counts
            out.add(d.rsplit("/", 1)[0])
    for d in dirs:
        parts = d.split("/")
        for i in range(3, len(parts)):                # <tree>/package/<group>/...
            if parts[1] == "package":
                out.add("/".join(parts[:i]))
    return out


def own_refs(pkg_dir):
    """BR2_ tokens in the package's own make files: symbols it reads, whatever their owner."""
    toks = set()
    for path in sorted((HERE / pkg_dir).glob("*.mk")):
        toks |= set(BR2_TOKEN.findall(path.read_text(errors="replace")))
    return toks


def make_keep(owners_doc, dirs, own_dir):
    scope = scope_dirs(set(dirs) | {own_dir})
    refs = own_refs(own_dir)
    exact = {t for t in refs if not t.endswith("_")} | set(owners_doc["infra_refs"])
    prefixes = {t for t in refs if t.endswith("_")}
    if prefixes & {"BR2_", "BR2_PACKAGE_"}:
        return None                                   # dynamic access to any package symbol: keep all
    owners = owners_doc["owners"]

    def keep(sym):
        # Virtual-package selectors are read by the package infrastructure under names it builds
        # dynamically (BR2_PACKAGE_PROVIDES_$(virtual)): a provider package such as libopenssl needs
        # the symbol of the virtual package it provides, whose directory is not in its closure.
        if sym.startswith(("BR2_PACKAGE_PROVIDES_", "BR2_PACKAGE_HAS_")):
            return True
        dirs_of = owners.get(sym)
        if dirs_of is None or any(not SCOPED_DIR.match(d) or d in scope for d in dirs_of):
            return True
        return sym in exact or any(sym.startswith(p) for p in prefixes)
    return keep


def slice_config(text, keep):
    """(.config, auto.conf) restricted to the symbols `keep` accepts; assignments only."""
    lines = []
    for line in text.splitlines():
        m = CONFIG_LINE.match(line)
        if m and not line.startswith("#") and (keep is None or keep(m.group(1))):
            lines.append(line)
    body = "\n".join(lines) + "\n"
    return body, body


def write_slice_tar(dest, conf, auto):
    """Deterministic tar: the same slice always has the same digest, which is what lets
    Buck2 stop invalidating downstream actions when a config change does not affect them."""
    def add(tf, name, data=None):
        ti = tarfile.TarInfo(name)
        ti.mtime, ti.uid, ti.gid, ti.uname, ti.gname = FIXED_MTIME, 0, 0, "", ""
        if data is None:
            ti.type, ti.mode = tarfile.DIRTYPE, 0o755
            tf.addfile(ti)
        else:
            raw = data.encode()
            ti.size, ti.mode = len(raw), 0o644
            tf.addfile(ti, io.BytesIO(raw))
    with tarfile.open(dest, "w", format=tarfile.GNU_FORMAT) as tf:
        add(tf, ".config", conf)
        add(tf, "build")
        add(tf, "build/buildroot-config")
        add(tf, "build/buildroot-config/auto.conf", auto)


def cmd_slice(spec, dest):
    doc = json.loads(Path(spec["owners"]).read_text())
    keep = make_keep(doc, spec["dirs"], spec["dir"])
    conf, auto = slice_config(Path(spec["dot_config"]).read_text(), keep)
    write_slice_tar(dest, conf, auto)



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["owners", "slice"])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text())
    {"owners": cmd_owners, "slice": cmd_slice}[args.mode](spec, os.path.abspath(args.out))


if __name__ == "__main__":
    main()
