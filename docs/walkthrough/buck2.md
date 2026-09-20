<title>Step 2: Buck2 from scratch</title>

# Step 2: Buck2 from scratch

You do not need to know Buck2 to follow this walkthrough. This page teaches what you need with a three-file toy project,
and every output shown was produced by running it. If you already know Buck2, skip to [Step 3](project.md).

## The problem Buck2 solves

You have a build made of many steps, each turning some files into other files. Some steps take seconds, some take an
hour. When you change one file, you want to redo **exactly the steps that are affected**, no more and no fewer, and you
want a colleague (or a build server) who already did a step to share the result instead of repeating it.

`make` does a version of this by comparing file modification times. That is fast, but it is easy to get wrong:
timestamps lie (a checkout, a copy, a clock difference), a step can silently read a file nobody told `make` about, and
`make` cannot share results between machines.

**Buck2** is a build system that fixes this by being strict. You tell it, for every step, **exactly which inputs it reads
and which outputs it produces**. In return it:

- rebuilds only what depends on what changed, decided by *content*, not by timestamps;
- runs independent steps in parallel;
- can store every result in a **cache** shared between machines, so a step is done once by anybody;
- can run steps on **other machines** (remote execution).

The price is the strictness: a step that reads something it did not declare is a bug Buck2 wants to find. Much of what
buckroot does is about making Buildroot's builds honest enough for that.

## The toy project

The files are in `examples/buck2-toy/`. There are three of them that matter.

`greeting.txt` is an input file:

```text
hello from a tiny buck2 project
this is the second line
```

`BUCK` says what to build. It is a file written in Starlark, a small language that looks like Python:

```python
genrule(
    name = "upper",
    srcs = ["greeting.txt"],
    out = "upper.txt",
    cmd = "tr a-z A-Z < $SRCS > $OUT",
)

genrule(
    name = "first_word",
    srcs = [":upper"],
    out = "first_word.txt",
    cmd = "head -c 5 $SRCS > $OUT",
)

genrule(
    name = "banner",
    srcs = [":first_word"],
    out = "banner.txt",
    cmd = "(echo '=== banner ==='; cat $SRCS) > $OUT",
)
```

`.buckconfig` (and a small `toolchains/BUCK`) tell Buck2 where the project's root is and where its built-in rules come
from. You do not need to read it; it is the same boilerplate in every project.

## Targets, rules and labels

Each `genrule(...)` above defines a **target**: a named thing that can be built. A target has:

- a **rule** (`genrule`): the kind of thing it is. A rule knows how to turn inputs into outputs; `genrule` means "run this
  shell command". Other rules compile C, build Python packages, and so on. buckroot defines its own rules, such as
  `br2_package`.
- **attributes** (`name`, `srcs`, `out`, `cmd`): the arguments of the rule. `srcs` is the list of inputs: files, or other
  targets (`":upper"` means "the output of the target named `upper` in this directory").
- a **label** that names it uniquely: `//:upper` means "the target `upper` in the `BUCK` file at the project root". A
  package in a subdirectory would be `//some/dir:name`.

The three targets form a **graph**: `banner` reads `first_word`, which reads `upper`, which reads `greeting.txt`.

```text
$ buck2 targets //...
root//:banner
root//:first_word
root//:upper

$ buck2 uquery 'deps(//:banner)'      # everything banner depends on
root//:upper
root//:first_word
root//:banner
```

This graph is what buckroot generates for Buildroot: one target per package, with the package's dependencies as the graph's
edges. That is the whole idea of [Step 3](project.md).

## Building: actions

Ask Buck2 to build the last target:

```text
$ buck2 build //:banner
Commands: 3 (cached: 0, remote: 0, local: 3)
BUILD SUCCEEDED
```

Buck2 walked the graph and ran three **actions**. An action is one concrete command Buck2 runs to produce an output:
here, one shell command per target. (A target can have several actions; a compile-then-link target has two.) Where is
the result?

```text
$ cat buck-out/.../banner.txt
=== banner ===
HELLO
```

All outputs live under `buck-out/`. `upper` turned the text into capitals, `first_word` kept the first five characters
(`HELLO`), and `banner` added a heading. You can ask what Buck2 will run for a target:

```text
$ buck2 aquery --output-all-attributes //:upper
category  genrule
cmd       [/usr/bin/env, bash, -e, buck-out/v2/art/root/.../__upper__/sh/genrule.sh]
```

## The key idea: the action key

For each action, Buck2 computes an **action key**: a fingerprint (a hash) of **everything that could affect the result**:
the command, the *contents* of every declared input file, the outputs of the actions it depends on, and the declared
environment. Two actions with the same key must produce the same output. That one rule is the source of all of Buck2's
behaviour. Watch it work.

