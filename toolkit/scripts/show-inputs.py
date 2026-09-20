#!/usr/bin/env python3
"""Show what a package action can see: the entries of its /mnt/src, /mnt/external and
/mnt/common views (infrastructure + the package dirs of its dependency closure) and how
much of .config its slice keeps. Same code as the Buck2 rules use, so it is the truth.

  scripts/show-inputs.py hello            # summary + every view entry
  scripts/show-inputs.py hello --files    # expand directories into individual files
  scripts/show-inputs.py hello --config   # also print the sliced .config lines
"""
import argparse
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "scripts"))
os.chdir(HERE)
import br2buck  # noqa: E402
import br2project  # noqa: E402

_spec = importlib.util.spec_from_file_location("pkg_action", HERE / "br2" / "pkg_action.py")
pkg_action = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pkg_action)
_sl = importlib.util.spec_from_file_location("slicing", HERE / "br2" / "slicing.py")
slicing = importlib.util.module_from_spec(_sl)
_sl.loader.exec_module(slicing)


def closure(model, name):
    seen, todo = set(), [name]
    while todo:
        for d in model[todo.pop()]["deps"]:
            if d not in seen:
                seen.add(d)
                todo.append(d)
    return seen


def expand(root, entry):
    path = HERE / root / entry
    if path.is_dir() and not path.is_symlink():
        for dp, _, fns in os.walk(path):
            for f in sorted(fns):
                yield os.path.relpath(Path(dp) / f, HERE)
    else:
        yield f"{root}/{entry}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pkg")
    ap.add_argument("--files", action="store_true", help="expand directories into files")
    ap.add_argument("--config", action="store_true", help="print the sliced .config")
    ap.add_argument("--golden", default=str(br2project.cache_dir(br2buck.PROJECT) / "golden"))
    args = ap.parse_args()

    model = json.loads(br2buck.MODEL.read_text())["packages"]
    if args.pkg not in model:
        sys.exit(f"{args.pkg}: not in golden/model.json ({', '.join(sorted(model))})")
    p = model[args.pkg]
    deps = closure(model, args.pkg)
    carved = {m["dir"] for m in model.values()}
    dirs = [model[d]["dir"] for d in sorted(deps)] + [p["dir"]]
    spec = {"dirs": dirs, "links": br2buck.outward_links(p["dir"], carved),
            "infra_src": br2buck.infra_parts("buildroot-src", carved)[1],
            "infra_ext": br2buck.infra_parts("buildroot-external", carved)[1],
            "common_dirs": [s["local"] for s in p["sources"] if "local" in s]}
    views = pkg_action.view_entries(spec)

    print(f"{args.pkg}: closure = {', '.join(sorted(deps)) or '(none)'}")
    for name, root in (("SRC", "buildroot-src"), ("EXT", "buildroot-external"), ("COMMON", "common")):
        entries = views[name]
        print(f"\n== /mnt/{ {'SRC': 'src', 'EXT': 'external', 'COMMON': 'common'}[name] }  ({len(entries)} entries)")
        n = 0
        for e in entries:
            if args.files:
                for f in expand(root, e):
                    print("  " + f)
                    n += 1
            else:
                print("  " + e + ("/" if (HERE / root / e).is_dir() else ""))
        if args.files:
            print(f"  -> {n} files")
    if spec["links"]:
        print("\n(includes symlink targets in other package dirs: " + ", ".join(spec["links"]) + ")")

    cfg = Path(args.golden) / ".config"
    if cfg.exists():
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "owners.json"
            slicing.cmd_owners({}, str(out))
            keep = slicing.make_keep(json.loads(out.read_text()), dirs, p["dir"])
        text = cfg.read_text()
        conf, _ = slicing.slice_config(text, keep)
        print(f"\n== .config slice: {len(conf.splitlines())} of {len(text.splitlines())} lines")
        if args.config:
            print(conf)


if __name__ == "__main__":
    main()
