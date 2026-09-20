"""toolchain-external-bootlin's install, natively (toolchain/toolchain-external/
pkg-toolchain-external.mk and toolchain/helpers.mk). Buildroot fixes all paths at /mnt/out
(scripts/br2-ns.sh), so the two files that embed absolute paths are reproduced with them.

  host/opt/ext-toolchain     the unpacked toolchain tarball (TOOLCHAIN_EXTERNAL_MOVE)
  host/bin/toolchain-wrapper compiled from toolchain-wrapper.c (a separate Buck2 action)
  host/bin/<prefix>-*        symlinks: the compiler drivers go through the wrapper, ar/ranlib/nm
                             and everything else point into opt/ext-toolchain
  sysroot ("staging")        copy_toolchain_sysroot: etc, lib, sbin, usr, usr/lib of the
                             toolchain's sysroot (rsync -au --chmod=u=rwX,go=rX, no locale/);
                             absolute symlinks made relative; gdbinit; libstdc++ pretty-printer
                             loader path fixed
  target/{lib,usr/lib}       copy_toolchain_lib_root: the runtime libraries, following symlinks

Only the musl, static-libs-off, no-host-gdb, single-arch case is implemented; other settings
raise rather than produce a wrong artifact.
"""
import fnmatch
import os
import re
import tarfile
from pathlib import Path

BASE = "/mnt/out"
PKG = "toolchain-external-bootlin"
TUPLE = "aarch64-buildroot-linux-musl"


