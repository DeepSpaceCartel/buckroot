<title>Walkthrough</title>

# Walkthrough: how buckroot builds a Linux image, from scratch

This section explains buckroot to a reader who has **never used Buildroot or Buck2**. It builds one tiny project,
`helloworld`, and follows it from a pile of source files to a finished root filesystem image, stopping at every command to show
what it does and what is happening underneath. It is a tutorial: you can follow along on a Linux machine, and everything printed
on these pages is real output.

If you already know both tools, go straight to [Step 3](project.md) (how buckroot joins them) or [Step 4](wrapped.md).

## The six steps

| Step | Page | You will learn |
|---|---|---|
| 1 | [Buildroot from scratch](buildroot.md) | what Buildroot builds and how: packages, the defconfig, host and target, the output directory, stamps |
| 2 | [Buck2 from scratch](buck2.md) | what Buck2 does and why: targets, actions, the action key, caching, remote execution. Uses a three-file toy project |
| 3 | [Joining Buildroot and Buck2](project.md) | `project.json`, `br2 setup`, `br2 extract`, `br2 golden`: how a Buildroot project becomes a Buck2 graph |
| 4 | [Wrapped](wrapped.md) | build a package with Buck2 running Buildroot's own `make` inside an action; what's inside that action |
| 5 | [Stepped (design)](stepped.md) | what happens if each Buildroot step becomes its own action. Not implemented; the page says what was checked and what is a proposal |
| 6 | [Native](native.md) | build a package with Buck2 alone, no `make`; proof that the result is the same |

Steps 1 and 2 are independent of each other and of buckroot; read whichever you need. Steps 3 to 6 are one story, in order.

## What you need to follow along

- A Linux machine (x86-64) with root access or the ability to create mount namespaces, about 8 GB of RAM and 20 GB of disk.
  The steps that build things take from a few seconds to a few minutes.
- `python3`, `git`, and the usual build tools (`gcc`, `make`, `rsync`, `perl`). The full list is in the
  [Quickstart](../home/quickstart.md#prerequisites).
- A checkout of the [buckroot repository](https://github.com/DeepSpaceCartel/buckroot).

All commands run from `experiments/helloworld` unless a page says otherwise (Step 2 uses `examples/buck2-toy`). Output shown as
`$ command` followed by text is real; long lines are shortened with `...`.

## The example project

`helloworld` is a Buildroot project of the smallest useful kind: one program of its own (`hello`, a seven-line C program that prints
a greeting) plus the parts of a minimal Linux root filesystem, for a 64-bit ARM board, using a prebuilt compiler so that a full
build takes minutes rather than hours. It has 29 packages. The larger projects that buckroot is tested on (a handheld game console
firmware, Home Assistant OS) work the same way, only with more packages and longer builds; see [Projects](../project/projects.md).

## A note on the numbers

Timings on these pages were measured on a 4-core machine that was often busy with another build, so treat them as orders of
magnitude. The carefully measured tables, taken from clean runs, are on [Results](../project/results.md).

## Words you will meet

Each page explains its own terms where they first appear. If you get lost, the [glossary](../reference/glossary.md) lists them all.

[Start with Step 1: Buildroot from scratch](buildroot.md){ .md-button }
