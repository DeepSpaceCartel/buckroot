#!/usr/bin/env python3
"""Cheap sanity check before compiling: does every package's narrowed view contain what its
extract/patch steps need?

  scripts/preflight.py [--pkg NAME ...] [--jobs N]

For each package: seed a scratch output dir (config slice + dependency stamps, like
check-narrow.py), run `make <pkg>-patch` in the package's view, and compare the list of
patches Buildroot applied (`build/<pkg>/.applied_patches_list`) with the golden build's.
A patch that is silently not applied (it lived in a directory the view did not include)
shows up here in seconds instead of as a wrong or failing multi-hour compile.
Also reports steps that fail outright (missing .mk, source, hash file).
"""
import argparse
import concurrent.futures
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cn", HERE / "check-narrow.py")
cn = importlib.util.module_from_spec(spec)
_argv, sys.argv = sys.argv, [sys.argv[0]]          # check-narrow parses argv at import time
spec.loader.exec_module(cn)
sys.argv = _argv
br2buck, slicing, pkg_action = cn.br2buck, cn.slicing, cn.pkg_action


def applied(build_dir):
    f = build_dir / ".applied_patches_list"
    return sorted(Path(l).name for l in f.read_text().split()) if f.exists() else []


def one(name, model, golden, owners_doc, infra, full_config, full_auto, dl_src):
    p = model[name]
    if p.get("virtual"):
        return name, [], -1                                     # virtual packages have no extract/patch step
    deps = cn.closure(model, name)
    dirs = [model[d]["dir"] for d in sorted(deps)] + [p["dir"]]
    carved = {m["dir"] for m in model.values()}
    links = br2buck.outward_links(p["dir"], carved)
    keep = slicing.make_keep(owners_doc, dirs + links, p["dir"])
    conf, auto = slicing.slice_config(full_config, keep)
    spec_ = {"dirs": dirs, "links": links, "infra_src": infra["buildroot-src"], "infra_ext": infra["buildroot-external"],
             "common_dirs": [s["local"] for s in p["sources"] if "local" in s]}
    with tempfile.TemporaryDirectory(prefix=f"preflight-{name}-") as tmp:
        tmp = Path(tmp)
        out, dl = tmp / "out", tmp / "dl"
        out.mkdir(), (dl / (p["dl_dir"] or "")).mkdir(parents=True)
        cn.seed(out, golden, model, deps, conf, auto)
        for s in p["sources"]:                                  # the same files a Buck action gets
            src = dl_src / (p["dl_dir"] or "") / s["file"]
            if src.exists():
                os.symlink(src, dl / (p["dl_dir"] or "") / s["file"])
        views = pkg_action.write_views(tmp, spec_)
        rc, o, e = cn.run_make(out, dl, ["-s", f"{name}-patch"], views)
        mine = applied(out / p["stamp_dir"])
        ref = applied(golden / p["stamp_dir"])
    problems = []
    if rc != 0:
        problems.append("make -patch failed: " + (e.strip().splitlines() or ["?"])[-1][:200])
    elif mine != ref:
        problems.append(f"patches differ: golden applied {len(ref)}, view applied {len(mine)}; "
                        f"missing {sorted(set(ref) - set(mine))[:4]}")
    return name, problems, len(ref)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pkg", nargs="*")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--golden", default=str(cn.br2project.cache_dir(br2buck.PROJECT) / "golden"))
    args = ap.parse_args()
    golden = Path(args.golden)
    model = json.loads(br2buck.MODEL.read_text())["packages"]
    names = args.pkg or sorted(model)
    carved = {p["dir"] for p in model.values()}
    infra = {r: br2buck.infra_parts(r, carved)[1] for r in ("buildroot-src", "buildroot-external")}
    with tempfile.TemporaryDirectory() as t:
        owners = Path(t) / "owners.json"
        slicing.cmd_owners({}, str(owners))
        owners_doc = json.loads(owners.read_text())
    full_config = (golden / ".config").read_text()
    full_auto = (golden / "build" / "buildroot-config" / "auto.conf").read_text()
    dl_src = br2buck.HERE / "buildroot-src" / "dl"
    bad = 0
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as ex:
        futs = [ex.submit(one, n, model, golden, owners_doc, infra, full_config, full_auto, dl_src) for n in names]
        for f in concurrent.futures.as_completed(futs):
            name, problems, n = f.result()
            print(f"{'ok  ' if not problems else 'FAIL'} {name:34s} " + ("virtual, skipped" if n < 0 else f"{n} patch(es) in golden"))
            for pr in problems:
                print("     " + pr)
            bad += bool(problems)
    print("preflight: all packages extract and patch exactly as in the golden build" if not bad
          else f"preflight: {bad} package(s) differ")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
