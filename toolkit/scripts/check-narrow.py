#!/usr/bin/env python3
"""Soundness check for narrowed action inputs (see br2/pkg_action.py).

For each package, ask Buildroot the same question twice:

  full    : whole source tree + whole .config
  narrow  : the view (infrastructure + the package's closure) + the .config slice

`make show-vars` dumps every make variable, raw and expanded (so with every
config-derived flag and dependency resolved). Every variable that still exists in the
narrowed run must have the identical value in the full run, and every variable of the
package itself (`<PKG>_*`) must survive. (`make -n` would be simpler but runs `+` recipe
lines, i.e. the real build steps.) The probe also checks that the view really hides a
package outside the closure, so an undeclared read fails instead of going stale.

  scripts/check-narrow.py [--pkg NAME ...] [--jobs N] [--golden DIR]

--golden is a finished PER_PACKAGE_DIRECTORIES output dir (default
~/.cache/br2/<name>/golden, see scripts/build-rootfs-golden.sh): it supplies the
config and the dependencies' stamp files, so make sees them as already built.
"""
import argparse
import concurrent.futures
import difflib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True       # no __pycache__ in the Buck2-watched tree
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "scripts"))
os.chdir(HERE)                       # pkg_action finds the project root from the cwd
import br2buck                       # noqa: E402
import br2project                    # noqa: E402
ROOT_PROJECT = br2buck.HERE
HERE = ROOT_PROJECT

spec_ = importlib.util.spec_from_file_location("pkg_action", HERE / "br2" / "pkg_action.py")
pkg_action = importlib.util.module_from_spec(spec_)
spec_.loader.exec_module(pkg_action)
_sl = importlib.util.spec_from_file_location("slicing", HERE / "br2" / "slicing.py")
slicing = importlib.util.module_from_spec(_sl)
_sl.loader.exec_module(slicing)

NS = HERE / "scripts" / "br2-ns.sh"
MAKE = ["make", "-C", "/mnt/src", "O=/mnt/out", "BR2_DL_DIR=/mnt/dl"] + (
    ["BR2_EXTERNAL=/mnt/external"] if br2buck.PROJECT["external"] else [])
# Variables that legitimately differ. Each is derived from OTHER packages (reverse
# dependencies, lists over every enabled package, tool paths a package only gets through
# a dependency, ...) and cannot change how this package builds: per-package directories
# already limit what a build can reach to its declared dependencies.
IGNORED = re.compile(
    r"(RDEPENDENCIES|^ROOTFS_|^PKG_(PYTHON|CARGO|GO)|PKG_(PYTHON|CARGO|GO)_|^REBAR_|^OCI_|"
    r"^MAKEFILE_LIST$|^DL_TOOLS_DEPENDENCIES$|^TARGET_FINALIZE_HOOKS$|^AUTORECONF_HOOK$|"
    r"^QT_HEADERS_SYNC_HOOK$|^KEEP_PYTHON|^(AUTOCONF|AUTOHEADER|AUTORECONF|AUTOMAKE|ACLOCAL|LIBTOOLIZE)$|^__|-package$|^BR2_LOCALVERSION$|__X$)")
PKG_CONFIG_RE = re.compile(r'PKG_CONFIG="[^"]*"')
AGGREGATES = {"MAKEFLAGS", "MAKEOVERRIDES", "PACKAGES", "PACKAGES_ALL", "TARGETS", "TARGETS_ROOTFS",
              "TARGETS_SOURCE", "TARGETS_EXTRACT", "TARGETS_PATCH", "TARGETS_CONFIGURE", "TARGETS_BUILD",
              "TARGETS_INSTALL", "TARGETS_LEGAL_INFO", "PACKAGES_PERMISSIONS_TABLE",
              "PACKAGES_USERS_TABLE", "PACKAGES_DEVICES_TABLE", "PACKAGES_LINUX_CONFIG_FIXUPS",
              "BR2_EXTERNAL_MKS"}
ENV = {"PATH": os.environ["PATH"], "LC_ALL": "C", "TERM": "dumb"}


