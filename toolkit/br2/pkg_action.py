#!/usr/bin/env python3
"""Buck2 action driver: run ONE Buildroot package (or the final image) from the
seeded outputs of its dependencies. Buildroot still does all the real work
(`make <pkg>`); this script only reconstructs the state make expects.

  pkg_action.py config  --spec S.json --out config.tar [--dot-config .config]
  pkg_action.py package --spec S.json --out pkg.tar
  pkg_action.py rootfs  --spec S.json --out rootfs.ext4

How a package build works (BR2_PER_PACKAGE_DIRECTORIES=y):
  * make decides "dependency done" from stamp files in build/<pkg>-<ver>/; deps are
    order-only prerequisites, so seeded stamps make it skip them.
  * at the configure step Buildroot merges each DIRECT dependency's complete
    per-package/<dep>/{host,target} into per-package/<pkg>/. A package's Buck artifact
    holds only what it ADDED (its delta) plus its stamps, because every complete tree
    carries the whole 362 MB toolchain. Complete trees are rebuilt here by overlaying
    the deltas of a dependency's closure, in topological order.
  * everything runs through scripts/br2-ns.sh: fixed absolute paths (Buildroot bakes
    build paths into the rootfs) and no network (all sources are declared inputs).

Narrow inputs (so adding a package rebuilds only that package and the rootfs):
  * a package action sees a VIEW of the source trees: the infrastructure plus the
    package directories of its dependency closure. Buck2 does not sandbox local
    actions, so the view is what makes the declared inputs true (an undeclared read
    is ENOENT, not a silently stale cache hit).
  * it also gets a SLICE of .config, not the whole file: the symbols of packages it
    cannot depend on are dropped (see slicing.py). The slice ships its own auto.conf, so
    Buildroot's `prepare` step does not run Kconfig `syncconfig` over the whole tree.
"""
import argparse
import json
import os
import io
import shutil
import signal
import tarfile
import time
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

def _project_root():
    # Buck2 runs actions with cwd = the project root, locally (`env -C <root>`) and remotely
    # (the input root), and the declared inputs sit below it. A `.buckroot` marker does not
    # exist in a remote input root, so cwd is the only definition that works in both.
    return Path.cwd()


HERE = _project_root()
NS = HERE / "scripts" / "br2-ns.sh"   # overridden by spec["ns"]: the declared artifact
def memory_bytes():
    """The memory this process may use: the smaller of the machine's and, in a container, the cgroup limit."""
    with open("/proc/meminfo") as fh:
        total = int(next(l for l in fh if l.startswith("MemTotal:")).split()[1]) * 1024
    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            limit = int(Path(path).read_text().strip())
        except (OSError, ValueError):                 # absent, or "max" (no limit)
            continue
        total = min(total, limit)
    return total


