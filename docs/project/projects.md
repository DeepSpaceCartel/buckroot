<title>Projects</title>

# Projects

Each project lives in its own directory under
[`experiments/`](https://github.com/DeepSpaceCartel/buckroot/tree/main/experiments) with a `project.json`,
a golden reference and its results. This page records what each one is and what it needed from the
toolkit; the numbers are on [Results](results.md).

| Project | Buildroot | Target | Packages | Status |
|---|---|---|---|---|
| [helloworld](#helloworld) | 2025.02.18 | aarch64, musl, external toolchain | 29 | full matrix done |
| [superduperbird](#superduperbird) | 2024.05.3 | aarch64, glibc, internal toolchain | 98 | matrix in progress |
| [funkey-os](#funkey-os) | 2021.02 (vendor fork) | 32-bit ARM, musl, external toolchain | 143 | model and sources ready |
| [home-assistant-os](#home-assistant-os) | 2024.02 (vendor fork) | aarch64, glibc, internal toolchain | 205 | model ready, sources pending |

### Candidates

Projects not started yet, chosen because each covers something the four above do not. The
four above cover aarch64 glibc with an internal toolchain, an old 32-bit ARM musl fork with an
external toolchain, and a large systemd/Docker/Go stack, each with a single external tree and a
tar rootfs.

| Project | Buildroot | Target | What it adds | Status |
|---|---|---|---|---|
| In-tree `qemu_x86_64_defconfig` | upstream | x86_64, glibc | no external tree, no vendor fork | candidate |
| In-tree `qemu_riscv64_virt_defconfig` | upstream | riscv64, glibc | RISC-V | candidate |
| In-tree `qemu_mips64el_malta_defconfig` | upstream | mips64el | MIPS | candidate |
| In-tree `qemu_ppc64le_pseries_defconfig` | upstream | ppc64le | PowerPC | candidate |
| In-tree `qemu_arm_versatile_nommu_defconfig` | upstream | ARM noMMU, uClibc-ng | FLAT binaries, no shared libraries; breaks ELF assumptions in the rootfs merge | candidate |
| Buildroot test suite (`support/testing/tests/package/`) | upstream | various, QEMU | one tiny image per package infrastructure (cargo, golang, python-pep517/flit/setuptools, luarocks, perl, meson, waf, qmake, kconfig, rebar), each with a runtime test | candidate |
| [Nerves](https://github.com/nerves-project/nerves_system_br) (with a system such as `nerves_system_rpi4`) | external tree | aarch64 and others | Erlang/OTP host build, squashfs `.fw` image, a custom wrapper around `make` | candidate |
| [SkiffOS](https://github.com/skiffos/SkiffOS) | external trees | many boards | several stacked `BR2_EXTERNAL` trees, layered configuration | candidate |
| [OpenIPC](https://github.com/OpenIPC/firmware) / [Thingino](https://github.com/themactep/thingino-firmware) | fork | MIPS (Ingenic, HiSilicon), uClibc or musl | MIPS, uClibc, squashfs rootfs, tiny stripped images | candidate |
| [Bottlerocket SDK](https://github.com/bottlerocket-os/bottlerocket-sdk) | upstream, own defconfigs | x86_64 and aarch64 toolchains | host-only, toolchain-only build with no target rootfs; a production user | candidate |
| [buildroot-external-st](https://github.com/STMicroelectronics/buildroot-external-st) | external tree | ARMv7 (STM32MP1), glibc | TF-A, OP-TEE, U-Boot, post-image scripts and genimage | candidate |
| [buildroot-external-microchip](https://github.com/linux4microchip/buildroot-external-microchip) | external tree | ARMv7 (SAMA5) and RISC-V (PolarFire) | vendor BSP, RISC-V, genimage | candidate |
| [Milk-V Duo SDK](https://github.com/milkv-duo/duo-buildroot-sdk) | vendor fork | riscv64 (Sophgo CV1800B) | RISC-V vendor SDK, post-image scripts | candidate |
| [Batocera](https://github.com/batocera-linux/batocera.linux) / [Knulli](https://github.com/knulli-cfw/distribution) | fork | x86_64 and many ARM SoCs | hundreds of packages, Qt, SDL, Python, emulator cores; a stress test for hidden references | candidate |
| [motionEyeOS](https://github.com/motioneye-project/motioneyeos) / thingOS | old fork | ARM (Raspberry Pi and others) | Python-heavy image on an old Buildroot; archived, so a fixed target | candidate |

Not candidates, because they only look like Buildroot: OpenWrt (forked in 2004, incompatible
package format), LibreELEC, Lakka and CoreELEC (their own build system), and Yocto-based projects
such as AGL, BalenaOS and OpenSTLinux.

## helloworld

A minimal image written for developing the toolkit: Bootlin's external musl toolchain, BusyBox
init, and one local package (`hello`, sources in `common/`). It has a QEMU boot test
(`tests/test-tier0.py`) that asserts the guest architecture and the program's output. Its `native`
list covers the whole dependency closure of `hello` (12 packages, including the toolchain trio), so it
is the reference for what a native package looks like.

## superduperbird

[`nd-0r/superduperbird-buildroot`](https://github.com/nd-0r/superduperbird-buildroot), firmware for the
Spotify Car Thing (Amlogic S905D2), pinned at commit `fcc1ef9`. An internal glibc toolchain, a 4.9 vendor
kernel, Mesa (`mesa3d`), SDL2, avahi, OpenSSH and a Rust host toolchain (`host-rust-bin`), for 98 packages
and 199 Buck2 actions. The rootfs is a tar.

What it needed:

- **`extra_view` for hidden references:** `util-linux` includes the makefile of its child directory `util-linux-libs` (found only by the
  remote view check: a directory bind exposes the child locally, but the worker has only declared files), `gettext-tiny` reads `gettext-gnu`, `avahi` reads `python3`,
  `gcc-initial` and `gcc-final` read the `package/gcc` group directory, `autoconf` reads `automake`,
  `rust-bin` reads `rustc`, `util-linux` reads `ncurses`, `linux` reads `uboot-tools`,
  `skeleton-init-common` reads `mkpasswd`.
- **`heavy`:** both GCC builds, the kernel, Mesa, host CMake and host Python, so two of them never overlap
  (an out-of-memory kill otherwise).
- **A kernel-release stub:** the rootfs action runs `depmod`, whose `kernelrelease` probe needs the kernel's
  build tree, which is not part of the rootfs action's inputs.
- **`manifest_ignore` for `/etc/shadow`:** the root password hash has a random salt on every build.
- **Vendored sources**, because some downloads are git checkouts or have only SHA-512 hashes.
- **One oversized source**: `googlefontdirectory` downloads the whole `google/fonts` repository at one commit (965 MB compressed, 1.9 GB
  extracted) to install a single family, `ufl/ubuntu` (2.9 MB in the image). The recipe cannot fetch a subset. It is faithful to Buildroot, costs one
  large upload per cache and one 1.9 GB extraction, and it sets the minimum block size of the Buildbarn storage
  ([Sizing the storage](../guides/buildbarn.md#sizing-the-storage)).
- **Three deviations from the project's defconfig**, in `notes`: no post-image script, an older kernel
  config that builds at the pinned commit, and the device-tree settings the external tree's hook needs.

## funkey-os

[FunKey-OS 2.3.0](https://github.com/FunKey-Project/FunKey-OS), firmware for the FunKey S handheld
(Allwinner V3s, Cortex-A7). The external tree is the `FunKey/` directory of a monorepo, built on the
FunKey fork of Buildroot (2021.02), pinned by the monorepo's git submodule. A prebuilt musl toolchain is
downloaded as an external toolchain, so nothing compiles a compiler, and the image is small (143
packages, 150 vendored sources).

What it needed from the toolkit, all of it because the Buildroot tree is old:

- `buildroot.commit` and `external_repo.subdir` in `project.json`.
- A `printvars` fallback where `show-vars` does not exist, and `build_dir` where `show-info` has no
  `stamp_dir`.
- A raised stack limit: GNU make 4.3 segfaults in the old `printvars`.
- `FORCE_UNSAFE_CONFIGURE=1`: the old `host-tar` refuses to configure as root.

## home-assistant-os

[Home Assistant OS 18.3](https://github.com/home-assistant/operating-system), generic aarch64 (UEFI)
board. The external tree is `buildroot-external/` of the monorepo, on the Home Assistant fork of
Buildroot (2024.02), with an internal glibc toolchain, systemd, Docker and containerd, RAUC, NetworkManager,
and a mainline 6.18 kernel built with LTO: 205 packages, including Go-based ones.

Deviations, in `notes`: no ccache (its directory is outside the build), no post-image script (it
assembles disk images), and a tar rootfs in place of EROFS so the manifest scanner can read it.

What it needed so far: local package sources that live inside the external tree
(`package/hassio`), which the extractor now accepts. Downloading Go module sources runs `make source`, which
builds a Go toolchain, and the log showed parts of the compiler being built too, as a side effect (probably
through `host-go`'s dependencies); that makes `br2 fetch` expensive on this project.
