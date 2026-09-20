"""The experiment's `project.json`: the only project-specific input of the toolkit.

  {
    "name": "helloworld",                     # experiment name (cache dir, buildbarn instance)
    "defconfig": "my_defconfig",              # name make understands (configs/ in the tree or in the external)
    "external": true,                         # is there a BR2_EXTERNAL tree in buildroot-external/ ?
    "buildroot": {"repo": "https://git.buildroot.net/buildroot", "ref": "2025.02.18"},
    "heavy": ["host-gcc-initial", "gcc-final", "linux"],       # run alone (OOM otherwise)
    "extra_view": {"package/gettext-tiny": ["package/gettext-gnu"]},  # implicit cross-package references
    "sources": "vendored",                    # how downloads reach Buck2: http (http_file) | vendored (br2 fetch)
    "native": ["hello", "host-skeleton"]      # packages built natively in the `native` variant
  }

Layout convention (fixed names, so the generated Buck2 files are the same everywhere):
  buildroot-src/        the Buildroot tree (a clone, or a project's own fork of Buildroot)
  buildroot-external/   BR2_EXTERNAL tree (optional; an empty directory when `external` is false)
  common/               local package sources (<PKG>_SITE_METHOD = local), mounted at /mnt/common
  native/<pkg>/BUCK     project-specific native rules (generic ones ship with the toolkit)
  golden/               committed model + manifest of the plain-make build
"""
import json
import os
from pathlib import Path


def root(start=None):
    d = Path(start or os.getcwd()).resolve()
    for p in [d, *d.parents]:
        if (p / "project.json").exists():
            return p
    raise SystemExit("no project.json found (run from inside an experiment directory)")


def load(start=None):
    r = root(start)
    cfg = json.loads((r / "project.json").read_text())
    cfg.setdefault("external", True)
    cfg.setdefault("native", [])
    cfg.setdefault("salts", {})                          # package -> any string: bump to force just that package to rebuild
    cfg.setdefault("heavy", [])                          # packages whose build must not share the machine (weight)
    cfg.setdefault("heavy_weight", os.cpu_count() or 4)
    cfg.setdefault("extra_view", {})                     # package dir -> other dirs its .mk reads (not dependencies)
    cfg.setdefault("sources", "http")                   # "http": Buck2 http_file where possible; "vendored": everything via `br2 fetch`
    cfg.setdefault("rootfs_image", "rootfs.ext4")        # what output/images/ provides to compare
    cfg.setdefault("manifest_ignore", [])                # paths whose content is random per build (compared by presence only)
    cfg["root"] = r
    return cfg


# What the instrumentation needs from the Buildroot configuration: per-package directories (one
# tree per package, so a package can be built from its dependencies' outputs alone) and
# reproducible timestamps. Appended to the project's defconfig (then `make olddefconfig`).
REQUIRED_FRAGMENT = ["BR2_PER_PACKAGE_DIRECTORIES=y", "BR2_REPRODUCIBLE=y"]


def fragment(cfg):
    return REQUIRED_FRAGMENT + list(cfg.get("config_fragment", []))


def cache_dir(cfg):
    """Build outputs live OUTSIDE the project (they exhaust file-watch limits)."""
    return Path(os.environ.get("BR2_CACHE", Path.home() / ".cache" / "br2")) / cfg["name"]
