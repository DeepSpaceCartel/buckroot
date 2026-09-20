# Buck2 owns the Buildroot package loop; Buildroot still does the work inside each
# package (see br2/pkg_action.py). One target per package, one action per target.
#
# Narrow inputs: a package action declares (and, through br2-ns.sh views, can only
# SEE) the infrastructure, its own directory, the directories of its dependency
# closure, and a slice of .config. Adding a package therefore invalidates only that
# package, the rootfs, and a few cheap config-derived actions whose outputs come out
# byte-identical for everybody else (Buck2 stops there: early cutoff).

load("//br2/generated:target.bzl", "TARGET_TUPLE")

Br2Pkg = provider(fields = {
    "dir": provider_field(str),                 # repo-relative package directory
    "dirs": provider_field(typing.Any),         # directories of the closure incl. self, deps first
    "inputs": provider_field(typing.Any),       # source artifacts of those directories
    "links": provider_field(typing.Any),        # extra view entries (files/dirs a .mk reads) of the closure
    "pkg": provider_field(str),                 # Buildroot package name, e.g. "host-fakeroot"
    "symlinks": provider_field(typing.Any),     # dangling symlinks of the closure's dirs
    "tar": provider_field(typing.Any),          # artifact: what this package ADDED + its stamps
    "topo": provider_field(typing.Any),         # [(name, tar)] transitive closure incl. self, deps first
})

Br2Infra = provider(fields = {
    "entries": provider_field(typing.Any),      # allow-list for the tree's view (br2-ns.sh)
    "symlinks": provider_field(typing.Any),     # {repo path: target} of dangling symlinks (see br2buck.py)
})

Br2Links = provider(fields = {
    "symlinks": provider_field(typing.Any),
})

def _merge_topo(infos):
    """Topological union of the dependencies' closures (keeps first occurrence)."""
    seen = {}
    topo = []
    for info in infos:
        for name, tar in info.topo:
            if name not in seen:
                seen[name] = True
                topo.append((name, tar))
    return topo

def _merge_links(infos):
    out = []
    for info in infos:
        for l in info.links:
            if l not in out:
                out.append(l)
    return out

def _merge_dirs(infos):
    seen = {}
    dirs = []
    inputs = []
    symlinks = {}
    for info in infos:
        for d in info.dirs:
            if d not in seen:
                seen[d] = True
                dirs.append(d)
        inputs += info.inputs
        symlinks.update(info.symlinks)
    return dirs, inputs, symlinks

def _outputs_of(deps):
    outs = []
    for d in deps:
        outs += d[DefaultInfo].default_outputs + d[DefaultInfo].other_outputs
    return outs

def _br2_inputs_impl(ctx):
    return [
        DefaultInfo(other_outputs = list(ctx.attrs.srcs) + _outputs_of(ctx.attrs.deps)),
        Br2Links(symlinks = ctx.attrs.symlinks),
    ]

# A bag of input files that builds nothing (prelude filegroup would try to lay the files
# out in one directory and reject duplicate names such as the many `inputs` groups).
br2_inputs = rule(
    impl = _br2_inputs_impl,
    attrs = {
        "deps": attrs.list(attrs.dep(), default = []),
        "srcs": attrs.list(attrs.source(allow_directory = True), default = []),
        # dangling symlinks cannot be Buck2 sources: declared as data, recreated in the view
        "symlinks": attrs.dict(key = attrs.string(), value = attrs.string(), default = {}),
    },
)

def _br2_infra_impl(ctx):
    return [
        DefaultInfo(other_outputs = list(ctx.attrs.srcs) + _outputs_of(ctx.attrs.deps)),
        Br2Infra(entries = ctx.attrs.entries, symlinks = ctx.attrs.symlinks),
    ]

# Everything a package action may read that is not a package directory: the same bag of
# files plus the list of entries the action's view exposes at /mnt/src (or /mnt/external).
br2_infra = rule(
    impl = _br2_infra_impl,
    attrs = {
        "deps": attrs.list(attrs.dep(), default = []),
        "entries": attrs.list(attrs.string(), default = []),
        "srcs": attrs.list(attrs.source(allow_directory = True), default = []),
        "symlinks": attrs.dict(key = attrs.string(), value = attrs.string(), default = {}),
    },
)

