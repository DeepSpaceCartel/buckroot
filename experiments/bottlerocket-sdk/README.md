# bottlerocket-sdk

The toolchain and host tools AWS builds Bottlerocket with ([`bottlerocket-os/bottlerocket-sdk`](https://github.com/bottlerocket-os/bottlerocket-sdk),
v0.79.0): Buildroot 2025.05.1 plus the SDK's five-patch series, x86_64 glibc. The build product is a cross toolchain and sysroot, not a firmware image.

- `buildroot-external/configs/` holds the SDK's four defconfigs, unchanged, in a minimal BR2_EXTERNAL (the SDK has no packages of its own).
- `patches/buildroot/0001-0005` are the SDK's Buildroot patches (sysroot and tools-directory controls for binutils and gcc), applied by `br2 setup`.
- `project.json` `config_fragment` turns off `BR2_PRIMARY_SITE_ONLY`: the SDK's Dockerfile pre-fetches every source into a local directory and the defconfigs
  say so; here Buildroot downloads normally. Nothing else in the configuration changes.
- Not run: the aarch64 and musl variants (the same project with another `defconfig`).

See `docs/project/projects.md` and `docs/project/results.md`.