def parallel_jobs():
    """The -jN of the action's make. Buildroot's default is CPUs + 1, and a single make -j5 of GCC was OOM-killed twice on a
    7.7 GB machine, so cap it at about 2 GB of memory per job. BR2_JOBS overrides. Output does not depend on N."""
    if os.environ.get("BR2_JOBS"):
        return max(1, int(os.environ["BR2_JOBS"]))
    cpus = len(os.sched_getaffinity(0))
    return max(1, min(cpus + 1, memory_bytes() // (2 * 2**30)))


# --no-print-directory: without it every sub-make gets `w` in MAKEFLAGS, and GNU make 4.3 then prints "make: Entering directory" to
# STDOUT even under -s. Buildroot's kernel-module infrastructure captures `$(MAKE) ... kernelrelease` in backticks as KVER=..., so
# rtl8821cu (Home Assistant OS) received "make[1]: Entering directory ..." words and failed with "multiple target patterns".
MAKE = ["make", "--no-print-directory", "-C", "/mnt/src", "O=/mnt/out",
        "BR2_EXTERNAL=/mnt/external", "BR2_DL_DIR=/mnt/dl", f"PARALLEL_JOBS={parallel_jobs()}"]
ENV = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
       "LC_ALL": "C", "TERM": "dumb", "BR2_NS_NET": "off"}


# Work directories live OUTSIDE the project: Buck2's own scratch area is inside buck-out and
# it trips over build trees (autoconf leaves files literally named `conftest.t\\t`; "Error
# relativizing" then aborts the next build). SIGTERM (Buck2 cancelling an action) unwinds
# through `with` so the directory is removed instead of leaking gigabytes.
WORK_BASE = Path(os.environ.get("BR2_WORK_DIR", "/var/tmp/buckroot-work"))


def work_dir(prefix):
    WORK_BASE.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    if os.environ.get("BR2_KEEP_WORK"):               # debugging: leave the work dir (and make.log) behind
        class Keep:
            name = tempfile.mkdtemp(prefix=prefix, dir=WORK_BASE)
            def __enter__(self): return self.name
            def __exit__(self, *a): print(f"[pkg_action] kept {self.name}", file=sys.stderr)
        return Keep()
    return tempfile.TemporaryDirectory(prefix=prefix, dir=WORK_BASE)


def log(msg):
    print(f"[pkg_action] {msg}", file=sys.stderr, flush=True)


def sh(cmd, **kw):
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def untar(tar, dest):
    sh(["tar", "-xf", tar, "-C", dest])


def make_in_ns(out, dl, goals, logfile, views=None, common_root=None, command=None):
    """`make <goals>` (or `command`) inside the namespace; `views` = {"SRC"|"EXT"|"COMMON": view file}."""
    env = dict(ENV, HOME=str(out), BR2_NS_HERE=str(HERE))
    if common_root:
        env["BR2_NS_COMMON_ROOT"] = str(common_root)
    for name, path in (views or {}).items():
        env[f"BR2_NS_{name}_VIEW"] = str(path)
    with open(logfile, "w") as lf:
        r = subprocess.run([str(NS), str(out), str(dl), "--", *(command or [*MAKE, *goals])],
                           stdout=lf, stderr=subprocess.STDOUT, env=env)
    if r.returncode != 0:
        tail = Path(logfile).read_text().splitlines()[-40:]
        sys.exit(f"make {' '.join(goals)} failed (exit {r.returncode}); last output:\n" + "\n".join(tail))


def overlay_complete(out, below, subdirs):
    """Replace each per-package/X/<sub> (currently X's delta) by the COMPLETE tree:
    the deltas of X's closure (`below[X]`, topological) then X's own delta.
    Hardlinks keep the toolchain overlay cheap; sources are replaced only after every
    complete tree has been computed."""
    per, stage = out / "per-package", out / ".complete"
    for x, deps in below.items():
        for sub in subdirs:
            dst = stage / x / sub
            dst.mkdir(parents=True, exist_ok=True)
            for y in [*deps, x]:
                src = per / y / sub
                if src.is_dir():
                    sh(["rsync", "-a", f"--link-dest={src}", f"{src}/", f"{dst}/"])
    for x in below:
        for sub in subdirs:
            tgt = per / x / sub
            shutil.rmtree(tgt, ignore_errors=True)
            tgt.parent.mkdir(parents=True, exist_ok=True)
            os.rename(stage / x / sub, tgt)
    shutil.rmtree(stage, ignore_errors=True)        # absent when there is nothing to overlay


def index_seeded(out, direct):
    """What the direct dependencies already provide: relpath -> inodes / symlink targets.
    Buildroot merges them into per-package/<pkg>/ with hardlinks, so an inherited regular
    file shares an inode with the seeded one (mtimes are useless here: files unpacked
    from an upstream tarball, like the toolchain's, keep their original old mtimes)."""
    files, links = {}, {}
    per = out / "per-package"
    for dep in direct:
        for sub in ("host", "target"):
            base = per / dep / sub
            for root, dirs, fnames in os.walk(base):
                for name in dirs + fnames:
                    path = os.path.join(root, name)
                    key = (sub, os.path.relpath(path, base))
                    st = os.lstat(path)
                    if stat.S_ISLNK(st.st_mode):
                        links.setdefault(key, set()).add(os.readlink(path))
                    elif stat.S_ISREG(st.st_mode):
                        files.setdefault(key, set()).add(st.st_ino)
    return files, links


def own_entries(out, pkg, files, links):
    """Paths (relative to `out`) that `pkg` added or changed: every directory (cheap, keeps
    modes), plus each file / symlink that is not inherited from a seeded dependency."""
    names = []
    for sub in ("host", "target"):
        base = out / "per-package" / pkg / sub
        if not base.is_dir():
            continue
        names.append(os.path.relpath(base, out))
        for root, dirs, fnames in os.walk(base):
            for name in dirs + fnames:
                path = os.path.join(root, name)
                key = (sub, os.path.relpath(path, base))
                st = os.lstat(path)
                if stat.S_ISLNK(st.st_mode):
                    if os.readlink(path) not in links.get(key, ()):
                        names.append(os.path.relpath(path, out))
                elif stat.S_ISDIR(st.st_mode):
                    names.append(os.path.relpath(path, out))
                elif st.st_ino not in files.get(key, ()):
                    names.append(os.path.relpath(path, out))
    return names


def pack_delta(out, pkg, stamp_dir, files, links, dest):
    """Tar what `pkg` added plus its stamp files, plus the few build-dir files that
    LATER steps read: e.g. busybox's finalize hook greps build/busybox-*/.config for
    CONFIG_ASH=y to decide whether /bin/ash goes into /etc/shells. The build dir itself
    is not carried between actions, so a hook like that silently does nothing without it."""
    names = own_entries(out, pkg, files, links)
    stamps = subprocess.run(
        ["find", stamp_dir, "-maxdepth", "1", "(", "-name", ".stamp_*", "-o", "-name",
         ".files-list*", "-o", "-name", ".config", ")", "-print0"],
        cwd=out, check=True, capture_output=True).stdout
    listing = b"\0".join(n.encode() for n in names) + b"\0" + stamps
    subprocess.run(["tar", "--null", "--no-recursion", "--numeric-owner", "-T", "-",
                    "-cf", str(dest)], cwd=out, input=listing, check=True)
    add_kernel_release_stub(out, stamp_dir, dest)


def add_kernel_release_stub(out, stamp_dir, dest):
    """The rootfs step asks the kernel build dir for its release string (`make -C <dir>
    kernelrelease`, LINUX_VERSION_PROBED) to run depmod and to name lib/modules/<release>.
    That directory (a whole kernel tree) is not carried between actions, and without it the probe
    silently answers with the HOST's `uname -r`. Carry a stub Makefile that answers the probe."""
    rel_file = out / stamp_dir / "include" / "config" / "kernel.release"
    if not rel_file.is_file():
        return
    release = rel_file.read_text().strip()
    stub = f"kernelrelease:\n\t@echo {release}\n".encode()
    with tarfile.open(dest, "a") as tf:
        for name, data in ((f"{stamp_dir}/Makefile", stub), (f"{stamp_dir}/include/config/kernel.release", release.encode() + b"\n")):
            ti = tarfile.TarInfo(name)
            ti.size, ti.mode, ti.mtime = len(data), 0o644, int(time.time())
            tf.addfile(ti, io.BytesIO(data))


def seed_config_and_stamps(out, spec, config_key="config"):
    untar(spec[config_key], out)
    for dep in spec.get("closure", []):
        untar(dep["tar"], out)


# ------------------------------------------------------------ narrow inputs ----

def view_entries(spec):
    """Allow-lists for the three trees: infrastructure + the package dirs of the closure.
    Entries below another entry are dropped (a bind mount inside a read-only bind fails)."""
    src, ext = list(spec["infra_src"]), list(spec["infra_ext"])
    common = [d[len("common/"):] for d in spec.get("common_dirs", [])]
    for d in [*spec["dirs"], *spec.get("links", [])]:
        for prefix, lst in (("buildroot-src/", src), ("buildroot-external/", ext)):
            if d.startswith(prefix):
                lst.append(d[len(prefix):])

    def prune(entries):
        out = []
        for e in sorted(set(entries)):
            if not any(e.startswith(o + "/") for o in out):
                out.append(e)
        return out
    return {"SRC": prune(src), "EXT": prune(ext), "COMMON": prune(common)}


def assemble_common(work, spec):
    """common/<name> from the DECLARED source artifacts (filegroup outputs under buck-out)."""
    root = Path(work) / "common-root"
    for name, arts in spec.get("common_src", {}).items():
        dst = root / name
        dst.mkdir(parents=True, exist_ok=True)
        for a in arts:
            a = Path(a)
            sh(["cp", "-aL", f"{a}/." if a.is_dir() else a, dst])
    return root


TREE_ROOTS = {"SRC": "buildroot-src", "EXT": "buildroot-external"}


def overlay_entry(work, root, entry, links):
    """A copy of `root/entry` plus the dangling symlinks below it. Buck2 cannot declare
    a dangling symlink as an input, so the renderer records them as data (path -> target)."""
    dst = Path(work) / "overlay" / root / entry
    dst.parent.mkdir(parents=True, exist_ok=True)
    real = HERE / root / entry
    if real.is_dir():
        sh(["cp", "-a", real, dst])
    for path, target in links.items():
        link = dst / os.path.relpath(path, f"{root}/{entry}")
        link.parent.mkdir(parents=True, exist_ok=True)
        if not os.path.lexists(link):
            os.symlink(target, link)
    return dst


def write_views(work, spec):
    """One view file per tree. A line is `entry`, or `entry<TAB>real path` when the entry
    needs an overlay (dangling symlinks to recreate)."""
    views = {}
    symlinks = spec.get("symlinks", {})
    for name, entries in view_entries(spec).items():
        lines = []
        for e in entries:
            root = TREE_ROOTS.get(name)
            links = {k: v for k, v in symlinks.items() if root and k.startswith(f"{root}/{e}/")}
            if links:
                lines.append(f"{e}\t{overlay_entry(work, root, e, links)}")
            else:
                lines.append(e)
        path = Path(work) / f"view-{name.lower()}.txt"
        path.write_text("".join(l + "\n" for l in lines))
        views[name] = path
    return views


def cmd_config(spec, dest, dot_config=None):
    with work_dir("br2-config-") as work:
        out, dl = Path(work) / "out", Path(work) / "dl"
        out.mkdir(), dl.mkdir()
        make_in_ns(out, dl, [spec["defconfig"]], Path(work) / "make.log")
        if spec.get("fragment"):
            # what the instrumentation needs (per-package dirs, reproducibility) on top of the defconfig
            with open(out / ".config", "a") as fh:
                fh.write("".join(l + "\n" for l in spec["fragment"]))
            make_in_ns(out, dl, ["olddefconfig"], Path(work) / "make2.log")
        sh(["tar", "--numeric-owner", "-cf", dest, "-C", out, "."])
        if dot_config:
            shutil.copyfile(out / ".config", dot_config)


def cmd_package(spec, dest):
    pkg = spec["pkg"]
    with work_dir(f"br2-{pkg}-") as work:
        out, dl = Path(work) / "out", Path(work) / "dl"
        out.mkdir(), (dl / spec["dl_dir"]).mkdir(parents=True)
        for src in spec.get("sources", []):
            os.symlink(os.path.abspath(src["path"]), dl / spec["dl_dir"] / src["file"])
        seed_config_and_stamps(out, spec, "slice")
        overlay_complete(out, spec["direct"], ["host", "target"])
        seeded_files, seeded_links = index_seeded(out, spec["direct"])
        log(f"make {pkg}")
        make_in_ns(out, dl, [pkg], Path(work) / "make.log", views=write_views(work, spec),
                   common_root=assemble_common(work, spec))
        if not (out / spec["stamp_dir"] / ".stamp_installed").exists():
            sys.exit(f"{pkg}: no .stamp_installed after make")
        pack_delta(out, pkg, spec["stamp_dir"], seeded_files, seeded_links, dest)


def cmd_viewcheck(spec, dest):
    """Enter the namespace with this package's views and let make PARSE every makefile it can see (`<pkg>-show-version`
    builds nothing). Run where only the declared inputs exist (a remote input root), it fails in seconds on
      * a view entry that is not a declared input (br2-ns.sh: `view entry missing`), and
      * a makefile that includes or reads a file the view does not provide (`No such file or directory`),
    instead of hours into a build. Needs the config slice, not the dependencies' outputs."""
    with work_dir("br2-view-") as work:
        out, dl = Path(work) / "out", Path(work) / "dl"
        out.mkdir(), dl.mkdir()
        untar(spec["slice"], out)
        views = write_views(work, spec)
        make_in_ns(out, dl, [f"{spec['pkg']}-show-version"], Path(work) / "view.log", views=views,
                   common_root=assemble_common(work, spec))
        entries = {name: path.read_text().count("\n") for name, path in views.items()}
        Path(dest).write_text(json.dumps({"pkg": spec["pkg"], "view_entries": entries}) + "\n")


def cmd_rootfs(spec, dest):
    with work_dir("br2-rootfs-") as work:
        out, dl = Path(work) / "out", Path(work) / "dl"
        out.mkdir(), dl.mkdir()
        seed_config_and_stamps(out, spec)
        # Complete TARGET trees are needed exactly (finalize merges them in a fixed
        # order); host trees stay as deltas (their union is the same host tools).
        overlay_complete(out, spec["below"], ["target"])
        # host-finalize merges only the packages Buildroot lists in PACKAGES, relying on each one's
        # COMPLETE host tree to carry its dependencies (host-binutils: the cross strip). Ours are deltas,
        # so merge all of them first (make's own, ordered merge then runs on top).
        for d in sorted((out / "per-package").glob("*/host")):
            sh(["rsync", "-a", "--hard-links", f"{d}/", f"{out}/host/"])
        log("make (finalize + image)")
        make_in_ns(out, dl, [], Path(work) / "make.log")
        shutil.copyfile(out / "images" / spec.get("image", "rootfs.ext4"), dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["config", "package", "rootfs", "viewcheck"])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dot-config", default=None, help="config mode: also copy the plain .config here")
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text())
    global NS
    NS = HERE / spec.get("ns", NS)
    if not spec.get("external", True):               # a project without a BR2_EXTERNAL tree
        MAKE[:] = [a for a in MAKE if not a.startswith("BR2_EXTERNAL=")]
    out = os.path.abspath(args.out)
    if args.mode == "config":
        cmd_config(spec, out, os.path.abspath(args.dot_config) if args.dot_config else None)
    else:
        {"package": cmd_package, "rootfs": cmd_rootfs, "viewcheck": cmd_viewcheck}[args.mode](spec, out)


if __name__ == "__main__":
    main()