# With remote execution on, actions must be free to run on a worker; otherwise they stay local
# (the mount namespace needs CAP_SYS_ADMIN on whichever machine runs them).
_LOCAL_ONLY = read_config("br2", "remote_execution", "false") != "true" or read_config("br2", "dev_tools", "false") == "true"
_FRAGMENT = [l for l in read_config("br2", "fragment", "").split(";") if l]   # config lines appended to the defconfig
_ROOTFS_IMAGE = read_config("br2", "rootfs_image", "rootfs.ext4")   # the image the rootfs action returns
_HAS_EXTERNAL = read_config("br2", "external", "true") == "true"
# Dev mode (`br2 dev`): the toolkit's own scripts are referenced by PATH and are NOT inputs of the
# actions, so editing pkg_action.py / slicing.py / br2-ns.sh does not re-run gcc and the kernel.
# Deliberately unsound (a cached result may predate a script change; remote workers cannot see
# the scripts): only for iterating on the toolkit; measured runs (`br2 matrix`) never use it.
_DEV_TOOLS = read_config("br2", "dev_tools", "false") == "true"
_DEV_PATHS = {"pkg_action.py": "br2/pkg_action.py", "slicing.py": "br2/slicing.py",
              "native_pkg.py": "br2/native_pkg.py", "native_config.py": "br2/native_config.py",
              "br2-ns.sh": "scripts/br2-ns.sh"}

def _tool(artifact):
    """The script as an input artifact, or (dev mode) just its path in the project."""
    if _DEV_TOOLS:
        return _DEV_PATHS[artifact.basename]
    return artifact      # project.json: is there a BR2_EXTERNAL tree

# Remote commands start with an empty environment and Buildbarn's runner resolves `python3`
# through the command's own PATH, so the PATH is part of the action (and of its key).
_ENV = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}
# Buildbarn's local storage ignores the instance name, so separate cache "generations" (a really
# cold run vs. a warm one) need different action keys: a salt in the environment changes every
# key without changing what the actions do. Set by `br2 build`/`br2 matrix`, empty otherwise.
_SALT = read_config("br2", "cache_salt", "")
if _SALT:
    _ENV = dict(_ENV, BR2_CACHE_SALT = _SALT)

def _attrs(*groups, **extra):
    """Starlark's dict() takes one positional argument, so merge attribute groups by hand."""
    merged = {}
    for g in groups:
        merged.update(g)
    merged.update(extra)
    return merged

def _common_attrs():
    return {
        "_action": attrs.source(default = "//br2:pkg_action.py"),
        "_ns": attrs.source(default = "//scripts:br2-ns.sh"),
    }

def _full_tree_attrs():
    # config / owners / rootfs really do depend on every file (Kconfig, all make files).
    return {
        "_external": attrs.dep(default = "//buildroot-external:tree"),
        "_tree": attrs.dep(default = "//buildroot-src:tree"),
    }

def _run(ctx, mode, spec, outs, category, identifier, hidden = [], extra_args = [], script = None, weight = 1):
    if script == None:
        spec = dict(spec, ns = _tool(ctx.attrs._ns), external = _HAS_EXTERNAL)   # ns: the declared artifact, not scripts/ in the checkout
    spec_file = ctx.actions.write_json(mode + ".spec.json", spec, with_inputs = True)
    cmd = cmd_args(
        ["python3", _tool(ctx.attrs._action) if script == None else _tool(script), mode, "--spec", spec_file, "--out", outs[0].as_output()] + extra_args,
        hidden = [[] if _DEV_TOOLS else ctx.attrs._ns, hidden],
    )
    # local_only unless remote execution is enabled: package/config/rootfs actions start a
    # private mount namespace (needs CAP_SYS_ADMIN, which the remote runner container has).
    ctx.actions.run(cmd, category = category, identifier = identifier, local_only = _LOCAL_ONLY, allow_cache_upload = True, env = _ENV, weight = weight)

def _full_tree_inputs(ctx):
    return [_outputs_of([ctx.attrs._tree, ctx.attrs._external])]

# ---------------------------------------------------------------- config ----

def _br2_config_impl(ctx):
    tar = ctx.actions.declare_output("config.tar")
    dot = ctx.actions.declare_output("dot-config")
    _run(ctx, "config", {"defconfig": ctx.attrs.defconfig, "fragment": _FRAGMENT}, [tar], "br2_config", ctx.attrs.defconfig,
         hidden = _full_tree_inputs(ctx), extra_args = ["--dot-config", dot.as_output()])
    return [DefaultInfo(default_output = tar, sub_targets = {
        # the plain .config: deterministic, so unchanged symbols give an unchanged digest
        "dot_config": [DefaultInfo(default_output = dot)],
    })]

