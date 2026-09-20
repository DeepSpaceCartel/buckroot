<title>Step 1: Buildroot from scratch</title>

# Step 1: Buildroot from scratch

You do not need to know Buildroot to follow this walkthrough. This page teaches what you need, using the small
example project, `helloworld`, and real output from building it. If you already know Buildroot, skim the headings and
go to [Step 2](buck2.md).

## The problem Buildroot solves

Imagine you are building a small device: a handheld game console, a router, a smart speaker. It has an ARM processor and
a few hundred megabytes of storage. You want it to run Linux. You cannot install Ubuntu on it: it is too big, it is built
for other hardware, and you do not control what is in it. What you want is a **tiny Linux system with exactly the software
your device needs** and nothing else.

A running Linux system has two big parts:

- the **kernel**: the program that talks to the hardware;
- the **root filesystem** ("rootfs"): all the other files the system uses, laid out as the familiar tree:
  `/bin` (basic commands), `/etc` (settings), `/lib` (shared libraries), `/usr/bin` (programs), and so on.

**Buildroot** builds such a system from source. You tell it what you want; it downloads the source code of every piece,
compiles it, arranges the results into a root filesystem, and packs that into an **image**: a single file you can write
to the device's storage (or, for testing, attach to an emulator).

`helloworld` builds only the root filesystem. Its image, `rootfs.ext4`, is a 60 MB filesystem containing BusyBox (a
tiny toolbox that provides `ls`, `cp`, `sh` and hundreds of other commands), the C library, some startup scripts, and one
program of our own: `/usr/bin/hello`.

## Four words you will see everywhere

**Host and target.** The *host* is the machine that runs the build: your x86-64 PC or server. The *target* is the
device the result runs on: here, a 64-bit ARM ("aarch64") computer. They are different kinds of CPU, which matters
for the next word.

**Cross-compiler.** A normal compiler produces programs for the machine it runs on. To build for the target you need a
*cross-compiler*: it runs on the host and produces aarch64 machine code. A program built by one cannot run on your PC.

```text
$ file target/usr/bin/hello
target/usr/bin/hello: ELF 64-bit LSB pie executable, ARM aarch64, version 1 (SYSV), dynamically linked,
                      interpreter /lib/ld-musl-aarch64.so.1, stripped
```

That is `hello` after the build: an ARM executable, sitting on an x86 machine, which will only run on the device (or in
an emulator).

**Toolchain.** The cross-compiler plus the things it needs to build for the target: the target's C library (here **musl**,
a small alternative to glibc) and its header files. Building a toolchain takes an hour; Buildroot can do it, or you can
give it a prebuilt one. `helloworld` uses a prebuilt toolchain from Bootlin, which is why its whole build takes minutes.

**Package.** One piece of software Buildroot knows how to build: BusyBox, `hello`, the OpenSSH server, the Linux
kernel. A package is described by a small directory of files. `helloworld` has 29 packages: `hello`, BusyBox, the
toolchain, and a number of *host* packages (tools that run on the build machine: `host-e2fsprogs` creates the filesystem
image, `host-fakeroot` lets the build set file ownership without being root).

## You describe the system in one file: the defconfig

Buildroot has hundreds of options: which CPU, which toolchain, which packages, how big the image is. You choose them
in a menu (`make menuconfig`) that saves your choices in a file named `.config`, or you keep only the *differences from the
defaults* in a short file called a **defconfig**. This is `helloworld`'s, in full:

```text
BR2_aarch64=y                                   # the target CPU is 64-bit ARM
BR2_TOOLCHAIN_EXTERNAL=y                        # use a prebuilt toolchain ...
BR2_TOOLCHAIN_EXTERNAL_BOOTLIN=y                #   ... from Bootlin ...
BR2_TOOLCHAIN_EXTERNAL_BOOTLIN_AARCH64_MUSL_STABLE=y   #   ... the aarch64 + musl one
BR2_PER_PACKAGE_DIRECTORIES=y                   # one output tree per package (explained below)
BR2_REPRODUCIBLE=y                              # same input, same output: fixed timestamps
BR2_DOWNLOAD_FORCE_CHECK_HASHES=y               # refuse a download whose checksum is not known
BR2_SYSTEM_DHCP="eth0"                          # get an IP address on the first network interface
BR2_TARGET_ROOTFS_EXT2=y                        # produce an ext2/ext4 filesystem image ...
BR2_TARGET_ROOTFS_EXT2_4=y                      #   ... in the ext4 flavour
BR2_PACKAGE_HOST_KMOD=y                         # a host tool the image step needs
BR2_PACKAGE_HELLO=y                             # and our own package
```

