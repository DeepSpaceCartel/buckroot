# Verification

## `mkdocs build --strict` is the whole point

```bash
python3 -m venv .venv-docs && . .venv-docs/bin/activate
pip install -r docs/requirements.txt
mkdocs build --strict
```

Without `--strict`, MkDocs *warns* about a broken internal link or a
missing heading anchor and still produces a site — exactly the failure
mode this whole skill exists to prevent gets silently ignored by
default. `--strict` turns those warnings into a nonzero exit code. Run
it, not the plain `mkdocs build`, in CI and locally.

What it actually catches:
- A link to a page that doesn't exist (a typo'd path, a page that got
  moved/renamed without updating its inbound links).
- A link to `#some-anchor` on a real page where that heading doesn't
  exist (or doesn't anymore — anchors are auto-generated from headings,
  so **renaming a heading silently breaks every link into it** unless
  strict mode catches it).

What it does *not* catch:
- A fact that's wrong but not a broken link (an example that no longer
  matches real behavior — see [`writing.md`](writing.md) on keeping
  examples real).
- A page that exists but isn't wired into `nav:` — that's an `INFO`-level
  message, not an error, and deliberately so (see
  [`structure.md`](structure.md)'s note on non-public content). Don't
  chase these to zero if some are intentional; do check each one is
  actually intentional.

## When to run it

Not just once at the end. Run it immediately after:
- Renaming any heading (anchor changes, every inbound link to it is now
  suspect).
- Moving or renaming a file (every relative link *from* or *to* it is
  now suspect).
- Restructuring `nav:` or folder layout (relative-path depth changes
  everywhere).

Catching this immediately after the edit that caused it is cheap;
finding out at the end of a large restructure which of a dozen edits
broke a link is not.

## Anchor slugs: know the rule before you rename a heading

A heading becomes its anchor by lowercasing, replacing spaces with
hyphens, and stripping punctuation — `## REST Endpoint` becomes
`#rest-endpoint`, `## A Service can't route to a Pod` becomes
`#a-service-cant-route-to-a-pod`. Renaming a heading for wording reasons
is exactly the kind of low-drama edit that quietly breaks links without
`--strict` catching it for you at edit time — it only catches it at
build time, so still run the build.

## Wire it into CI, not just local habit

A GitHub Actions (or equivalent) job that runs `mkdocs build --strict`
on every PR touching `docs/**` (or the whole repo, if docs changes are
common) turns "did I break a link" from a thing a human has to remember
into a thing that fails the PR automatically. Pair it with a separate
deploy job (`mkdocs gh-deploy` or a Pages workflow) that only runs on
merge to the default branch — validation on every PR, publish only on
merge.

## Clean up local build artifacts

`mkdocs build` writes a `site/` directory; gitignore it. A stray local
venv used just to run the strict-build check (`.venv-docs/` or similar)
should be gitignored or removed after use — it's local tooling, not
project state.