**Build again without changing anything.** Every key is the same as last time, so nothing runs:

```text
$ buck2 build //:banner
BUILD SUCCEEDED                 <- no "Commands:" line: zero actions ran
```

**Edit the second line of `greeting.txt`** (`second line` becomes `SECOND LINE, edited`) and build:

```text
$ buck2 build //:banner
Commands: 2 (cached: 0, remote: 0, local: 2)
BUILD SUCCEEDED
```

Two actions ran, not three. `greeting.txt` changed, so `upper` (which reads it) had a new key and reran. Its output
changed too (it is the capitals of the whole file), so `first_word` (which reads that output) had a new key and reran.
But `first_word` keeps only five characters, and they are still `HELLO`: its output is **byte-for-byte identical** to last
time. So `banner`'s inputs are unchanged, its key is unchanged, and Buck2 does **not** run it. This is **early cutoff**:
a change stops propagating the moment it stops making a difference.

**Edit the first line** (`hello from a tiny` becomes `goodbye from a tiny`) and build:

```text
$ buck2 build //:banner
Commands: 3 (cached: 0, remote: 0, local: 3)
BUILD SUCCEEDED
```

Now `first_word` produces `GOODB`, the output differs, and `banner` reruns as well. Compare this with `make`, which would
have rebuilt everything downstream on any change to `greeting.txt`, or nothing if the timestamps said so. Buck2 decides
by looking at contents, and it is right both times. Buildroot's coarse "did this step happen once" stamps, from
[Step 1](buildroot.md#stamps-how-buildroot-knows-what-is-done), are exactly what this replaces.

## The cache

The action key is also an address. When Buck2 has run an action it can store the output under that key. The next time
*anyone* needs an action with the same key, they can fetch the stored output instead of running the command. In this toy
the commands take a millisecond, so there is nothing to gain; for a package that takes an hour to compile, a hit
turns an hour into seconds.

Where is the store? Buck2 speaks a standard protocol, the **Remote Execution API**, to a server. buckroot uses a
server called **Buildbarn** (in `toolkit/infra/buildbarn`). It has two halves:

- the **CAS** (content-addressable storage): files and directories, stored under the hash of their contents;
- the **action cache**: a map from an action key to the output it produced.

Building "with cache" means: before running an action, Buck2 asks the action cache whether that key exists; after running
one, it uploads the result. A second machine, or the same machine after `buck2 clean` wipes its local state, then
gets 100% cache hits. buckroot measures exactly that: a helloworld build that took 364 seconds cold takes 8.5 seconds
warm.

## Remote execution

The same server can also *run* actions. Instead of executing the command on your machine, Buck2 sends the action's
inputs to the server, and a **worker** there executes the command and sends the outputs back. This is useful when the
machine you have is small and the build is big, or when you want every build to happen in an identical, controlled
environment (the same compiler, the same tools).

It only works if the action is **hermetic**: it must depend on nothing except its declared inputs. A command that reads
`/home/you/.config`, or the machine's installed compiler, or the current time, will behave differently on the worker.
This is why the strictness of the first section is not pedantry: hermetic actions are what make caching correct and remote
execution possible.

The four ways buckroot builds, which you will see in every results table, are the combinations of these two features:

| Mode | Where actions run | Cache |
|---|---|---|
| `local` | your machine | none |
| `local-cache` | your machine | Buildbarn |
| `remote` | a Buildbarn worker | none |
| `remote-cache` | a Buildbarn worker | Buildbarn |

## Try it

```bash
cd examples/buck2-toy
../../experiments/helloworld/tools/buck2 build //:banner --show-output
# edit greeting.txt as above and build again after each edit; run `buck2 build //:banner` with no changes too
```

(Any `tools/buck2` from an experiment after `scripts/br2 setup` works. The toy needs nothing else.)

## The vocabulary, in one table

| Term | Meaning |
|---|---|
| **target** | a named thing you can build, defined in a `BUCK` file |
| **rule** | the kind of a target: how inputs become outputs (`genrule`, `br2_package`, ...) |
| **label** | a target's unique name: `//dir:name` |
| **action** | one concrete command Buck2 runs to produce an output |
| **action key** | the hash of an action's command, inputs and environment; equal keys mean equal results |
| **early cutoff** | if an action reruns but its output is identical, nothing downstream reruns |
| **hermetic** | depends only on declared inputs |
| **cache** | stored results, looked up by action key |
| **remote execution** | running an action on another machine |

[Continue to Step 3: Joining Buildroot and Buck2](project.md){ .md-button }