br2_config = rule(
    impl = _br2_config_impl,
    attrs = _attrs(_common_attrs(), _full_tree_attrs(), defconfig = attrs.string()),
)

# ---------------------------------------------------------------- owners ----

def _br2_owners_impl(ctx):
    out = ctx.actions.declare_output("owners.json")
    _run(ctx, "owners", {}, [out], "br2_owners", "owners.json", hidden = _full_tree_inputs(ctx),
         script = ctx.attrs._slicer)
    return [DefaultInfo(default_output = out)]

# Kconfig symbol -> directories that declare it (+ symbols read by Buildroot's own make files).
br2_owners = rule(
    impl = _br2_owners_impl,
    attrs = _attrs(_common_attrs(), _full_tree_attrs(), _slicer = attrs.source(default = "//br2:slicing.py")),
)

# --------------------------------------------------------------- package ----

def _br2_package_impl(ctx):
    dep_infos = [d[Br2Pkg] for d in ctx.attrs.deps]
    closure = _merge_topo(dep_infos)
    own_dir = ctx.label.package
    own_inputs = _outputs_of([ctx.attrs.pkg_inputs])
    dirs, inputs, symlinks = _merge_dirs(dep_infos)
    if own_dir not in dirs:
        dirs = dirs + [own_dir]
    inputs = inputs + own_inputs
    links = _merge_links(dep_infos)
    for l in ctx.attrs.links:
        if l not in links:
            links.append(l)
    symlinks = dict(symlinks)
    symlinks.update(ctx.attrs.pkg_inputs[Br2Links].symlinks)
    symlinks.update(ctx.attrs._infra_src[Br2Infra].symlinks)
    symlinks.update(ctx.attrs._infra_ext[Br2Infra].symlinks)

    # A slice of .config: only the symbols this package can read (see pkg_action.py).
    slice_tar = ctx.actions.declare_output(ctx.attrs.pkg + ".slice.tar")
    _run(ctx, "slice", {
        "dir": own_dir,
        "dirs": dirs + links,                  # extra_view dirs may own config symbols this package reads
        "dot_config": ctx.attrs._config[DefaultInfo].sub_targets["dot_config"][DefaultInfo].default_outputs[0],
        "owners": ctx.attrs._owners[DefaultInfo].default_outputs[0],
        "pkg": ctx.attrs.pkg,
    }, [slice_tar], "br2_slice", ctx.attrs.pkg, hidden = [own_inputs], script = ctx.attrs._slicer)

    sources = []
    for fname, dep in zip(ctx.attrs.source_files, ctx.attrs.sources):
        sources.append({"file": fname, "path": dep[DefaultInfo].default_outputs[0]})

    spec = {
        "closure": [{"name": n, "tar": t} for n, t in closure],
        "common_dirs": [d.label.package for d in ctx.attrs.local_srcs],
        "common_src": {d.label.package[len("common/"):]: d[DefaultInfo].default_outputs for d in ctx.attrs.local_srcs},
        # each DIRECT dependency -> its own closure (excluding itself), deps first
        "direct": {d.pkg: [n for n, _ in d.topo[:-1]] for d in dep_infos},
        "dirs": dirs,
        "dl_dir": ctx.attrs.dl_dir,
        "infra_ext": ctx.attrs._infra_ext[Br2Infra].entries,
        "infra_src": ctx.attrs._infra_src[Br2Infra].entries,
        "links": links,
        "pkg": ctx.attrs.pkg,
        "slice": slice_tar,
        "sources": sources,
        "symlinks": symlinks,
        "stamp_dir": ctx.attrs.stamp_dir,
    }
    if ctx.attrs.salt:
        spec = dict(spec, salt = ctx.attrs.salt)      # only when set: adding a field to every spec re-keys every package
    out = ctx.actions.declare_output(ctx.attrs.pkg + ".tar")
    action_inputs = [
        _outputs_of([ctx.attrs._infra_src, ctx.attrs._infra_ext]),
        inputs,
        _outputs_of(ctx.attrs.local_srcs),
    ]
    _run(ctx, "package", spec, [out], "br2_package", ctx.attrs.pkg, weight = ctx.attrs.weight, hidden = action_inputs)

    # `[viewcheck]`: the same views and inputs as the package action, no dependency outputs and no make. Building it
    # (locally, or with remote execution) proves every view entry is a declared input of this action.
    view_spec = {k: v for k, v in spec.items() if k not in ("closure", "direct", "slice", "sources")}
    check = ctx.actions.declare_output(ctx.attrs.pkg + ".viewcheck.json")
    _run(ctx, "viewcheck", view_spec, [check], "br2_viewcheck", ctx.attrs.pkg, hidden = action_inputs)
    return [
        DefaultInfo(default_output = out, sub_targets = {"viewcheck": [DefaultInfo(default_output = check)]}),
        Br2Pkg(
            dir = own_dir,
            dirs = dirs,
            inputs = inputs,
            links = links,
            pkg = ctx.attrs.pkg,
            symlinks = symlinks,
            tar = out,
            topo = closure + [(ctx.attrs.pkg, out)],
        ),
    ]