(The real file has no comments; they are added here.) Every name starting `BR2_` is a **config symbol**. `=y` turns a
feature on. Buildroot expands this short list into a complete `.config` of about 4,100 lines, filling in the defaults
for everything you did not mention.

## What a package looks like

A package is a directory. `helloworld`'s own package, `hello`, has two files.

**`Config.in`** adds the package to the menu, so `BR2_PACKAGE_HELLO=y` is a valid thing to write:

```text
config BR2_PACKAGE_HELLO
	bool "hello"
	help
	  Trivial hello-world C program ...
```

**`hello.mk`** is the recipe. It is a makefile that fills in variables Buildroot understands:

```make
HELLO_VERSION = 1.0                                                     # (1)
HELLO_SITE = $(BR2_EXTERNAL_BUCKROOT_HELLOWORLD_PATH)/../common/hello   # (2)
HELLO_SITE_METHOD = local                                               # (3)
HELLO_LICENSE = MIT

define HELLO_BUILD_CMDS                                                 # (4)
	$(TARGET_CC) $(TARGET_CFLAGS) -o $(@D)/hello $(@D)/hello.c
endef

define HELLO_INSTALL_TARGET_CMDS                                        # (5)
	$(INSTALL) -D -m 0755 $(@D)/hello $(TARGET_DIR)/usr/bin/hello
endef

$(eval $(generic-package))                                              # (6)
```

1. The version. It becomes part of the build directory's name, `build/hello-1.0/`.
2. **Where the source code is.** For most packages this is a web address to download a tarball from. Here it is a
   directory on disk, next to the project.
3. How to get it: `local` means "copy that directory". Other methods are downloading a file, cloning git.
4. **How to build it.** A shell command: run the cross-compiler (`$(TARGET_CC)`) with the standard flags on `hello.c`.
   `$(@D)` is the package's build directory.
5. **How to install it.** Copy the program into the target tree, `$(TARGET_DIR)`, at `/usr/bin/hello`, with mode 0755.
6. Ask Buildroot's generic machinery to turn these variables into a working package.

The source, `hello.c`, is seven lines:

```c
#include <stdio.h>

int main(void)
{
    printf("hello from buckroot helloworld\n");
    return 0;
}
```

For a real package such as BusyBox the same file has more lines and the source is a downloaded archive, but the shape is
identical: where is the source, how to build it, how to install it.

