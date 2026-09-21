#!/usr/bin/env python3
"""Turn Buildroot's own build graph into Buck2 targets, in two stages.

  br2buck.py extract [--out-dir DIR]   query Buildroot (defconfig + `show-info`, no build
                                       needed) -> golden/model.json (committed)
  br2buck.py render                    golden/model.json -> BUCK files (no Buildroot needed)
  br2buck.py render --check            fail if the rendered files differ from the model

Only the package GRAPH is extracted (versions, direct deps, sources, sha256, patches,
stamp dirs). Build commands and hooks stay inside Buildroot; Buck2 owns ordering,
parallelism, downloads and caching (see br2/rules.bzl). Stdlib only.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import br2project                                       # noqa: E402

PROJECT = br2project.load(Path(__file__).resolve().parent)
HERE = PROJECT["root"]                                  # the experiment directory
MODEL = HERE / "golden" / "model.json"
DEFCONFIG = PROJECT["defconfig"]
NS = HERE / "scripts" / "br2-ns.sh"

# Inside the br2-ns.sh mount namespace.
IN_NS_MAKE = ["make", "-s", "-C", "/mnt/src", "O=/mnt/out", "BR2_DL_DIR=/mnt/dl"] + (
    ["BR2_EXTERNAL=/mnt/external"] if PROJECT["external"] else [])


# ---------------------------------------------------------------- extract ----

def buildroot_json(out_dir, *goal):
    cmd = [str(NS), out_dir, str(HERE / "buildroot-src" / "dl"), "--", *IN_NS_MAKE, *goal]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"{' '.join(goal)} failed:\n{r.stderr}")
    return json.loads(r.stdout)


def buildroot_vars(out_dir, patterns):
    """Expanded make variables matching `patterns` (a `%` is a wildcard): {name: {"expanded": value}}.
    `show-vars` exists since Buildroot 2023; older trees have `printvars` (NAME=value lines)."""
    cmd = [str(NS), out_dir, str(HERE / "buildroot-src" / "dl"), "--", *IN_NS_MAKE, "show-vars", f"VARS={patterns}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0:
        return json.loads(r.stdout)
    cmd = [str(NS), out_dir, str(HERE / "buildroot-src" / "dl"), "--", *IN_NS_MAKE, "QUIET=1", "printvars", f"VARS={patterns}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"printvars VARS={patterns} failed:\n{r.stderr}")
    found = {}
    for line in r.stdout.splitlines():
        name, sep, value = line.partition("=")
        if sep:
            found[name] = {"expanded": value}
    return found


def parse_hash_file(path):
    """`<algo>  <hex>  <file>` lines -> {file: {algo: hex}} (sha256 and sha512 are kept)."""
    hashes = {}
    for line in Path(path).read_text().splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] in ("sha256", "sha512"):
            hashes.setdefault(parts[2], {})[parts[0]] = parts[1]
    return hashes


def normalize_pkg_dir(pkg_dir):
    """Package dir as reported inside the namespace -> path relative to the Buck root."""
    p = pkg_dir.rstrip("/")
    if p.startswith("/mnt/external/"):
        return "buildroot-external/" + p[len("/mnt/external/"):]
    if p.startswith("/"):
        sys.exit(f"unexpected absolute package_dir {pkg_dir!r}")
    return "buildroot-src/" + p


def urls_for(source, uris, dl_dir):
    """Ordered download URLs for one source file, or (None, local_path)."""
    urls, local = [], None
    for uri in uris:
        method, _, base = uri.partition("+")
        base = base.rstrip("/")
        if uri.startswith("local+"):
            local = os.path.normpath(uri[len("local+"):])
            continue
        if method in ("http", "https"):
            urls.append(f"{base}/{source}")
        elif method in ("http|urlencode", "https|urlencode"):
            urls.append(f"{base}/{source}")           # mirror; sha256 still enforced
        elif uri.startswith(("http://", "https://")):
            urls.append(f"{uri.rstrip('/')}/{source}")  # bare URL base
        else:
            urls.append(None)                             # git, svn, scp...: not expressible as http_file
    return urls, local


def buildroot_defconfig(out_dir):
    cmd = [str(NS), out_dir, str(HERE / "buildroot-src" / "dl"), "--", *IN_NS_MAKE, DEFCONFIG]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"{DEFCONFIG} failed:\n{r.stderr}")
    with open(Path(out_dir) / ".config", "a") as fh:            # same fragment the br2_config action applies
        fh.write("".join(l + "\n" for l in br2project.fragment(PROJECT)))
    r = subprocess.run([str(NS), out_dir, str(HERE / "buildroot-src" / "dl"), "--", *IN_NS_MAKE, "olddefconfig"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"olddefconfig failed:\n{r.stderr}")


def var_prefix(name, entry):
    """make variable prefix of a package: HOST_ for host packages (gcc-final is one although its
    name has no host- prefix), then the upper-cased name with - as _."""
    up = name.upper().replace("-", "_")
    return up if up.startswith("HOST_") or entry.get("type") != "host" else "HOST_" + up


def extract(out_dir):
    """`show-info` needs only the configuration and the parsed makefiles, not built
    packages, so by default a throwaway output dir with just the defconfig applied."""
    if out_dir is None:
        with tempfile.TemporaryDirectory(prefix="br2-extract-") as tmp:
            buildroot_defconfig(tmp)
            return extract(tmp)
    info = buildroot_json(out_dir, "show-info")
    # Older Buildroot (2024.05) has no "hashes" in show-info; <PKG>_HASH_FILES is in every version.
    hash_vars = {}
    if any("hashes" not in e or "package_dir" not in e for e in info.values()):
        hv = buildroot_vars(out_dir, "%_HASH_FILES %_PKGDIR")
        hash_vars = {k: v["expanded"].split() for k, v in hv.items()}
    # The toolchain tuple names the sysroot (host/<tuple>/sysroot): aarch64-buildroot-linux-gnu for an
    # internal glibc toolchain, ...-musl for a musl or Bootlin one. Native rules must not hard-code it.
    tuple_var = buildroot_vars(out_dir, "GNU_TARGET_NAME")["GNU_TARGET_NAME"]["expanded"].strip()
    model = {"defconfig": DEFCONFIG,
             "buildroot": (HERE / "BUILDROOT_PINNED_VERSION.txt").read_text().strip(),
             "target_tuple": tuple_var,
             "packages": {}}
    for name, e in sorted(info.items()):
        if e.get("type") not in ("target", "host"):
            continue                                   # rootfs-common / rootfs-ext2
        hashes = {}
        hash_files = e.get("hashes")
        if hash_files is None:
            hash_files = hash_vars.get(var_prefix(name, e) + "_HASH_FILES", [])
        for hf in hash_files:
            hf = "buildroot-external/" + hf[len("/mnt/external/"):] if hf.startswith("/mnt/external/") else "buildroot-src/" + hf
            if (HERE / hf).is_file():
                hashes.update(parse_hash_file(HERE / hf))
        sources = []
        for dl in e.get("downloads", []):
            urls, local = urls_for(dl["source"], dl["uris"], e["dl_dir"])
            if local:
                # A local site inside the trees (hassio: $(BR2_EXTERNAL_HAOS_PATH)/package/hassio) is read from the
                # package's own directory, which its view contains; nothing to declare.
                if local.startswith(("/mnt/external/", "/mnt/src/")):
                    continue
                # HELLO_SITE = $(BR2_EXTERNAL_..._PATH)/../common/hello  ->  /mnt/common/hello
                if not local.startswith("/mnt/common/"):
                    sys.exit(f"{name}: unexpected local source {local!r} (only common/<dir> is mounted)")
                sources.append({"file": dl["source"], "local": "common/" + local[len("/mnt/common/"):]})
                continue
            h = hashes.get(dl["source"], {})
            if PROJECT["sources"] == "http" and urls and urls[0] is not None and h.get("sha256"):
                sources.append({"file": dl["source"], "urls": [u for u in urls if u], "sha256": h["sha256"]})
            else:
                # Buck2's http_file needs an http(s) URL and a sha256. Everything else (git/svn
                # downloads, sha512-only hashes, no hash at all) is fetched by Buildroot's own
                # downloader in `br2 fetch` and vendored under sources/ (see fetch()).
                sources.append({"file": dl["source"], "vendored": True, "hash": h or None})
        model["packages"][name] = {
            "kind": e["type"], "virtual": bool(e.get("virtual")),
            "version": e.get("version"), "dl_dir": e.get("dl_dir"),
            "stamp_dir": (e.get("stamp_dir") or e["build_dir"]).rstrip("/"),     # older show-info calls it build_dir
            "dir": normalize_pkg_dir(e["package_dir"] if "package_dir" in e else
                                     hash_vars[var_prefix(name, e) + "_PKGDIR"][0]),
            "deps": sorted(e["dependencies"]), "sources": sources,
        }
    names = set(model["packages"])
    for n, p in model["packages"].items():
        missing = [d for d in p["deps"] if d not in names]
        if missing:
            sys.exit(f"{n}: dependencies not in the model: {missing}")
    MODEL.parent.mkdir(exist_ok=True)
    MODEL.write_text(json.dumps(model, indent=1, sort_keys=True) + "\n")
    print(f"{len(model['packages'])} packages -> {MODEL.relative_to(HERE)}")


# ------------------------------------------------------------------ fetch ----

def fetch():
    """Download what Buck2 cannot: run Buildroot's own downloader (`make source`, network on,
    hashes checked by Buildroot), then vendor the files listed as `vendored` in the model under
    sources/ and pin their sha256 in golden/sources.lock.json (a later fetch must reproduce it:
    Buildroot's git tarballs are reproducible)."""
    import hashlib
    model = json.loads(MODEL.read_text())
    dl = HERE / "buildroot-src" / "dl"
    with tempfile.TemporaryDirectory(prefix="br2-fetch-") as tmp:
        buildroot_defconfig(tmp)
        r = subprocess.run([str(NS), tmp, str(dl), "--", "make", "-C", "/mnt/src", "O=/mnt/out",
                            "BR2_DL_DIR=/mnt/dl", *(["BR2_EXTERNAL=/mnt/external"] if PROJECT["external"] else []),
                            "source"])
        if r.returncode != 0:
            sys.exit("make source failed")
    lock_path = HERE / "golden" / "sources.lock.json"
    lock = json.loads(lock_path.read_text()) if lock_path.exists() else {}
    for d, f, h in vendored_sources(model):
        src = dl / d / f
        if not src.is_file():
            sys.exit(f"{d}/{f}: not downloaded")
        data = src.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        for algo in ("sha256", "sha512"):
            if h and algo in h and hashlib.new(algo, data).hexdigest() != h[algo]:
                sys.exit(f"{d}/{f}: {algo} does not match the Buildroot hash file")
        key = f"{d}/{f}"
        if lock.get(key, digest) != digest:
            sys.exit(f"{key}: content differs from golden/sources.lock.json (upstream changed or download is not reproducible)")
        lock[key] = digest
        dst = HERE / "sources" / d / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst.unlink()
        try:
            os.link(src, dst)
        except OSError:
            import shutil
            shutil.copy2(src, dst)
    lock_path.write_text(json.dumps(lock, indent=1, sort_keys=True) + "\n")
    print(f"{len(vendored_sources(model))} vendored sources in sources/")


# ----------------------------------------------------------------- render ----

HEADER = ("# @generated by scripts/br2buck.py from golden/model.json. Do not edit;\n"
          "# regenerate with `scripts/br2buck.py render`.\n")


class Expr(str):
    """A raw Starlark expression (not quoted when rendered)."""


def label(pkg_dir, name):
    return f"//{pkg_dir}:{name}"


def native_label(name):
    """Label of the native target of `name`: project-specific (native/<name>) wins over the
    toolkit's generic ones (br2/native/<name>); None if there is none."""
    for base in ("native", "br2/native"):
        if (HERE / base / name / "BUCK").exists():
            return f"//{base}/{name}:{name}"
    return None


def dep_label(pkg_dir, name):
    """Label of package `name`: its wrapped target, or a switch to a native target when one
    exists (`[br2] native = a,b` in .buckconfig selects which ones are used)."""
    wrapped = label(pkg_dir, name)
    nat = native_label(name)
    if nat:
        return Expr(f'("{nat}" if "{name}" in read_config("br2", "native", "").split(",") '
                    f'else "{wrapped}")')
    return wrapped


def bzl_list(items, indent="    "):
    if not items:
        return "[]"
    return "[\n" + "".join(f'{indent}    {i if isinstance(i, Expr) else chr(34) + i + chr(34)},\n' for i in items) + f"{indent}]"


# Never inputs: VCS data, build output, downloads, and the .config files an in-tree
# `make` (scripts/build-tier0.sh without O=) leaves in the source directory.
ROOT_SKIP = {"buildroot-src": {".git", "output", "dl", ".config", ".config.old", "..config.tmp",
                               ".defconfig"},
             "buildroot-external": {".git"}}
# Infrastructure = what a package action reads besides package directories. In the source
# tree that is everything but package/<dir>; in the external tree everything but the
# packages, the defconfigs and Config.in (Kconfig never runs in a package action).
INFRA_SKIP = {"buildroot-src": set(), "buildroot-external": {"Config.in", "configs", "output", "dl", ".git"}}


def dangling_links(path):
    """Symlinks below `path` whose target does not resolve on their own."""
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            full = os.path.join(root, name)
            if os.path.islink(full) and not os.path.exists(full):
                yield full


def file_list(path):
    """Files below `path` (relative), skipping dangling symlinks. Buck2 cannot track a
    symlink whose target is missing, e.g. skeleton/tmp -> ../var/tmp, which only resolves
    once Buildroot merges skeleton-init-common and skeleton-init-sysv."""
    out = []
    for root, _, files in os.walk(path):
        for name in files:
            full = os.path.join(root, name)
            if not (os.path.islink(full) and not os.path.exists(full)):
                out.append(os.path.relpath(full, path))
    return sorted(out)


def input_entries(rel_dir, carved, prefix="", dangling=True):
    """Top-level entries of `rel_dir` as Buck2 sources (relative to rel_dir), listing a
    directory whole unless a carved-out package lives inside it (Buck2 forbids a directory
    source that covers a subpackage), in which case we descend. Directory sources also
    sidestep dangling symlinks inside Buildroot's skeleton, which glob() chokes on.
    dangling=False keeps directories whole (the form a mount view wants)."""
    out = []
    skip = {"BUCK"} | (ROOT_SKIP.get(rel_dir, set()) if not prefix else set())
    for name in sorted(os.listdir(HERE / rel_dir)):
        if name in skip:
            continue
        rel = f"{rel_dir}/{name}"
        path = HERE / rel
        if path.is_dir() and not path.is_symlink():
            if rel in carved:
                continue                                 # its own BUCK provides :inputs
            if any(c.startswith(rel + "/") for c in carved):
                out += [f"{name}/{e}" for e in input_entries(rel, carved, prefix=name, dangling=dangling)]
                continue
            if dangling and next(dangling_links(path), None):
                out += [f"{name}/{e}" for e in file_list(path)]
                continue
        out.append(name)
    return out


def outward_links(pkg_dir, carved):
    """Files that symlinks inside `pkg_dir` reach in ANOTHER package's directory, e.g.
    busybox/S02sysctl -> ../procps-ng/S02sysctl. A view that shows only the closure would
    leave such a link dangling, so the target is a declared input and a view entry of the
    package. Targets in infrastructure (docs/...) are covered by the infra target anyway."""
    root = pkg_dir.split("/", 1)[0]
    found = set()
    for dp, dns, fns in os.walk(HERE / pkg_dir):
        for name in dns + fns:
            path = Path(dp) / name
            if not path.is_symlink():
                continue
            target = os.path.normpath(os.path.join(os.path.dirname(path), os.readlink(path)))
            rel = os.path.relpath(target, HERE)
            if rel == pkg_dir or rel.startswith(pkg_dir + "/"):
                continue
            parts = rel.split("/")
            if parts[0] != root or len(parts) < 3 or parts[1] != "package":
                continue                                   # infrastructure (or outside the trees)
            found.add(rel)
    # A package nested in a group directory (package/opengl/libegl) is only INCLUDED by the group's
    # own makefile (package/opengl/opengl.mk), and the group may hold shared files and patch dirs:
    # every ancestor directory between package/ and the package is part of its view.
    parts = pkg_dir.split("/")
    for i in range(3, len(parts)):                            # <root>/package/<group>[/...]
        if parts[1] == "package":
            extra_dirs = PROJECT["extra_view"].setdefault("/".join(parts[1:i]), [])
    ancestors = ["/".join(parts[1:i]) for i in range(3, len(parts)) if parts[1] == "package"]
    for other in ancestors:
        base = f"{root}/{other}"
        found.update(f"{base}/{n}" for n in sorted(os.listdir(HERE / base))
                     if n != "BUCK" and f"{base}/{n}" not in carved
                     and not any(c.startswith(f"{base}/{n}/") for c in carved))
    # A .mk may read variables another package's .mk defines without depending on it (the view
    # would hide that directory): project.json "extra_view" names them.
    for other in PROJECT["extra_view"].get(pkg_dir.split("/", 1)[1], []):
        base = f"{root}/{other}"
        if any(c.startswith(base + "/") for c in carved):
            # a group directory (package/gcc holds gcc.mk next to the gcc-initial/gcc-final packages):
            # a directory source may not cover a sub-package, so take its own top-level files
            # ... plus its non-carved subdirectories: package/gcc/13.3.0/ holds the patches Buildroot
            # applies to gcc-initial/gcc-final. Missing they are silently NOT applied.
            found.update(f"{base}/{n}" for n in sorted(os.listdir(HERE / base))
                         if n != "BUCK" and f"{base}/{n}" not in carved
                         and not any(c.startswith(f"{base}/{n}/") for c in carved))
        else:
            found.add(base)
    return sorted(found)


def dangling_map(rel_dir):
    """{repo-relative path: target} for the dangling symlinks below `rel_dir`. Buck2 cannot
    track them (a directory source with one is refused), so they are declared as DATA and
    recreated in the action's view; without this a remote worker's input root lacks them
    (e.g. skeleton-init-sysv/var/log -> ../tmp) and the rootfs silently loses /var/log."""
    return {os.path.relpath(l, HERE): os.readlink(l) for l in dangling_links(HERE / rel_dir)}


def bzl_dict(d, indent="    "):
    if not d:
        return "{}"
    return "{\n" + "".join(f'{indent}    "{k}": "{v}",\n' for k, v in sorted(d.items())) + f"{indent}}}"


def link_target_name(pkg_dir):
    return "links-" + pkg_dir.replace("/", "-")


def render_pkg_dir(pkg_dir, pkgs, carved):
    """One BUCK next to the package's .mk: its sources, its targets, its inputs."""
    root = pkg_dir.split("/", 1)[0]
    links = outward_links(pkg_dir, carved)
    lines = [HEADER, 'load("//br2:rules.bzl", "br2_inputs", "br2_package")\n',
             "# Everything in this directory (patches, hashes, configs). An input of this package's\n"
             "# actions and of every package that depends on it (see br2_package.pkg_inputs).\n"
             'br2_inputs(\n    name = "inputs",\n    srcs = '
             + bzl_list(input_entries(pkg_dir, carved)) + ',\n'
             + (f'    deps = ["//{root}:{link_target_name(pkg_dir)}"],\n' if links else "")
             + (f'    symlinks = {bzl_dict(dangling_map(pkg_dir))},\n' if dangling_map(pkg_dir) else "")
             + '    visibility = ["PUBLIC"],\n)\n']
    exports = [n for n in sorted(os.listdir(HERE / pkg_dir))
               if n != "BUCK" and (HERE / pkg_dir / n).is_file() and not (HERE / pkg_dir / n).is_symlink()]
    lines.append("# The package's own files, for hand-written native rules (br2/native/) to consume.\n"
                 + "".join(f'export_file(name = "file.{n}", src = "{n}", mode = "reference", visibility = ["PUBLIC"])\n' for n in exports))
    seen_sources = set()
    for name, p in sorted(pkgs.items()):
        for s in p["sources"]:
            if "urls" in s and s["file"] not in seen_sources:
                seen_sources.add(s["file"])
                lines.append(f'http_file(\n    name = "{s["file"]}",\n    out = "{s["file"]}",\n'
                             f'    urls = {bzl_list(s["urls"][:1])},  # prelude http_file takes one URL; sha256 is enforced\n'
                             f'    sha256 = "{s["sha256"]}",\n'
                             f'    visibility = ["PUBLIC"],\n)\n')
        remote = [s for s in p["sources"] if "urls" in s or s.get("vendored")]
        local = [s for s in p["sources"] if "local" in s]
        args = [f'    name = "{name}",', f'    pkg = "{name}",', '    pkg_inputs = ":inputs",',
                f'    stamp_dir = "{p["stamp_dir"]}",']
        if p["dl_dir"]:
            args.append(f'    dl_dir = "{p["dl_dir"]}",')
        if p["deps"]:
            args.append("    deps = " + bzl_list([dep_label(DIRS[d], d) for d in p["deps"]]) + ",")
        if remote:
            args.append("    source_files = " + bzl_list([s["file"] for s in remote]) + ",")
            args.append("    sources = " + bzl_list([f'//sources:{p["dl_dir"]}--{s["file"]}' if s.get("vendored") else f':{s["file"]}'
                                        for s in remote]) + ",")
        if local:
            args.append("    local_srcs = " + bzl_list([f"//{s['local']}:src" for s in local]) + ",")
        if links:
            args.append("    links = " + bzl_list(links) + ",")
        if PROJECT["salts"].get(name):
            args.append(f'    salt = "{PROJECT["salts"][name]}",')
        if name in PROJECT["heavy"]:
            args.append(f"    weight = {PROJECT['heavy_weight']},")
        args.append('    visibility = ["PUBLIC"],')
        lines.append("br2_package(\n" + "\n".join(args) + "\n)\n")
    return "\n".join(lines)


def render_tree(root, carved):
    """The whole tree of one root as a single input group: its own files plus the
    `inputs` of every sub-package we carved out with a BUCK file. Used by the actions that
    really read everything (config, owners, rootfs)."""
    extra = [f"//{d}:inputs" for d in sorted(d for d in carved if d.startswith(root + "/"))]
    return ('load("//br2:rules.bzl", "br2_infra", "br2_inputs")\n\nbr2_inputs(\n    name = "tree",\n'
            '    srcs = ' + bzl_list(input_entries(root, carved)) + ',\n'
            '    deps = ' + bzl_list(extra) + ",\n"
            '    visibility = ["PUBLIC"],\n)\n')


# Infrastructure files that native rules install verbatim (name -> path in the tree).
ROOT_EXPORTS = {"buildroot-src": {"target-dir-warning.txt": "support/misc/target-dir-warning.txt",
                   "toolchain-wrapper.c": "toolchain/toolchain-wrapper.c",
                   "toolchainfile.cmake.in": "support/misc/toolchainfile.cmake.in",
                   "Buildroot.cmake": "support/misc/Buildroot.cmake"}}


def render_exports(root):
    out = ""
    for name, src in sorted(ROOT_EXPORTS.get(root, {}).items()):
        out += f'\nexport_file(name = "{name}", src = "{src}", mode = "reference", visibility = ["PUBLIC"])\n'
    return out


def render_links(root, carved):
    """Input groups for the files that package directories reach through symlinks."""
    out = ""
    for d in sorted(d for d in carved if d.startswith(root + "/")):
        links = outward_links(d, carved)
        if not links:
            continue
        srcs, deps = [], []
        for l in links:
            # the most specific owner: a link target can lie in a carved package and in its carved parent, and the
            # iteration order of a set (hash-seed dependent) must not decide which one renders
            owner = max((c for c in carved if l == c or l.startswith(c + "/")), key=len, default=None)
            if owner is None:
                srcs.append(l[len(root) + 1:])                   # a plain file of the root package
            elif l == owner:
                deps.append(f"//{owner}:inputs")                 # a whole (carved) package dir
            elif "/" in l[len(owner) + 1:]:
                sys.exit(f"{d}: symlink target {l} is nested inside another carved package")
            else:
                deps.append(f"//{owner}:file.{l[len(owner) + 1:]}")   # the export_file of that package
        out += ('\nbr2_inputs(\n    name = "' + link_target_name(d) + '",\n    srcs = ' + bzl_list(srcs) + ',\n'
                + ('    deps = ' + bzl_list(deps) + ',\n' if deps else '')
                + '    visibility = ["PUBLIC"],\n)\n')
    return out


def infra_keep(root, entry):
    """Is a top-level-relative entry infrastructure (not a package directory)?"""
    parts = entry.split("/")
    if parts[0] in INFRA_SKIP[root]:
        return False
    if parts[0] == "package":
        # package/<dir> is a package (its own inputs); package/<file> (pkg-*.mk, Makefile.in) is not
        return len(parts) == 2 and not (HERE / root / entry).is_dir()
    return True


def infra_parts(root, carved):
    """(srcs, entries, outside) of the infrastructure of `root`. `srcs` is what Buck2
    tracks, `entries` the matching allow-list for the mount view (whole directories,
    dangling symlinks and all), `outside` the carved sub-packages that are not under
    package/ (toolchain-external-bootlin...): infrastructure with their own BUCK."""
    own = [d[len(root) + 1:] for d in sorted(carved) if d.startswith(root + "/")]
    outside = [d for d in own if not d.startswith("package/") and d.split("/")[0] not in INFRA_SKIP[root]]
    srcs = [e for e in input_entries(root, carved) if infra_keep(root, e)]
    entries = sorted({e for e in input_entries(root, carved, dangling=False) if infra_keep(root, e)}
                     | set(outside))
    return srcs, entries, outside


def infra_symlinks(root, entries):
    """Dangling symlinks inside the infrastructure entries (system/skeleton/etc/mtab...)."""
    out = {}
    for e in entries:
        if (HERE / root / e).is_dir():
            out.update(dangling_map(f"{root}/{e}"))
    return out


def render_infra(root, carved):
    """What a PACKAGE action may see of `root` besides its closure's package directories."""
    srcs, entries, outside = infra_parts(root, carved)
    links = infra_symlinks(root, entries)
    return ('\nbr2_infra(\n    name = "infra",\n    srcs = ' + bzl_list(srcs) + ',\n'
            '    entries = ' + bzl_list(entries) + ',\n'
            '    deps = ' + bzl_list([f"//{root}/{d}:inputs" for d in outside]) + ",\n"
            + (f'    symlinks = {bzl_dict(links)},\n' if links else "")
            + '    visibility = ["PUBLIC"],\n)\n')


def vendored_sources(model):
    """(dl_dir, file, hash) of every source that `br2 fetch` provides under sources/."""
    seen = {}
    for p in model["packages"].values():
        for s in p["sources"]:
            if s.get("vendored"):
                seen[(p["dl_dir"], s["file"])] = s.get("hash")
    return sorted((d, f, h) for (d, f), h in seen.items())


def render_sources(model):
    """Vendored downloads, exposed as Buck2 sources (the files are put there by `br2 fetch`)."""
    body = "".join(f'export_file(name = "{d}--{f}", src = "{d}/{f}", visibility = ["PUBLIC"])\n'
                   for d, f, _ in vendored_sources(model))
    return HEADER + "\n# Downloads Buck2's http_file cannot express (git, sha512-only hashes...): put here by `br2 fetch`.\n" + body


def render_generated(model):
    names = sorted(model["packages"])
    return (HEADER + '\nload("//br2:rules.bzl", "br2_config", "br2_owners", "br2_rootfs")\n\n'
            f'br2_config(\n    name = "config",\n    defconfig = "{model["defconfig"]}",\n'
            '    visibility = ["PUBLIC"],\n)\n\n'
            'br2_owners(\n    name = "owners",\n    visibility = ["PUBLIC"],\n)\n\n'
            'br2_rootfs(\n    name = "rootfs",\n    packages = '
            + bzl_list([dep_label(DIRS[n], n) for n in names]) + ",\n"
            '    visibility = ["PUBLIC"],\n)\n')


DIRS = {}   # package name -> package dir (filled by render())


def render(check):
    model = json.loads(MODEL.read_text())
    DIRS.clear()
    DIRS.update({n: p["dir"] for n, p in model["packages"].items()})
    by_dir = {}
    for n, p in model["packages"].items():
        by_dir.setdefault(p["dir"], {})[n] = p
    carved = set(by_dir)
    files = {d: render_pkg_dir(d, pkgs, carved) for d, pkgs in by_dir.items()}
    out = {f"{d}/BUCK": text for d, text in files.items()}
    for root in ("buildroot-src", "buildroot-external"):
        out[f"{root}/BUCK"] = HEADER + "\n" + render_tree(root, carved) + render_infra(root, carved) + render_links(root, carved) + render_exports(root)
    out["br2/generated/BUCK"] = render_generated(model)
    if not model.get("target_tuple"):
        sys.exit("golden/model.json has no target_tuple: run `scripts/br2 extract` again")
    out["br2/generated/target.bzl"] = (f"{HEADER}\n# The toolchain tuple: the sysroot is host/<tuple>/sysroot.\n"
                                       f'TARGET_TUPLE = "{model["target_tuple"]}"\n')
    out["sources/BUCK"] = render_sources(model)

    changed = []
    for rel, text in sorted(out.items()):
        path = HERE / rel
        if not path.exists() or path.read_text() != text:
            changed.append(rel)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
    if check:
        if changed:
            sys.exit("stale rendered files (run `scripts/br2buck.py render`):\n  " + "\n  ".join(changed))
        print(f"{len(out)} rendered files up to date")
        return
    # Keep the rendered files in the upstream clone out of its own `git status`.
    excl = HERE / "buildroot-src" / ".git" / "info" / "exclude"
    if excl.parent.is_dir() and "\nBUCK\n" not in "\n" + excl.read_text() + "\n":
        with open(excl, "a") as fh:
            fh.write("BUCK\n")
    print(f"{len(out)} files rendered ({len(changed)} changed)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("extract")
    ex.add_argument("--out-dir", default=None,
                    help="an existing Buildroot output dir to query (default: a temporary one)")
    sub.add_parser("fetch")
    rd = sub.add_parser("render")
    rd.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.cmd == "fetch":
        fetch()
    elif args.cmd == "extract":
        extract(args.out_dir)
    else:
        render(args.check)


if __name__ == "__main__":
    main()