br2_package = rule(
    impl = _br2_package_impl,
    attrs = _attrs(
        _common_attrs(),
        _config = attrs.dep(default = "//br2/generated:config"),
        _infra_ext = attrs.dep(default = "//buildroot-external:infra", providers = [Br2Infra]),
        _infra_src = attrs.dep(default = "//buildroot-src:infra", providers = [Br2Infra]),
        _owners = attrs.dep(default = "//br2/generated:owners"),
        _slicer = attrs.source(default = "//br2:slicing.py"),
        pkg = attrs.string(),
        pkg_inputs = attrs.dep(),                    # this directory's `inputs` target
        stamp_dir = attrs.string(),
        dl_dir = attrs.string(default = ""),
        deps = attrs.list(attrs.dep(providers = [Br2Pkg]), default = []),
        source_files = attrs.list(attrs.string(), default = []),
        sources = attrs.list(attrs.dep(), default = []),
        local_srcs = attrs.list(attrs.dep(), default = []),
        # local CPU slots the action occupies: a heavy compile (gcc, kernel) takes them all and runs
        # alone, otherwise concurrent inner `make -jN` runs oversubscribe the machine and OOM
        weight = attrs.int(default = 1),
        # any string: changing it re-keys this package (and only its dependents) to force a rebuild
        salt = attrs.string(default = ""),
        # files of OTHER package dirs that symlinks in this one point at (view entries)
        links = attrs.list(attrs.string(), default = []),
    ),
)

# ---------------------------------------------------------------- rootfs ----

def _br2_rootfs_impl(ctx):
    infos = [d[Br2Pkg] for d in ctx.attrs.packages]
    closure = _merge_topo(infos)
    spec = {
        "below": {i.pkg: [n for n, _ in i.topo[:-1]] for i in infos},
        "closure": [{"name": n, "tar": t} for n, t in closure],
        "config": ctx.attrs._config[DefaultInfo].default_outputs[0],
    }
    out = ctx.actions.declare_output(_ROOTFS_IMAGE)
    spec = dict(spec, image = _ROOTFS_IMAGE)
    _run(ctx, "rootfs", spec, [out], "br2_rootfs", _ROOTFS_IMAGE, hidden = _full_tree_inputs(ctx))
    return [DefaultInfo(default_output = out)]

br2_rootfs = rule(
    impl = _br2_rootfs_impl,
    attrs = _attrs(
        _common_attrs(),
        _full_tree_attrs(),
        _config = attrs.dep(default = "//br2/generated:config"),
        packages = attrs.list(attrs.dep(providers = [Br2Pkg])),
    ),
)

# ================================================================== native ====
# Packages built by Buck2 actions instead of Buildroot's `make <pkg>`. They produce the same
# artifact (Br2Pkg) as a wrapped package, so the rootfs action and every other package are
# unchanged, and the result can be checked against the wrapped build byte for byte.

def _br2_untar_impl(ctx):
    out = ctx.actions.declare_output("tree", dir = True)
    ctx.actions.run(
        cmd_args(["sh", "-c", 'mkdir -p "$1" && tar -xf "$2" --strip-components=1 -C "$1"', "--", out.as_output(), ctx.attrs.src]),
        category = "br2_untar",
        env = _ENV,
    )
    return [DefaultInfo(default_output = out)]

