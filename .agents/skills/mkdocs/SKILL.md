---
name: mkdocs
description: How to build a genuinely good documentation site with MkDocs + Material for MkDocs - project-agnostic (not specific to any one app/service). Covers site structure and nav design, mkdocs.yml anatomy, Material components (tabs, admonitions, grid cards, abbreviations), writing principles that keep docs from rotting, and the strict-build verification discipline that catches broken links before a reader does. Use when creating a new docs site, restructuring an existing one, or reviewing documentation for quality.
---

# MkDocs

How to build a documentation site people actually trust — with MkDocs
and the Material for MkDocs theme. Not tied to any one project; these
are the patterns and failure modes that show up building **any**
app/service's docs, distilled from doing it for real.

## The core idea

A docs site rots the moment it says something that isn't true anymore.
Everything here optimizes for one thing: making that lie *impossible to
miss*, not just possible to avoid.
- Structure the site so a fact lives in exactly one place
  ([`references/structure.md`](references/structure.md)).
- Write examples that are real and runnable, not invented-for-the-docs
  pseudocode ([`references/writing.md`](references/writing.md)).
- Use the theme's components to say the right thing in the right shape —
  a warning looks like a warning, a variant looks like a tab, not
  another wall of prose
  ([`references/material-components.md`](references/material-components.md)).
- Run a strict build after every change that touches a link or a
  heading, so a broken cross-reference fails loud in CI instead of
  quietly in front of a reader
  ([`references/verification.md`](references/verification.md)).

## Where to look

| Reference | Covers |
|---|---|
| [`references/structure.md`](references/structure.md) | Folder layout, `nav:` design, `mkdocs.yml`'s site-level settings, `requirements.txt` pinning |
| [`references/writing.md`](references/writing.md) | What makes a page worth reading: real examples, one source of truth, audience-shaped organization, the quick-start test |
| [`references/material-components.md`](references/material-components.md) | Tabs, admonitions, grid cards, abbreviations, mermaid diagrams, code annotations — and when each one is the right tool |
| [`references/verification.md`](references/verification.md) | `mkdocs build --strict`, what it catches and what it doesn't, when to run it, wiring it into CI |

## Quick orientation

```
docs/
  index.md                    # landing page — the site's own quick start
  <audience-group>/
    <page>.md
mkdocs.yml                     # site config, theme, nav
requirements.txt                # pinned mkdocs + mkdocs-material versions
```

`nav:` in `mkdocs.yml` and the folder layout under `docs/` should mirror
each other — a reader (or a contributor adding a page) should be able to
predict one from the other. See
[`references/structure.md`](references/structure.md) for how to group
pages by audience question ("how does this work" vs. "look up this
detail" vs. "how do I operate this") rather than by implementation area.
