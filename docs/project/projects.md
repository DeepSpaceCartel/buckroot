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

Candidates for the next ports are summarised in [Candidates](#candidates) at the end of this page.

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

## Candidates

Projects not started yet, each chosen because it covers something the four above do not. The four
ported projects share a shape: one external tree, one Buildroot pin, and a toolchain that is either
a downloaded external musl one or an internal glibc one. The table is ordered by my estimate of value
per unit of effort; the sections below it carry the evidence.

| Project | Buildroot | Target | Packages | Value for migration |
|---|---|---|---|---|
| [Bottlerocket SDK](#bottlerocket-sdk) | 2025.05.1, patched | x86_64, aarch64; glibc, musl | 33, 32 | **High.** Smallest real project; toolchain-only build; patched tree |
| [Nerves (rpi4)](#nerves) | 2026.05.3, patched | aarch64, glibc, no init | not measured | **High.** Newest Buildroot; Erlang runtime; build driven by a wrapper |
| [In-tree QEMU defconfigs](#in-tree-qemu-defconfigs) | any release | x86_64, riscv64, mips64el, ppc64le | 63 to 69 | **High.** Four architectures, no external tree, lowest effort |
| [Microchip](#microchip) | 2025.02.16 or 2025.02-mchp fork | riscv64, arm; glibc | 192, 320 | **Medium-high.** Vendor BSP with U-Boot, genimage, systemd; two Buildroot flavours |
| [STMicroelectronics](#stmicroelectronics) | 2025.02.12 | arm, aarch64; glibc | 72, 145 | **Medium.** TF-A, OP-TEE, U-Boot, Qt5, genimage; four vendor forks |
| [Buildroot test suite](#buildroot-test-suite) | any release | many, QEMU | small each | **Medium.** Many tiny images; needs config extraction from Python |
| [In-tree noMMU defconfigs](#in-tree-nommu-defconfigs) | any release | riscv64, xtensa; uClibc | 64 | **Medium, risky.** FLAT binaries, initramfs; may break ELF assumptions |
| [OpenIPC](#openipc) | 2024.02.10 | mipsel and others; musl | not measured | **Medium.** MIPS, external musl toolchain, many chip variants |
| [Thingino](#thingino) | fork, 2026.08-rc3 | Ingenic MIPS | not measured | **Medium.** MIPS, submodule pin, 178 camera configs |
| [Milk-V Duo SDK](#milk-v-duo-sdk) | 2021.05 vendored | riscv64, musl | 133 | **Medium.** RISC-V; Buildroot buried in a large SDK; stale |
| [SkiffOS](#skiffos) | fork, 2026.11-git | many boards | not measured | **Medium.** Layered configuration selected at build time |
| [thingOS](#thingos) | 2021.11 vendored | arm, glibc | 114 | **Low-medium.** Small and old; overlaps FunKey-OS |
| [motionEyeOS](#motioneyeos) | 2020.05.1 vendored | arm, glibc | 171 | **Low-medium.** Oldest tree; unmaintained; Python-heavy |
| [Batocera](#batocera) | fork, 2026.05-git | x86_64, many ARM SoCs | not measured | **Low-medium.** Stress test, not a first port |
| [Knulli](#knulli) | fork, 2024.11 | ARM handhelds | not measured | **Low.** Archived, and a Batocera derivative |

Not candidates, because they only look like Buildroot: OpenWrt (forked in 2004, incompatible
package format), LibreELEC, Lakka and CoreELEC (their own build system), and Yocto-based projects
such as AGL, BalenaOS and OpenSTLinux.

### How these numbers were taken

- **Packages** is the number of entries `make show-info` reports for the named defconfig, host
  packages included. In-tree defconfigs were measured on the 2025.02.18 tree the helloworld
  experiment uses. External projects were measured on the Buildroot version they pin. The
  toolkit's own count may differ by a few.
- **Not measured** means the image is assembled by a wrapper (a Makefile, a script, an environment
  the defconfig depends on) that I did not run.
- **Value** is a judgement. It weighs what the project adds that the four ported ones do not,
  against how much toolkit work it probably needs. Statements about what a project "would need" are
  inferences from the toolkit's [project.json](../reference/project-json.md) keys, not tried ports.
- Activity and stars are from GitHub on 2026-09-21.

### Bottlerocket SDK

[`bottlerocket-os/bottlerocket-sdk`](https://github.com/bottlerocket-os/bottlerocket-sdk), the
toolchain and host tools AWS uses to build Bottlerocket. Not a firmware image.

- **Buildroot:** upstream 2025.05.1 downloaded as a tarball (hash in `hashes/buildroot`), with a
  patch series from `patches/buildroot` (sysroot and tools-directory controls for binutils and gcc).
- **Configs:** four defconfigs in `configs/buildroot/`: `sdk_{x86_64,aarch64}_{gnu,musl}`.
- **Size:** 33 packages for `x86_64_gnu`, 32 for `aarch64_musl`, measured on the unpatched tree.
- **Contents:** GCC 13.4.0, binutils 2.44, glibc 2.41 or musl 1.2.5, Linux headers 6.1.147, built in
  a Fedora 43 builder image.
- **Activity:** pushed 2026-09-18, Apache-2.0, 58 stars.
- **What it adds:** a patched Buildroot tree, and a build whose product is a toolchain and sysroot
  rather than a bootable rootfs. A production user you can name.
- **Would need:** a way to apply the patch series to `buildroot-src/` at setup. I found no
  `project.json` key for that. The Dockerfile's older-distribution compatibility stage may matter
  for reproducing the exact toolchain.

### Nerves

[`nerves-project/nerves_system_br`](https://github.com/nerves-project/nerves_system_br) is the
shared Buildroot external tree. Each board is its own repository, for example
[`nerves_system_rpi4`](https://github.com/nerves-project/nerves_system_rpi4). There are many
systems, from Raspberry Pi to BeagleBone, x86_64, GRiSP2 and QEMU.

- **Buildroot:** upstream 2026.05.3, set as `NERVES_BR_VERSION` in `create-build.sh`, with 17 files
  under `patches/buildroot`.
- **Tree:** 13 package directories in the shared tree; `nerves_defconfig` in the board repository.
- **Target (rpi4):** aarch64 Cortex-A72, glibc, `BR2_INIT_NONE` (the Erlang runtime is the init),
  custom skeleton. The toolchain is a prebuilt Nerves GCC 15.3.0, downloaded. The kernel is a
  Raspberry Pi 6.18 tarball.
- **Image:** `post-createfs.sh` runs fwup to produce a `.fw` firmware file.
- **Activity:** pushed 2026-09-18, release v1.34.5 on 2026-09-15, 414 stars.
- **What it adds:** the newest Buildroot of any candidate, no init system, an Erlang/OTP runtime,
  and a build that is not `make <defconfig>`: the defconfig refers to `NERVES_DEFCONFIG_DIR` and
  other variables set by the wrapper.
- **Would need:** the wrapper's environment reproduced in the experiment, the patch series applied,
  and the fwup step skipped or replaced, as for Home Assistant OS's disk images.
- **Package count:** not measured, because the defconfig does not configure without that environment.

### In-tree QEMU defconfigs

Buildroot's own `qemu_*` defconfigs. No external tree, no vendor fork.

| Defconfig | Packages | Rootfs formats |
|---|---|---|
| `qemu_x86_64_defconfig` | 67 | ext2 |
| `qemu_riscv64_virt_defconfig` | 65 | ext2, tar |
| `qemu_mips64el_malta_defconfig` | 63 | ext2 |
| `qemu_ppc64le_pseries_defconfig` | 69 | ext2 |

- **Common shape:** internal glibc toolchain, BusyBox init, Linux 6.12.27, measured on 2025.02.18.
  The tree has 283 defconfigs in all.
- **What it adds:** three architectures (RISC-V, MIPS, PowerPC) plus x86_64 with the cheapest
  possible setup: `external: false`, no vendored sources beyond what the tree downloads.
- **Would need:** for the three ext2-only defconfigs, a `config_fragment` that enables a tar rootfs,
  since the manifest scanner reads tar (the riscv64 one already builds one). Weak as a credibility
  demonstration, strong as a portability check.

### In-tree noMMU defconfigs

- **Defconfigs present in 2025.02.18:** `qemu_riscv64_nommu_virt`, `qemu_riscv32_nommu_virt` and
  `qemu_xtensa_lx60_nommu`. There is no ARM noMMU QEMU defconfig; my earlier suggestion of
  `qemu_arm_versatile_nommu_defconfig` was wrong. The ARM noMMU option is the Cortex-M boards, such
  as `stm32f429_disco_xip_defconfig`, which also use XIP.
- **Measured:** `qemu_riscv64_nommu_virt` has 64 packages (uClibc, `BR2_BINFMT_FLAT`, ext2 and tar);
  `qemu_xtensa_lx60_nommu` has 64 (uClibc, FLAT, cpio initramfs).
- **What it adds:** FLAT binaries instead of ELF, no shared libraries, an initramfs image.
- **Risk:** any step of the rootfs merge that assumes ELF files or `.so` files will fail here. That
  is also why it is worth trying once.

### Buildroot test suite

`support/testing/` in the Buildroot tree: 752 test classes, 415 of them under `tests/package/`.

- **Format:** each test carries its configuration as a Python string, not as a defconfig file, and
  boots the image in QEMU to check it.
- **Coverage by files whose configuration mentions the package family:** Python 110, Lua 34, Perl 13,
  Go 2, Rust 1, Qt5 1, Meson (through Weston) 1, Erlang 0. It is wide for Python, Lua and Perl and
  thin elsewhere; my earlier claim that it exercises every infrastructure (waf, qmake, kconfig,
  rebar) was not verified and should be dropped.
- **What it adds:** many small, independent images, each with a runtime check.
- **Would need:** a script that extracts the config strings into defconfigs. Worth doing for a
  chosen handful (Go, Rust, Lua, Python), not for all 415.

### Microchip

[`linux4microchip/buildroot-external-microchip`](https://github.com/linux4microchip/buildroot-external-microchip),
an external tree for Microchip's AT91 (SAMA5, SAMA7, SAM9X), PolarFire SoC and PIC64GX boards.

- **Buildroot:** two flavours in one external tree. PolarFire and PIC64GX use upstream 2025.02.16.
  AT91 needs the `buildroot-mchp` fork at branch `2025.02-mchp`. Older branches `2022.02-mchp` and
  `2023.02-mchp` exist.
- **Configs:** 65 defconfigs; 42 package directories in the external tree.
- **Measured:** `icicle_defconfig` (riscv64, internal glibc toolchain, systemd) has 192 packages;
  `sama7d65_curiosity_graphics_defconfig` (arm, internal glibc toolchain, systemd) has 320, on the fork.
- **Also in the defconfig:** custom U-Boot, `genimage`, a post-image script, kernel from
  `linux4microchip-2026.04` tarballs.
- **Activity:** pushed 2026-09-08, 31 stars.
- **What it adds:** RISC-V with a vendor bootloader chain, a second Buildroot flavour selected per
  board, and image assembly you would have to skip or reproduce.
- **Would need:** `buildroot.repo` set to the fork for the AT91 boards, and the post-image script
  skipped, as for superduperbird.

### STMicroelectronics

[`bootlin/buildroot-external-st`](https://github.com/bootlin/buildroot-external-st), branch
`st/2025.02.12`. My earlier link to a `STMicroelectronics/` repository was wrong; this is the
maintained tree, by Bootlin.

- **Buildroot:** upstream 2025.02.12.
- **Configs:** 20 defconfigs for STM32MP135, MP157, MP215, MP235 and MP257 boards, each as `_flash`,
  plain and `_demo`. Three package directories.
- **Measured:** `st_stm32mp157d_dk1` has 72 packages (arm, external glibc toolchain, ext2 and ext4).
  `st_stm32mp257f_dk_demo` has 145 (aarch64, external glibc toolchain, squashfs, Qt5).
- **Also in the defconfig:** TF-A, OP-TEE OS and U-Boot from STMicroelectronics forks, kernel
  `6.6-stm32mp-r3`, `genimage`, a post-image script that builds an SD-card image.
- **Activity:** pushed 2026-07-30, 90 stars.
- **What it adds:** a full secure-boot firmware chain built by Buildroot, and Qt5.
- **Would need:** the same image-assembly skip as Microchip. Four vendor forks (kernel, U-Boot, TF-A, OP-TEE) to vendor as custom tarball sources.

### OpenIPC

[`OpenIPC/firmware`](https://github.com/OpenIPC/firmware), IP-camera firmware.

- **Buildroot:** upstream 2024.02.10, downloaded by the top-level Makefile, which also sets
  compiler flags for older host packages.
- **Tree:** `BR2_EXTERNAL=general` plus one `br-ext-chip-*` directory per vendor. 155 package
  directories in `general/package`.
- **Configs:** per chip family, for example HiSilicon 43, SigmaStar 27, Goke 15, Ingenic 12 and
  Novatek 2. Other families exist and were not counted.
- **Example:** `t31_lite_defconfig` is mipsel XBurst with a downloaded external musl toolchain
  (`mipsel-openipc-linux-musl`, headers 3.10).
- **Activity:** pushed 2026-09-20, MIT, 2,206 stars.
- **What it adds:** MIPS, an external toolchain that is not Bootlin's, and two external-tree layers.
- **Package count:** not measured; the Makefile picks the chip tree.

### Thingino

[`themactep/thingino-firmware`](https://github.com/themactep/thingino-firmware), firmware for
Ingenic SoC cameras.

- **Buildroot:** the `themactep/buildroot` fork at commit `62b5743`, reporting 2026.08-rc3, pinned
  by a git submodule, the same shape as FunKey-OS.
- **Tree:** 174 package directories; 178 entries under `configs/cameras`; configuration fragments
  for XBurst1 and XBurst2 SoCs and a `uclibc` set.
- **Activity:** pushed 2026-09-20, MIT, 2,160 stars.
- **What it adds:** MIPS with uClibc fragments, and a very large number of near-identical board
  configs, which is a good test for caching across variants.
- **Not verified:** which libc a given camera image uses. My earlier "uClibc or musl" was a guess for
  both this and OpenIPC; OpenIPC's sample is musl.
- **Package count:** not measured.

### Milk-V Duo SDK

[`milkv-duo/duo-buildroot-sdk`](https://github.com/milkv-duo/duo-buildroot-sdk) (Sophgo CV180x).

- **Buildroot:** 2021.05, copied into the SDK repository as `buildroot-2021.05/`, next to Linux 5.10,
  U-Boot 2021.10, OpenSBI and other components. A sparse checkout of the Buildroot directory alone
  was 723 MB.
- **Configs:** 11 defconfigs for Duo and Duo 256M, on SD, SPI NAND and SPI NOR, plus two Cvitek ones.
- **Measured:** `milkv-duo-sd_musl_riscv64_defconfig` has 133 packages (external riscv64 musl
  toolchain, headers 5.10, an ext2 rootfs of 786 MB).
- **Activity:** last push 2025-05-22, 494 stars.
- **What it adds:** RISC-V with a vendor toolchain, and a Buildroot that the wrapper script drives
  together with the rest of the SDK.
- **Not checked:** how the toolchain is fetched.

### SkiffOS

[`skiffos/SkiffOS`](https://github.com/skiffos/SkiffOS), a minimal OS for running containers.

- **Buildroot:** the `skiffos/buildroot` fork as a submodule at `8256d48`, reporting `2026.11-git`,
  a development version ahead of the 2026.08 release.
- **Tree:** 29 layer directories under `configs/` (Raspberry Pi, Rockchip, Intel, Apple, virtual
  machines, `core`, and more). A build combines them, for example `SKIFF_CONFIG=pi/4,core/debian`.
- **Activity:** pushed 2026-09-16, release 2026.08 on 2026-08-03, MIT, 817 stars.
- **What it adds:** stacked configuration layers instead of one defconfig.
- **Package count:** not measured; the defconfig is assembled by the Makefile.

### thingOS

[`ccrisan/thingos`](https://github.com/ccrisan/thingos), by the author of motionEyeOS.

- **Buildroot:** 2021.11, copied into the repository (not a submodule). A `buildroot.repo` pointing
  at the project itself should work; not tried.
- **Configs:** Raspberry Pi 2, 3, 4 and 64-bit, NanoPi R1 and Radxa CM3, each with an initramfs variant.
- **Measured:** `raspberrypi3_defconfig` has 114 packages (arm, external glibc toolchain, BusyBox init).
- **Activity:** pushed 2026-08-23, 233 stars.
- **What it adds:** little that FunKey-OS does not. Useful only as a quick, small extra.

### motionEyeOS

[`motioneye-project/motioneyeos`](https://github.com/motioneye-project/motioneyeos), branch `dev`.

- **Buildroot:** 2020.05.1, copied into the repository. The oldest tree of the candidates, so the
  old-Buildroot workarounds listed under FunKey-OS will apply again.
- **Configs:** 24 board defconfigs.
- **Measured:** `raspberrypi3_defconfig` has 171 packages (arm, external glibc toolchain, tar rootfs,
  Raspberry Pi kernel from a commit tarball).
- **Activity:** last push 2025-02-14, 8,215 stars. GitHub does not mark it archived, but the README
  says the maintainer can no longer be involved and is looking for a successor. My earlier
  "archived" was wrong; "unmaintained" is accurate.
- **What it adds:** a Python-heavy image on an old Buildroot.

### Batocera

[`batocera-linux/batocera.linux`](https://github.com/batocera-linux/batocera.linux).

- **Buildroot:** the `batocera-linux/buildroot` fork as a submodule at `4236c4b`, reporting
  `2026.05-git`.
- **Tree:** 661 package directories in the external tree, against about 2,900 in upstream
  Buildroot. 40 board files under `configs/` (Raspberry Pi, Rockchip, Allwinner, StarFive,
  Qualcomm, x86_64 and others). Driven by a top-level Makefile and a Docker builder, with a ccache
  directory inside the project tree.
- **Activity:** pushed 2026-09-20, 3,221 stars.
- **What it adds:** the largest package set of any candidate: Qt, SDL, Python and emulator cores.
  Expect the long tail of hidden references that superduperbird produced, at several times the scale.
- **Package count:** not measured. Do this after the smaller candidates.

### Knulli

[`knulli-cfw/distribution`](https://github.com/knulli-cfw/distribution), a Batocera derivative for
handhelds.

- **Buildroot:** the `knulli-cfw/buildroot` fork at `37060ae`, reporting 2024.11.
- **Tree:** 586 package directories; 12 board files.
- **Activity:** GitHub marks the repository archived; last push 2026-06-16, 1,026 stars. It may
  have moved; I did not check.
- **What it adds:** nothing that Batocera does not. Skip it.