# An upstream tarball unpacked into a directory artifact (the external toolchain).
br2_untar = rule(
    impl = _br2_untar_impl,
    attrs = {"src": attrs.source()},
)

# The flags Buildroot's toolchain wrapper adds to every compiler call (read from its
# BR2_DEBUG_WRAPPER output for this config). Native rules must reproduce them exactly.
_WRAPPER_ARCH = ["-mabi=lp64", "-mcpu=cortex-a53"]
_WRAPPER_COMPILE = ["-fstack-protector-strong", "-fPIE"]
_WRAPPER_LINK = [
    "-pie",
    "-Wl,-z,max-page-size=4096",
    "-Wl,-z,common-page-size=4096",
    "-Wl,--build-id=none",
    "-Wl,-z,now",
    "-Wl,-z,relro",
]

def _br2_cc_program_impl(ctx):
    tc = ctx.attrs.toolchain[DefaultInfo].default_outputs[0]
    cc = tc.project("bin/aarch64-buildroot-linux-musl-gcc.br_real")
    sysroot = tc.project("aarch64-buildroot-linux-musl/sysroot")
    common = ["--sysroot", sysroot] + _WRAPPER_ARCH
    objs = []
    for src in ctx.attrs.srcs:
        obj = ctx.actions.declare_output(src.basename + ".o")
        ctx.actions.run(
            cmd_args(
                [cc] + common + _WRAPPER_COMPILE + ["-D" + d for d in ctx.attrs.defines] + ctx.attrs.copts +
                ["-c", src, "-o", obj.as_output()],
                hidden = [tc],                          # cc1, as, ld and the sysroot live beside the driver
            ),
            category = "br2_cc_compile",
            identifier = src.short_path,
            env = _ENV,
            allow_cache_upload = True,
        )
        objs.append(obj)
    out = ctx.actions.declare_output(ctx.attrs.name)
    ctx.actions.run(
        cmd_args(
            [cc] + common + _WRAPPER_COMPILE + _WRAPPER_LINK + objs + ctx.attrs.ldflags + ["-o", out.as_output()],
            hidden = [tc],
        ),
        category = "br2_cc_link",
        identifier = ctx.attrs.name,
        env = _ENV,
        allow_cache_upload = True,
    )
    return [DefaultInfo(default_output = out)]

br2_cc_program = rule(
    impl = _br2_cc_program_impl,
    attrs = {
        "copts": attrs.list(attrs.string(), default = []),
        "defines": attrs.list(attrs.string(), default = []),
        "ldflags": attrs.list(attrs.string(), default = []),
        "srcs": attrs.list(attrs.source()),
        "toolchain": attrs.dep(),
    },
)

# `make` considers a package done when these exist (they differ per kind of package).
BR2_STAMPS_LOCAL = [".stamp_rsynced", ".stamp_configured", ".stamp_built", ".stamp_target_installed", ".stamp_installed"]
BR2_STAMPS_TARGET = [".stamp_downloaded", ".stamp_extracted", ".stamp_patched", ".stamp_configured", ".stamp_built", ".stamp_target_installed", ".stamp_installed"]
BR2_STAMPS_HOST = [".stamp_downloaded", ".stamp_extracted", ".stamp_patched", ".stamp_configured", ".stamp_built", ".stamp_host_installed", ".stamp_installed"]
BR2_STAMPS_STAGING = [".stamp_downloaded", ".stamp_extracted", ".stamp_patched", ".stamp_configured", ".stamp_built", ".stamp_staging_installed", ".stamp_installed"]

_STAGING_DIR = "host/" + TARGET_TUPLE + "/sysroot"

def _entries(ctx):
    out = []
    for tree, attr in (("target", ctx.attrs.install), ("host", ctx.attrs.host_install), ("staging", ctx.attrs.staging_install)):
        for dest, dep in attr.items():
            out.append({
                "dest": dest,
                "kind": "file",
                "mode": ctx.attrs.modes.get(tree + ":" + dest, "0755" if tree != "staging" else "0644"),
                "src": dep[DefaultInfo].default_outputs[0],
                "tree": tree,
            })
    for tree, attr in (("target", ctx.attrs.links), ("host", ctx.attrs.host_links)):
        for dest, target in attr.items():
            out.append({"dest": dest, "kind": "link", "target": target, "tree": tree})
    for tree, attr in (("target", ctx.attrs.dirs), ("host", ctx.attrs.host_dirs)):
        for dest in attr:
            out.append({"dest": dest, "kind": "dir", "tree": tree})
    return out