Where does this package live? `helloworld` is a **BR2_EXTERNAL tree**: Buildroot's way of keeping your own packages and
configs in a directory *outside* the Buildroot source tree, so you can upgrade Buildroot independently. The file
`external.desc` names it (`BUCKROOT_HELLOWORLD`), and `external.mk` includes every package's makefile. Almost every
real board project (a vendor's Buildroot setup) is one of these.

## The life of a package: the steps

To build a package, Buildroot walks it through fixed steps, in order:

| Step | What happens | Example |
|---|---|---|
| download | fetch the source and check its checksum | a tarball of BusyBox from busybox.net |
| extract | unpack it into `build/<pkg>-<version>/` | |
| patch | apply the patch files shipped with the package | a fix for a build error |
| configure | prepare the build | run the package's `./configure` |
| build | compile | `make` inside the package |
| install | copy results to the right places | the program into the target tree |

For `hello` (a `local` package with no `./configure`) the log of the real build reads like this:

```text
>>> hello 1.0 Syncing from source dir /mnt/external/../common/hello     # download+extract: copy the directory
>>> hello 1.0 Configuring
>>> hello 1.0 Building
/mnt/out/per-package/hello/host/bin/aarch64-linux-gcc -D_LARGEFILE_SOURCE ... -O2 -g0 -o .../hello .../hello.c
>>> hello 1.0 Installing to target
/usr/bin/install -D -m 0755 .../hello .../per-package/hello/target/usr/bin/hello
```

The compiler is `aarch64-linux-gcc`: the cross-compiler. Buildroot runs the packages in **dependency order**: a package
lists what it needs (`hello` needs the toolchain and the skeleton of the filesystem) and Buildroot builds those first.

## Where everything ends up: the output directory

Buildroot writes into one **output directory**. This is what the finished `helloworld` output looks like (real):

```text
$ ls output
build  host  images  per-package  staging  target

$ du -sh build host images per-package target
305M  build         one subdirectory per package, holding its unpacked source and its objects
395M  host          the build machine's tools: the cross-compiler, e2fsprogs, ... (plus the toolchain's sysroot)
8.7M  images        the results: rootfs.ext2 and rootfs.ext4 (a 60 MB filesystem, mostly empty space)
427M  per-package   one output tree per package (below)
4.4M  target        the root filesystem being assembled: this is what goes on the device

$ ls target
bin  dev  etc  lib  lib64  linuxrc  media  mnt  opt  proc  root  run  sbin  sys  tmp  usr  var
$ ls -la target/usr/bin/hello
-rwxr-xr-x 1 root root 5680 ... target/usr/bin/hello
```

`staging` is a link into the toolchain's sysroot: the target's libraries and headers that *other* packages compile
against. The `host` and `target` split is the same distinction as before: `host` holds what runs during the build, `target`
holds what runs on the device.

### Per-package directories

By default Buildroot has *one* `host` and *one* `target` directory that every package installs into. That is simple, but
it means a package can quietly use something a *different* package installed earlier, without saying so. With
`BR2_PER_PACKAGE_DIRECTORIES=y`, each package gets its own `per-package/<name>/host` and `per-package/<name>/target`, built
by copying in only the trees of the packages it *declared* it depends on. If `hello` forgets to declare a dependency, the
build fails instead of working by luck. buckroot turns this option on for every project, because it is what makes it
possible to build one package from only its dependencies' outputs.

### Stamps: how Buildroot knows what is done

How does `make` know not to rebuild a finished package? Each completed step leaves an empty marker file, a **stamp**:

```text
$ ls -a build/hello-1.0
.stamp_rsynced  .stamp_configured  .stamp_built  .stamp_target_installed  .stamp_installed  hello  hello.c
```

If `.stamp_built` exists, the build step is skipped. Notice what this is *not*: Buildroot does not look at whether the
source or the configuration changed. A stamp says "this step happened once", not "this step's result is still up to date".
This is the root of most of Buildroot's incremental-build surprises, and of what Buck2 will improve.

## Finishing: the rootfs and the image

When all packages are built, Buildroot does two last things:

1. **Finalize**: merge every package's `target` tree into the single `output/target`, apply your overlays and scripts
   (set the hostname, the root password, the network setup).
2. **Pack**: use a host tool (`mke2fs`, from `host-e2fsprogs`) to turn `output/target` into `images/rootfs.ext4`.

The image is a file. `scripts/fs-manifest.py` can list what is inside it: 369 entries in `helloworld`, of which one is
`/usr/bin/hello`.

## Try it

You can build the reference image yourself. From `experiments/helloworld`:

```bash
../../toolkit/bin/br2-sync .
scripts/br2 setup       # fetch Buildroot 2025.02.18 and the tools
scripts/br2 golden      # a plain Buildroot build (a few minutes), then a scan of the image
```

`br2 golden` runs Buildroot's own `make` with the options above and stores the output under
`~/.cache/br2/helloworld/golden`. You should end up with the `ls` and `du` output shown here. Do not worry about the
extra `br2` commands yet; [Step 3](project.md) explains each one.

## What Buildroot does not give you

Buildroot is good at what it does, and this project is built on it, not instead of it. But:

- **Rebuilds are coarse and stamp-based.** Change a package's source or a config option and Buildroot may rebuild
  nothing, or everything, depending on stamps, not on what actually changed.
- **Nothing is shared between machines.** Every developer and every CI job repeats the same multi-hour build. There is
  no cache of results a colleague already produced.
- **The build is mostly one process.** Buildroot can build several *parts of one package* in parallel, but it
  builds *packages* nearly one after another; the parallel top-level mode is experimental.
- **It cannot prove a build is correct.** Nothing checks that a package used only what it declared.

These are exactly what [Buck2](buck2.md) is good at. Step 2 introduces it; the rest of the walkthrough joins the two.

[Continue to Step 2: Buck2 from scratch](buck2.md){ .md-button }
