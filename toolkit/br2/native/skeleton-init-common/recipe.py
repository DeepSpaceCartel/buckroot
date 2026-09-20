"""skeleton-init-common's config-dependent install steps (package/skeleton-init-common/
skeleton-init-common.mk and system/system.mk), which Buildroot keeps in make macros.

  SYSTEM_USR_SYMLINKS_OR_DIRS  merged /usr: bin, sbin, lib are symlinks into usr/, else dirs
  SYSTEM_LIB_SYMLINK           lib64 (64-bit) or lib32 -> lib, in / and /usr
  sed 's,@PATH@,$(BR2_SYSTEM_DEFAULT_PATH),' etc/profile   (target only)
  install -d usr/include                                    (sysroot only)

`cfg` holds the raw values of the symbols declared in the BUCK file (quotes included, as make
sees them).
"""


def apply(cfg, entries, inputs=None):
    if cfg["BR2_MIPS_NABI32"] == "y":
        raise SystemExit("MIPS n32 lib symlinks are not implemented")
    merged = cfg["BR2_ROOTFS_MERGED_USR"] == "y"
    libdir = "lib64" if cfg["BR2_ARCH_IS_64"] == "y" else "lib32"
    for tree in ("target", "staging"):
        for d in ("bin", "sbin", "lib"):
            if merged:
                entries.append({"tree": tree, "dest": d, "kind": "link", "target": "usr/" + d})
            else:
                entries.append({"tree": tree, "dest": d, "kind": "dir"})
        entries.append({"tree": tree, "dest": libdir, "kind": "link", "target": "lib"})
        entries.append({"tree": tree, "dest": "usr/" + libdir, "kind": "link", "target": "lib"})
    entries.append({"tree": "staging", "dest": "usr/include", "kind": "dir"})

    for e in entries:                       # the sed on the target's /etc/profile
        if e["tree"] == "target" and e["dest"] == "etc/profile" and e["kind"] == "file":
            text = open(e["src"]).read() if "data" not in e else e["data"]
            e["data"] = text.replace("@PATH@", cfg["BR2_SYSTEM_DEFAULT_PATH"])