def _br2_host_program_impl(ctx):
    # Compiled with the AMBIENT host compiler (Buildroot's HOSTCC): the worker image pins it.
    out = ctx.actions.declare_output(ctx.attrs.name)
    maps = []
    if ctx.attrs.source_root:
        # __FILE__ ends up in the binary: make the source path what Buildroot's build has
        # (relative to its tree), not the artifact's location under buck-out
        maps = [cmd_args(src, parent = 1, format = "-ffile-prefix-map={}=" + ctx.attrs.source_root) for src in ctx.attrs.srcs]
    ctx.actions.run(
        cmd_args(["gcc"] + ctx.attrs.flags + maps + ctx.attrs.srcs + ["-o", out.as_output()]),
        category = "br2_host_cc",
        identifier = ctx.attrs.name,
        env = _ENV,
        allow_cache_upload = True,
    )
    return [DefaultInfo(default_output = out)]

br2_host_program = rule(
    impl = _br2_host_program_impl,
    attrs = {
        "flags": attrs.list(attrs.string(), default = []),
        "source_root": attrs.string(default = ""),
        "srcs": attrs.list(attrs.source()),
    },
)

def br2_dep(name, wrapped):
    """Dependency label for package `name`: its native target when `[br2] native` lists it, so a
    closure never contains the same package twice (once wrapped, once native)."""
    if name in read_config("br2", "native", "").split(","):
        # project-specific natives (native/) are listed in [br2] native_project; the rest ship with the toolkit
        base = "//native/" if name in read_config("br2", "native_project", "").split(",") else "//br2/native/"
        return base + name + ":" + name
    return wrapped

def _trees(ctx):
    """`install_trees = {"[tree:]dest": path}`: install everything below `path` into the target
    tree (or, with `staging:`, the toolchain sysroot) at <dest>, rsync-style. `path` is relative
    to the Buildroot package dir, or a repo path such as buildroot-src/system/skeleton. The
    files come from declared inputs; symlinks that dangle (invisible to Buck2) come from the
    recorded data."""
    out = []
    for key, path in ctx.attrs.install_trees.items():
        tree, _, dest = key.rpartition(":") if ":" in key else ("target", "", key)
        if path.startswith("buildroot-src/") or path.startswith("buildroot-external/"):
            infra = ctx.attrs._infra_src if path.startswith("buildroot-src/") else ctx.attrs._infra_ext
            root = path.split("/")[0]
            sub = path[len(root) + 1:]
            artifacts = infra[DefaultInfo].other_outputs
            links = infra[Br2Infra].symlinks
            prefix = path + "/"
        else:
            sub = path
            artifacts = ctx.attrs.pkg_inputs[DefaultInfo].other_outputs
            links = ctx.attrs.pkg_inputs[Br2Links].symlinks
            prefix = ctx.attrs.bdir + "/" + path + "/"
        srcs = []
        for a in artifacts:
            sp = a.short_path
            if sp == sub or sp.startswith(sub + "/"):
                srcs.append({"path": a, "rel": sp[len(sub) + 1:]})
        out.append({
            "dest": dest,
            "links": {k[len(prefix):]: v for k, v in links.items() if k.startswith(prefix)},
            "mode": ctx.attrs.tree_modes.get(key, ""),
            "srcs": srcs,
            "tree": tree or "target",
        })
    return out

