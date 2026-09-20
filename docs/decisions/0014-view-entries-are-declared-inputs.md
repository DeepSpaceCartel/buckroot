<title>ADR-0014</title>

# ADR-0014: Every view entry is a declared input, and remote execution proves it

Status: accepted
Date: 2026-09-20

## Context

A package action's [view](../concepts/views-and-slices.md#views) lists the files and directories it may read. Buck2 must also be *told*
those files are inputs, or a remote worker will not have them. Locally the difference is invisible: the whole checkout is on disk, so an
undeclared file is still readable, and the action key silently ignores it (an unsound cache hit waiting to happen).

The Car Thing's second wrapped remote build failed 100 minutes in, on `util-linux-libs`: `make: *** No rule to make target
'util-linux-libs'`. Two defects combined:

1. **The declared path was wrong.** Files that one package directory needs from another (`package/util-linux/util-linux.mk` for
   `util-linux-libs`) were declared through generated `export_file` targets. In Buck2's default mode that *copies* the file to
   `buck-out/.../file.util-linux.mk`, so the remote input root held the copy there and nothing at the source path the view expects. Only
   `util-linux.hash` happened to be present at its real path.
2. **A missing view entry was silently replaced by an empty file.** `br2-ns.sh` mounted an empty stand-in, `make` read an empty
   `util-linux.mk`, and the failure surfaced as an unrelated `make` error.

Every earlier remote run (`helloworld`) had passed, because its packages have no cross-directory `links`.

## Decision

- Generated `export_file` targets use `mode = "reference"`: the artifact is the source file itself, at its real path, in local and remote
  input roots alike.
- `br2-ns.sh` treats a missing view entry as an error (`view entry missing: <entry>`, exit 97), never an empty mount.
- Each `br2_package` has a `[viewcheck]` sub-target: an action with the same views and the same declared inputs as the package action, but
  no dependency outputs and no `make`, that only enters the namespace. `br2 viewcheck --mode remote` builds it for every package on the
  worker. On the Car Thing that is 98 actions in about 4.5 minutes, and it reproduces the original failure in seconds when the old export
  mode is restored.

## Consequences

- **Easier**: this class of failure is found in minutes, before the multi-hour remote build, with a message that names the missing entry.
  Adding a project should include `br2 viewcheck --mode remote`.
- **Easier**: the enforced view and the declared inputs are now checked against each other, where before they were merely written from
  the same list.
- **Harder**: the change alters the inputs of every package that has `links`, so cached results from before it (the local cells of the same
  matrix) are not reused; the results record which toolkit version each cell ran with.
- **Not covered**: the check enters the namespace but does not run the build, so a file read *outside* the view, or by a step other than
  the view setup, is not found by it. The full remote build remains the final test.
