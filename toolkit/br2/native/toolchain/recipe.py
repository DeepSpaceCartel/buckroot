"""The `toolchain` package's install (package/pkg-cmake.mk, TOOLCHAIN_CMAKE_INSTALL_FILES):
the CMake toolchain file, generated from support/misc/toolchainfile.cmake.in by substituting
values Buildroot derives from the configuration, plus the CMake platform file.

Only what this configuration needs is implemented; anything else raises instead of quietly
producing a wrong file.
"""
from pathlib import Path


def _flag(cfg, names):
    hit = [n for n in names if cfg.get(n) == "y"]
    return hit[0] if hit else None


def apply(cfg, entries, inputs):
    if cfg["BR2_ARCH"] != '"aarch64"' or cfg["BR2_TOOLCHAIN_USES_MUSL"] != "y":
        raise SystemExit("toolchainfile.cmake: only aarch64/musl is implemented")
    for sym in ("BR2_FORTIFY_SOURCE_1", "BR2_FORTIFY_SOURCE_2", "BR2_FORTIFY_SOURCE_3"):
        if cfg[sym] == "y":
            raise SystemExit(f"{sym}: TARGET_HARDENED flags are not implemented")
    q = lambda v: v.strip().strip('"')                     # $(call qstrip,...)
    opt = {"BR2_OPTIMIZE_0": "-O0", "BR2_OPTIMIZE_1": "-O1", "BR2_OPTIMIZE_2": "-O2", "BR2_OPTIMIZE_3": "-O3",
           "BR2_OPTIMIZE_G": "-Og", "BR2_OPTIMIZE_S": "-Os", "BR2_OPTIMIZE_FAST": "-Ofast"}
    dbg = {"BR2_DEBUG_1": "-g1", "BR2_DEBUG_2": "-g2", "BR2_DEBUG_3": "-g3"}
    optimization = opt.get(_flag(cfg, opt), "")
    debugging = dbg.get(_flag(cfg, dbg), "-g0")
    cppflags = "-D_LARGEFILE_SOURCE -D_LARGEFILE64_SOURCE -D_FILE_OFFSET_BITS=64"
    join = lambda *p: " ".join(x for x in p if x)              # $(strip ...) collapses empties
    cflags = join(cppflags, optimization, debugging)
    subst = {
        "STAGING_SUBDIR": "aarch64-buildroot-linux-musl/sysroot",
        "TARGET_CFLAGS": cflags,
        "TARGET_CXXFLAGS": cflags,
        "TARGET_FCFLAGS": join(optimization, debugging),
        "TARGET_LDFLAGS": join(q(cfg["BR2_TARGET_LDFLAGS"]), "-ztext"),
        "TARGET_CC": "bin/aarch64-linux-gcc",
        "TARGET_CXX": "bin/aarch64-linux-g++",
        "TARGET_FC": "bin/aarch64-linux-gfortran",
        "CMAKE_SYSTEM_PROCESSOR": q(cfg["BR2_ARCH"]),
        "TOOLCHAIN_HAS_CXX": "1" if cfg["BR2_INSTALL_LIBSTDCPP"] else "0",
        "TOOLCHAIN_HAS_FORTRAN": "1" if cfg["BR2_TOOLCHAIN_HAS_FORTRAN"] else "0",
        "CMAKE_BUILD_TYPE": "Debug" if cfg["BR2_ENABLE_RUNTIME_DEBUG"] else "Release",
    }
    text = Path(inputs["template"]).read_text()
    for k, v in subst.items():
        text = text.replace(f"@@{k}@@", v)
    entries.append({"tree": "host", "dest": "share/buildroot/toolchainfile.cmake", "kind": "file",
                    "mode": "0644", "data": text})
    entries.append({"tree": "host", "dest": "share/buildroot/Platform/Buildroot.cmake", "kind": "file",
                    "mode": "0644", "src": inputs["platform"]})