def _br2_native_package_impl(ctx):
    dep_infos = [d[Br2Pkg] for d in ctx.attrs.deps]
    closure = _merge_topo(dep_infos)
    dirs, inputs, symlinks = _merge_dirs(dep_infos)
    # A native package stands in for a Buildroot package: packages that still build with
    # `make` need that package's .mk (and files) in their view to know the dependency at all,
    # so it is reported as this package's directory and inputs, not br2/native/<pkg>.
    own_dir = ctx.attrs.bdir
    if own_dir not in dirs:
        dirs = dirs + [own_dir]
    inputs = inputs + _outputs_of([ctx.attrs.pkg_inputs])
    symlinks = dict(symlinks)
    symlinks.update(ctx.attrs.pkg_inputs[Br2Links].symlinks)
    links = _merge_links(dep_infos)

    cfg = None
    if ctx.attrs.config:
        # only the declared symbols reach the action: any other config change leaves this
        # file (and so the package's action key) byte-identical
        cfg = ctx.actions.declare_output(ctx.attrs.pkg + ".cfg.json")
        ctx.actions.run(
            cmd_args(["python3", _tool(ctx.attrs._config_tool), "--dot-config", ctx.attrs._config[DefaultInfo].sub_targets["dot_config"][DefaultInfo].default_outputs[0], "--symbols"] + ctx.attrs.config + ["--out", cfg.as_output()]),
            category = "br2_native_config",
            identifier = ctx.attrs.pkg,
            env = _ENV,
            allow_cache_upload = True,
        )
    out = ctx.actions.declare_output(ctx.attrs.pkg + ".tar")
    spec = ctx.actions.write_json("native.spec.json", {
        "cfg": cfg,
        "inputs": {k: v[DefaultInfo].default_outputs[0] for k, v in ctx.attrs.recipe_inputs.items()},
        "recipe": ctx.attrs.recipe,
        "entries": _entries(ctx),
        "pkg": ctx.attrs.pkg,
        "stamp_dir": ctx.attrs.stamp_dir,
        "stamps": ctx.attrs.stamps,
        "staging_dir": _STAGING_DIR,
        "trees": _trees(ctx),
    }, with_inputs = True)
    ctx.actions.run(
        cmd_args(["python3", _tool(ctx.attrs._tool), "--spec", spec, "--out", out.as_output()]),
        category = "br2_native_package",
        identifier = ctx.attrs.pkg,
        env = _ENV,
        allow_cache_upload = True,
    )
    return [
        DefaultInfo(default_output = out),
        Br2Pkg(
            dir = own_dir,
            dirs = dirs,
            inputs = inputs,
            links = links,
            pkg = ctx.attrs.pkg,
            symlinks = symlinks,
            tar = out,
            topo = closure + [(ctx.attrs.pkg, out)],
        ),
    ]

# `deps` still name the Buildroot dependencies (they order the overlay in the rootfs);
# a native package does not consume their tars to build itself. Files installed into the
# target tree (`install`, `links`, `dirs`), the host tree (`host_*`) or the toolchain
# sysroot (`staging_install`); `stamps` says which make steps count as done.
br2_native_package = rule(
    impl = _br2_native_package_impl,
    attrs = {
        "_config": attrs.dep(default = "//br2/generated:config"),
        "_config_tool": attrs.source(default = "//br2:native_config.py"),
        "_infra_ext": attrs.dep(default = "//buildroot-external:infra", providers = [Br2Infra]),
        "_infra_src": attrs.dep(default = "//buildroot-src:infra", providers = [Br2Infra]),
        "_tool": attrs.source(default = "//br2:native_pkg.py"),
        "config": attrs.list(attrs.string(), default = []),   # Kconfig symbols the recipe reads
        "recipe": attrs.option(attrs.source(), default = None),
        "recipe_inputs": attrs.dict(key = attrs.string(), value = attrs.dep(), default = {}),   # artifacts the recipe reads
        "bdir": attrs.string(),                       # the Buildroot package dir this replaces
        "deps": attrs.list(attrs.dep(providers = [Br2Pkg]), default = []),
        "dirs": attrs.list(attrs.string(), default = []),
        "host_dirs": attrs.list(attrs.string(), default = []),
        "host_install": attrs.dict(key = attrs.string(), value = attrs.dep(), default = {}),
        "host_links": attrs.dict(key = attrs.string(), value = attrs.string(), default = {}),
        "install": attrs.dict(key = attrs.string(), value = attrs.dep(), default = {}),
        "install_trees": attrs.dict(key = attrs.string(), value = attrs.string(), default = {}),
        "tree_modes": attrs.dict(key = attrs.string(), value = attrs.string(), default = {}),
        "links": attrs.dict(key = attrs.string(), value = attrs.string(), default = {}),
        "modes": attrs.dict(key = attrs.string(), value = attrs.string(), default = {}),
        "pkg": attrs.string(),
        "pkg_inputs": attrs.dep(),                    # that directory's `inputs` target
        "stamp_dir": attrs.string(),
        "stamps": attrs.list(attrs.string()),
        "staging_install": attrs.dict(key = attrs.string(), value = attrs.dep(), default = {}),
    },
)
