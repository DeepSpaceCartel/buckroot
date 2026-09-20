<title>Package output sizes</title>

# Package output sizes

How big are the artifacts the [wrapped](../walkthrough/wrapped.md) variant stores in the cache, and where do the bytes come from?
Measured on the Car Thing project (98 packages) during a wrapped `local-cache` run. This page reports what was measured; the ideas it
motivates are on [Status and roadmap](../project/status.md#directory-tree-package-outputs).

## What was measured

For every package action, the size of its output tarball and the sizes of the tarballs of its dependency closure (which the action must
unpack before it can run `make`).

| | |
|---|---|
| Packages | 98 |
| Total distinct output | 1.11 GB |
| of which `host-rust-bin` (a prebuilt Rust toolchain) | 751 MB (68 %) |
| All other 97 packages together | about 360 MB |
| Packages with an output under 1 MB | 24 |
| Between 1 and 5 MB | 44 |
| Between 5 and 9 MB | 14 |
| Between 9 and 13 MB | 15 |
| Sum, over all 98 actions, of the dependency tarballs each must unpack | **5.0 GB** |

## What it shows

**The outputs are small; the big one is a payload, not waste.** Ninety-seven of the 98 packages produce between a few kilobytes and
about 12 MB. The one exception, `host-rust-bin`, is exactly the prebuilt Rust distribution it installs (LLVM, the compiler driver, cargo,
the standard library for two targets, sanitizer runtimes), of which about 30 MB is repeated content.

**The input side is about four and a half times the output side.** Every action starts by unpacking the tarballs of *all* of its
dependencies, transitively. The largest closures are the Mesa-related packages (`libgbm`, `libegl`, `libgles`, `mesa3d`, `libdrm`,
`libinput`) at 190 to 223 MB and 50 to 58 packages each. Across the 98 actions that is 5.0 GB unpacked, to produce 1.11 GB of distinct
output: the same tarballs are read and unpacked again for every package that depends on them.

## What is not explained

Fifteen packages have outputs of 9 to 13 MB, and the three virtual Mesa providers (`libgles`, `libegl`, `libgbm`) have *identical* outputs
of 4.44 MB each, with `linux` at 4.49 MB. Ordinary host packages that depend on little (`host-gawk`, `host-zstd`, `host-autoconf-archive`)
are 3 MB or less and contain only their own files. So something sizeable is common to packages with a large closure.

The likeliest cause is Buildroot rewriting files it inherited from dependencies (it edits text files that contain paths, such as
`.pc`, `.la` and `*-config` files, after merging the trees), which breaks the hard links that the delta detection uses to tell
"inherited" from "added". This is a hypothesis: the tarballs were not inspected, because the size snapshot recorded sizes only, and
the build directory that held them is cleaned before each measured cell. It will be tested when the machine is idle, by unpacking
the outputs of a Mesa provider and of `linux` and listing what they contain.

If the hypothesis holds, the fix is cheap (do not ship rewritten inherited files; they are a function of the dependency set and can be
recomputed when the trees are overlaid), and it would shrink most target-package outputs.

## How this was measured, and its limits

- The sizes come from a snapshot of `buck-out` taken every eight minutes during the cell, keeping the snapshot with the most packages
  (all 98 in the final one). Sizes are of uncompressed tarballs.
- One project, one configuration, one machine. `helloworld` (a much smaller closure) shows the same shape: everything under 1 MB except
  the 379 MB toolchain.
- The cache traffic (bytes uploaded and downloaded per cell) has not been recorded yet; output size is only a proxy for it.