def apply(cfg, entries, inputs):
    for sym, want in (("BR2_TOOLCHAIN_EXTERNAL_MUSL", "y"),):
        if cfg[sym] != want:
            raise SystemExit(f"{sym}={cfg[sym]!r}: only the musl toolchain is implemented")
    for sym in ("BR2_STATIC_LIBS", "BR2_PACKAGE_HOST_GDB", "BR2_TOOLCHAIN_EXTERNAL_GDB_SERVER_COPY",
                "BR2_TOOLCHAIN_HAS_FORTRAN", "BR2_TOOLCHAIN_HAS_DLANG", "BR2_TOOLCHAIN_EXTERNAL_GLIBC",
                "BR2_TOOLCHAIN_EXTERNAL_UCLIBC"):
        if cfg[sym] == "y":
            raise SystemExit(f"{sym}: not implemented")
    if cfg["BR2_TOOLCHAIN_EXTRA_LIBS"].strip('"'):
        raise SystemExit("BR2_TOOLCHAIN_EXTRA_LIBS: not implemented")

    tc = Path(inputs["tc"])
    staging_abs = f"{BASE}/per-package/{PKG}/host/{TUPLE}/sysroot"
    install_abs = f"{BASE}/per-package/{PKG}/host/opt/ext-toolchain"
    prefix = cfg["BR2_TOOLCHAIN_EXTERNAL_PREFIX"].strip('"').replace("$(ARCH)", cfg["BR2_ARCH"].strip('"'))

    def add(tree, dest, kind, **kw):
        if dest.startswith("opt/ext-toolchain"):
            kw["nolist"] = True             # unpacked at extract time, not listed by the install step
        entries.append(dict(tree=tree, dest=dest, kind=kind, **kw))

    def exe_mode(path):
        return "0755" if os.stat(path).st_mode & 0o111 else "0644"

    # -- host/opt/ext-toolchain: the tarball's content as unpacked
    for dp, dns, fns in os.walk(tc):
        rel = os.path.relpath(dp, tc)
        base = "opt/ext-toolchain" + ("" if rel == "." else "/" + rel)
        add("host", base, "dir")
        for n in sorted(dns):
            if os.path.islink(os.path.join(dp, n)):                  # a symlink to a directory
                add("host", f"{base}/{n}", "link", target=os.readlink(os.path.join(dp, n)))
        for n in sorted(fns):
            full = os.path.join(dp, n)
            if os.path.islink(full):
                add("host", f"{base}/{n}", "link", target=os.readlink(full))
            else:
                add("host", f"{base}/{n}", "file", src=full, mode=exe_mode(full))

    # -- host/bin
    add("host", "bin/toolchain-wrapper", "file", src=inputs["wrapper"], mode="0755")
    for name in sorted(os.listdir(tc / "bin")):
        if not name.startswith(prefix + "-"):
            continue
        if name.endswith(("-ar", "-ranlib", "-nm")):
            target = f"../opt/ext-toolchain/bin/{name}"
        elif (name.endswith(("cc", "++", "cpp", "-gfortran", "-gdc")) or "cc-" in name or "++-" in name):
            target = "toolchain-wrapper"
        else:                                                        # incl. gdb: host-gdb is off
            target = f"../opt/ext-toolchain/bin/{name}"
        add("host", f"bin/{name}", "link", target=target)

    # -- sysroot ("staging")
    sysroot = tc / TUPLE / "sysroot"
    for sub in ("etc", "lib", "sbin", "usr", "usr/lib"):
        src_root = sysroot / sub
        if not src_root.is_dir():
            continue
        for dp, dns, fns in os.walk(src_root):
            rel = os.path.relpath(dp, sysroot)
            dns[:] = sorted(d for d in dns if d != "locale")
            if sub == "usr" and rel == "usr":
                dns[:] = [d for d in dns if not (d.startswith("lib") and not d.startswith("libexec"))]
            add("staging", rel, "dir")
            for n in sorted(dns) + sorted(fns):
                full = os.path.join(dp, n)
                dest = f"{rel}/{n}"
                if os.path.islink(full):
                    target = os.readlink(full)
                    if target.startswith("/"):                       # Buildroot's relpath_prefix rule
                        stripped = target[1:]
                        target = "../" * stripped.count("/") + stripped
                    add("staging", dest, "link", target=target)
                elif os.path.isfile(full):
                    add("staging", dest, "file", src=full, mode=exe_mode(full))
    # rsync -u never replaces a destination file that is newer. The skeleton (installed just
    # before, into the same sysroot) therefore wins over the toolchain's own etc/passwd, hosts...
    # Reproduced by dependency, not by mtime: paths the skeleton provides are not ours.
    with tarfile.open(inputs["skeleton"]) as tf:
        prefix_ = f"per-package/skeleton-init-common/host/{TUPLE}/sysroot/"
        provided = {m.name[len(prefix_):].rstrip("/") for m in tf.getmembers() if m.name.startswith(prefix_)}
    entries[:] = [e for e in entries if not (e["tree"] == "staging" and e["kind"] != "dir"
                                             and e["dest"] in provided)]

    # -- libtool files (fix_libtool_files, package/pkg-generic.mk): make their absolute paths point
    #    at this package's own sysroot. Same sed program, same order.
    def fix_la(text):
        text = text.replace(BASE, "@BASE_DIR@")
        text = text.replace(staging_abs, "@STAGING_DIR@")
        text = text.replace(install_abs, "@TOOLCHAIN_EXTERNAL_INSTALL_DIR@")
        text = re.sub(r"(['= ])/usr", r"\1@STAGING_DIR@/usr", text)
        text = re.sub(r"(['= ])/lib", r"\1@STAGING_DIR@/lib", text)
        text = text.replace("@TOOLCHAIN_EXTERNAL_INSTALL_DIR@", install_abs)
        text = text.replace("@STAGING_DIR@", staging_abs)
        return text.replace("@BASE_DIR@", BASE)

    for e in entries:
        if (e["tree"] == "staging" and e["kind"] == "file" and e["dest"].startswith("usr/lib")
                and e["dest"].endswith(".la")):
            e["data"] = fix_la(Path(e["src"]).read_text())

    add("staging", "usr/share/buildroot", "dir")
    add("staging", "usr/share/buildroot/gdbinit", "file", mode="0644",
        data=f"add-auto-load-safe-path {staging_abs}\nset sysroot {staging_abs}\n")

    # -- libstdc++ pretty-printer loader: hardcoded paths -> ours
    pyfiles = sorted(str(p) for p in tc.rglob("libstdcxx/__init__.py"))
    pythondir = f"{install_abs}/" + os.path.relpath(os.path.dirname(os.path.dirname(pyfiles[0])), tc)
    for e in entries:
        if e["tree"] == "staging" and e["kind"] == "file" and fnmatch.fnmatch(os.path.basename(e["dest"]), "libstdc++.so*-gdb.py"):
            out = []
            for line in Path(e["src"]).read_text().splitlines(True):
                stripped = line.lstrip()
                if line.startswith("libdir") and "=" in line.split()[1:2] + [line]:
                    line = f'libdir = "{staging_abs}/lib"\n'
                elif line.startswith("pythondir") and "=" in line:
                    line = f"pythondir = '{pythondir}'\n"
                out.append(line)
            e["data"] = "".join(out)

    # -- target libraries (copy_toolchain_lib_root)
    patterns = ["ld*.so.*", "libgcc_s.so.*", "libatomic.so.*"]
    if cfg["BR2_SSP_NONE"] != "y":
        patterns.append("libssp.so.*")
    patterns.append("libc.so")
    if cfg["BR2_INSTALL_LIBSTDCPP"] == "y":
        patterns.append("libstdc++.so.*")
    if cfg["BR2_TOOLCHAIN_HAS_OPENMP"] == "y":
        patterns.append("libgomp.so.*")
    staged = {e["dest"]: e for e in entries if e["tree"] == "staging" and e["kind"] in ("file", "link")}
    for pat in patterns:
        for dest in sorted(staged):
            if not fnmatch.fnmatch(os.path.basename(dest), pat):
                continue
            cur = dest
            while True:
                e = staged[cur]
                d = os.path.dirname(cur)
                name = os.path.basename(cur)
                if e["kind"] == "link":
                    add("target", f"{d}/{name}", "link", target=e["target"])
                    nxt = os.path.normpath(os.path.join(d, e["target"]))
                    cur = nxt
                else:
                    ent = dict(tree="target", dest=f"{d}/{name}", kind="file", mode="0755")
                    if "data" in e:
                        ent["data"] = e["data"]
                    else:
                        ent["src"] = e["src"]
                    entries.append(ent)
                    break
