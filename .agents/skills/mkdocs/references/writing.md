# Writing principles

## Every example is real, or it's a liability

An invented code snippet is a promise the docs make on the system's
behalf, unverified. It drifts the moment the API changes, and
nothing forces anyone to notice. Prefer embedding an actual example from
the codebase — a config file, a test scenario, a
CLI transcript — over writing one from scratch for the docs. When you
do embed one:

- **Quote it verbatim**, don't "clean it up for readability." A reader
  who copies it should get something that actually works.
- **Name the source** ("this is the complete
  `tests/quickstart_test.py` — nothing here is trimmed for the docs")
  so a skeptical reader can go verify it themselves, and so a future
  editor knows there's a file to keep in sync.
- When the source example changes, the doc's embedded copy has to change
  with it in the same edit — this doesn't happen automatically, so flag
  it as a linked pair when you first create the embed (a comment in the
  source file pointing at the doc section that quotes it is cheap
  insurance).

## One fact, one home

If two pages both explain what a term means or how a mechanism works,
one of them is already stale and you don't know which. Pick the
authoritative page for each concept, explain it there in full, and
*link* to it from everywhere else instead of re-explaining. A reference
page can use a term without re-deriving it — that's what the concepts
page is for.

## Terminology: match the reader's mental model, not the source code's

Prose describing what something *is* or *does* should read like a
sentence a knowledgeable person would actually say, not a
concatenated-identifier stand-in for it (`the Chart's dependencies`, not
`the HelmChart.dependencies`) — reserve the exact code-identifier
spelling for genuine code references (a function name, a class, a
literal command). When a project has both a user-facing vocabulary and
an internal implementation vocabulary for the same idea, decide
explicitly which one prose uses and hold the line consistently; don't
let the two bleed into each other page by page.

## Write the quick start as if the reader already has something to test

The strongest quick start isn't "install the tool, run `--help`" — it's
"here's the exact, complete flow for the most common task,
narrated as if you already had a system of your own to point it at."
Concretely: frame it in first person around a plausible scenario
("say you just built X and want to prove it works"), use one of the
project's own fixtures as the stand-in for the reader's system, and
show the *complete* artifact (the whole config file, the whole test
scenario) rather than an abbreviated fragment — trimming "for
simplicity" is exactly where invented-example drift starts.

## Don't hide navigation or table-of-contents without a good reason

Per-page front matter that hides the sidebar/TOC (`hide: navigation`,
`hide: toc`) trades a persistent cost (every other page on the
site loses its wayfinding while this one is open) for a cosmetic gain
that's rarely worth it outside a genuine full-bleed landing page. If a
page needs it, that's a deliberate design call to make once, not a
default to reach for.

## Abbreviations and jargon: define once, reference everywhere

Material's `abbr` extension (paired with a page-bottom
`*[TERM]: expansion` block) renders a term as a dotted-underline
hover-tooltip everywhere it's used on that page — cheaper than either
spelling it out every time or leaving a reader to guess:

```markdown
`BDD`-style scenarios exercise the API.

*[BDD]: Behavior-Driven Development
```

Keep one canonical list of a project's abbreviations (even if it has to
be pasted at the bottom of every page — `mkdocs` has no site-wide abbr
include) so `BDD` means the same thing on every page it appears.