DEFINE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*[:?+]*=", re.M)
DEFINE_BLOCK = re.compile(r"^define\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)
REF = re.compile(r"\$[({]([A-Za-z_][A-Za-z0-9_]*)[)}]|\$\(call\s+([A-Za-z_][A-Za-z0-9_]*)")


def own_refs(pkg_dir):
    """Variable names a package's own .mk files mention."""
    refs = set()
    for mk in (HERE / pkg_dir).glob("*.mk"):
        for m in REF.finditer(mk.read_text(errors="replace")):
            refs.add(m.group(1) or m.group(2))
    return refs


_DEFINERS = {}


def definers(var):
    """Package directories whose .mk files define `var` (scanned once, lazily)."""
    if not _DEFINERS:
        for tree in ("buildroot-src", "buildroot-external"):
            for mk in (HERE / tree).glob("package/**/*.mk"):
                text = mk.read_text(errors="replace")
                d = str(mk.parent.relative_to(HERE / tree))
                for m in list(DEFINE.finditer(text)) + list(DEFINE_BLOCK.finditer(text)):
                    _DEFINERS.setdefault(m.group(1), set()).add((tree, d))
    return _DEFINERS.get(var, set())


def var_prefix(name):
    """Make variable prefix of a Buildroot package: host-foo-bar -> HOST_FOO_BAR, foo-bar -> FOO_BAR."""
    return name.upper().replace("-", "_")


def closure(model, name):
    """Transitive dependencies of `name` (model deps are the direct ones)."""
    seen, todo = set(), [name]
    while todo:
        for d in model[todo.pop()]["deps"]:
            if d not in seen:
                seen.add(d)
                todo.append(d)
    return seen


def seed(out, golden, model, names, config_text, auto_text):
    """Config + the stamp files of `names` (their build dirs, stamps only)."""
    (out / "build" / "buildroot-config").mkdir(parents=True, exist_ok=True)
    (out / ".config").write_text(config_text)
    (out / "build" / "buildroot-config" / "auto.conf").write_text(auto_text)
    os.utime(out / ".config", (slicing.FIXED_MTIME, slicing.FIXED_MTIME))
    os.utime(out / "build" / "buildroot-config" / "auto.conf",
             (slicing.FIXED_MTIME, slicing.FIXED_MTIME))
    for n in names:
        sd = model[n]["stamp_dir"]
        (out / sd).mkdir(parents=True, exist_ok=True)
        for f in (golden / sd).glob(".stamp_*"):
            shutil.copy2(f, out / sd / f.name)


def run_make(out, dl, goals, views=None, probe=None):
    env = dict(ENV)
    for k, v in (views or {}).items():
        env[f"BR2_NS_{k}_VIEW"] = str(v)
    cmd = [str(NS), str(out), str(dl), "--", *(probe or (*MAKE, *goals))]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return r.returncode, r.stdout, r.stderr


def check(name, model, golden, owners_doc, infra, full_config, full_auto):
    p = model[name]
    deps = closure(model, name)
    dirs = [model[d]["dir"] for d in sorted(deps)] + [p["dir"]]
    keep = slicing.make_keep(owners_doc, dirs, p["dir"])
    conf, auto = slicing.slice_config(full_config, keep)
    view_spec = {"dirs": dirs, "links": br2buck.outward_links(p["dir"], {m["dir"] for m in model.values()}), "infra_src": infra["buildroot-src"], "infra_ext": infra["buildroot-external"],
                 "common_dirs": [s["local"] for s in p["sources"] if "local" in s]}

    with tempfile.TemporaryDirectory(prefix=f"narrow-{name}-") as tmp:
        tmp = Path(tmp)
        results = {}
        for label in ("full", "narrow"):
            out, dl = tmp / label / "out", tmp / label / "dl"
            out.mkdir(parents=True), dl.mkdir()
            c, a = (full_config, full_auto) if label == "full" else (conf, auto)
            seed(out, golden, model, deps, c, a)
            views = pkg_action.write_views(tmp / label, view_spec) if label == "narrow" else None
            results[label] = run_make(out, dl, ["-s", "show-vars"], views)
        (rc_f, out_f, err_f), (rc_n, out_n, err_n) = results["full"], results["narrow"]

        # isolation probe: something outside the closure must not exist in the view
        other = next((m for m in sorted(model) if m not in deps and m != name
                      and model[m]["dir"].startswith("buildroot-src/package/")
                      and model[m]["dir"] not in dirs), None)
        probe = None
        if other:
            out, dl = tmp / "probe" / "out", tmp / "probe" / "dl"
            out.mkdir(parents=True), dl.mkdir()
            odir = model[other]["dir"][len("buildroot-src/"):]
            prc, _, _ = run_make(out, dl, [], pkg_action.write_views(tmp / "probe", view_spec),
                                 probe=["test", "!", "-e", f"/mnt/src/{odir}"])
            probe = (other, prc == 0)

    problems = []
    if rc_f != 0:
        problems.append(f"full make -n failed ({rc_f}): {err_f.strip()[-300:]}")
    if rc_n != 0:
        problems.append(f"narrow make -n failed ({rc_n}): {err_n.strip()[-600:]}")
    nvars = 0
    if rc_f == 0 and rc_n == 0:
        vf, vn = json.loads(out_f), json.loads(out_n)
        nvars = len(vn)
        # <PKG>_RAWNAME exists for every package Buildroot knows: that gives the variable prefixes.
        known = {v[:-len("_RAWNAME")] for v in vf if v.endswith("_RAWNAME")}
        relevant = {var_prefix(n) for n in deps | {name}}
        cut = {}

        def owner(v):
            """Longest known package prefix of a variable name (SKELETON_CUSTOM_X is
            skeleton-custom's, not skeleton's); None for global variables."""
            if v not in cut:
                parts, cut[v] = v.split("_"), None
                for i in range(len(parts) - 1, 0, -1):
                    if "_".join(parts[:i]) in known:
                        cut[v] = "_".join(parts[:i])
                        break
            return cut[v]
        def norm(x):
            # pkgconf's binary path comes from pkgconf.mk: set iff pkgconf is in the closure
            return re.sub(PKG_CONFIG_RE, 'PKG_CONFIG=""', x["expanded"] + "\0" + x["raw"])
        changed = sorted(v for v in vn if v in vf and norm(vf[v]) != norm(vn[v]) and v not in AGGREGATES
                         and not IGNORED.search(v) and (owner(v) is None or owner(v) in relevant))
        for v in changed[:8]:
            a, b = vf[v]["expanded"], vn[v]["expanded"]
            i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
            problems.append(f"{v} differs at char {i}:\n      full  : {a[max(0, i - 60):i + 100]!r}\n      narrow: {b[max(0, i - 60):i + 100]!r}")
        if len(changed) > 8:
            problems.append(f"... and {len(changed) - 8} more")
    if probe and not probe[1]:
        problems.append(f"view still exposes package {probe[0]}")
    suggest = {}
    if rc_f == 0 and rc_n == 0:
        for v in sorted(own_refs(p["dir"])):
            if v in vf and v not in vn:                       # defined by a package outside this view
                for tree, d in definers(v):
                    if f"{tree}/{d}" not in dirs:
                        suggest.setdefault(v, set()).add(d)
    total = sum(1 for l in full_config.splitlines() if slicing.CONFIG_LINE.match(l) and not l.startswith("#"))
    kept = sum(1 for _ in conf.splitlines()) if keep else total
    return name, problems, {"suggest": {k: sorted(v) for k, v in suggest.items()}, "lines": nvars, "kept": kept, "total": total,
                            "all_config": keep is None, "probe": probe[0] if probe else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pkg", nargs="*", default=None)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--apply", action="store_true", help="write the suggested extra_view into project.json")
    ap.add_argument("--golden", default=str(br2project.cache_dir(br2buck.PROJECT) / "golden"))
    args = ap.parse_args()

    golden = Path(args.golden)
    if not (golden / ".config").exists():
        sys.exit(f"{golden}/.config missing: run scripts/build-rootfs-golden.sh first")
    model = json.loads(br2buck.MODEL.read_text())["packages"]
    names = args.pkg or sorted(model)
    carved = {p["dir"] for p in model.values()}
    infra = {root: br2buck.infra_parts(root, carved)[1] for root in ("buildroot-src", "buildroot-external")}

    with tempfile.TemporaryDirectory(prefix="narrow-owners-") as tmp:
        owners_json = Path(tmp) / "owners.json"
        slicing.cmd_owners({}, str(owners_json))
        owners_doc = json.loads(owners_json.read_text())
    print(f"owners: {len(owners_doc['owners'])} symbols, {len(owners_doc['infra_refs'])} read by infra make files")
    full_config = (golden / ".config").read_text()
    full_auto = (golden / "build" / "buildroot-config" / "auto.conf").read_text()

    bad = 0
    extra = {}
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as ex:
        futs = [ex.submit(check, n, model, golden, owners_doc, infra, full_config, full_auto) for n in names]
        for f in concurrent.futures.as_completed(futs):
            name, problems, st = f.result()
            tag = "ok  " if not problems else "FAIL"
            note = "full config (dynamic BR2_ access)" if st["all_config"] else f"{st['kept']}/{st['total']} config symbols"
            print(f"{tag} {name:32s} {st['lines']:5d} variables, {note}"
                  + (f", hides {st['probe']}" if st["probe"] else ""))
            for pr in problems:
                print("     " + pr)
            for var, dirs_ in st["suggest"].items():
                print(f"     hidden reference: {var} is defined in {', '.join(dirs_)}, outside the closure")
                extra.setdefault(model[name]["dir"].split("/", 1)[1], set()).update(dirs_)
            bad += bool(problems)
    if extra:
        print("\nsuggested project.json \"extra_view\":")
        print(json.dumps({k: sorted(v) for k, v in sorted(extra.items())}, indent=2))
        if args.apply:
            pj = ROOT_PROJECT / "project.json"
            cfg = json.loads(pj.read_text())
            for k, v in extra.items():
                cfg.setdefault("extra_view", {})[k] = sorted(set(cfg.get("extra_view", {}).get(k, [])) | v)
            pj.write_text(json.dumps(cfg, indent=2) + "\n")
            print("applied to project.json")
    print("all narrowed views and config slices give the same make variables as the full tree" if not bad else f"{bad} package(s) differ")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
