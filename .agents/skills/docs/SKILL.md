---
name: docs
description: How to organize documentation using the Divio documentation system (https://docs.divio.com/documentation-system/) - project-agnostic. Covers the four documentation types (tutorials, how-to guides, reference, explanation), the 2x2 framework (action vs. cognition, study vs. work) that distinguishes them, and how to tell which quadrant a given page belongs in. Use when planning a docs site's structure, reviewing whether a page mixes types it shouldn't, or deciding where new content belongs.
---

# The Divio Documentation System

Most documentation is bad for the same reason: one page tries to
be a tutorial, a reference, and an explanation all at once, and ends up
serving none of those readers well. The fix
([docs.divio.com/documentation-system](https://docs.divio.com/documentation-system/))
is recognizing these are **four genuinely different jobs**, each
needing its own kind of writing — not four styles of the same thing.

## The four types

| | **Learning** | **Goal** |
|---|---|---|
| **Practical** (doing) | **Tutorial** | **How-to guide** |
| **Theoretical** (knowledge) | **Explanation** | **Reference** |

- **Tutorial** — a lesson, taken by the hand, for someone with
  zero context. Practical (they're doing something, following
  along) and learning-oriented (the point is what they come away
  knowing, not what they produce). You choose every step; a beginner
  shouldn't have to make decisions mid-tutorial.
- **How-to guide** — a recipe for someone who already knows the
  basics and has one specific goal ("how do I rotate a secret").
  Practical, but goal-oriented, not learning-oriented — it can skip
  explaining *why*, and should assume competence.
- **Reference** — dry, structured facts: every parameter, every
  return value, every config key. Theoretical (describing the system,
  not walking through an action) but work-oriented — a reader consults
  it mid-task, the way you'd look up one entry in a dictionary, not read
  it front to back.
- **Explanation** — understanding: *why* something works the way
  it does, the trade-offs behind a design, the history that led here.
  Theoretical and study-oriented — read away from the keyboard, when a
  reader wants to understand rather than act.

## The test: which need is this page serving?

Ask two questions about the reader, not the content:
1. Are they **doing** something right now, or trying to **understand**
   something?
2. Are they **learning** (a beginner, taken step by step) or pursuing a
   **goal** they already know how to approach?

The answer picks the quadrant. A page that answers "doing +
understand" at once — a how-to guide that stops to explain background
theory — is usually two pages that got merged, not one well-rounded one.

## Symptoms of mixing types

- A **tutorial** that says "for more on why this works, see the config
  reference" mid-lesson — breaks the beginner's flow; link it at the
  end, not inline.
- A **how-to guide** that starts with three paragraphs of background
  theory before the first command — the reader with a
  specific goal has to wade through explanation to find the doing.
  Frontload the steps; put the "why" in a linked Explanation page.
  Applies at the *page* level, not the *site* level - the harness's
  own `docs/index.md` links out to `concepts/`/`reference/` right after
  its Quick Start precisely so the tutorial itself stays short, not by
  omitting the deeper material altogether.
- A **reference** page with prose narrative instead of structured
  entries — makes "look up one fact fast" slower than it needs to be;
  keep reference pages scannable (tables, consistent headers per entry),
  not paragraph-driven.
- An **explanation** page that's actually a how-to in disguise (a wall
  of numbered steps with no discussion of trade-offs) — if there's
  no "why," it's not an explanation page, move the steps to a how-to.

## Applying this to a site's nav

A docs site usually needs all four, organized so a reader in one
mode doesn't have to leave it to find the next page:
```
docs/
  tutorials/      # onboarding - "get this running end to end"
  how-to/         # task-oriented recipes
  reference/      # generated or hand-maintained factual lookup
  concepts/       # explanation - the "why", design rationale
```
Not every project needs deep content in all four immediately — but
knowing which quadrant a new page belongs in, before writing it,
is what keeps a docs site from drifting into one giant page that's
trying to be everything.
