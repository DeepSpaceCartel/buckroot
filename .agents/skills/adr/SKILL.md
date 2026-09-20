---
name: adr
description: How to write and maintain Architecture Decision Records (ADRs, https://adr.github.io/) - project-agnostic. Covers the numbered-file convention (docs/decisions/NNNN-title.md), Michael Nygard's original Status/Context/Decision/Consequences template, when a decision is worth recording, and how to supersede an old ADR instead of editing it. Use when a non-trivial architectural decision is about to be made (or was already made without a record), or when reviewing whether a design choice needs one.
---

# Architecture Decision Records (ADRs)

An ADR captures **one** architectural decision, the context
that led to it, and its consequences — so six months later,
nobody has to reconstruct "why did we do it this way?" from git blame
and Slack archaeology. The collection of ADRs in a project is its
decision log. See [adr.github.io](https://adr.github.io/) for the
broader landscape this pattern comes from.

## File layout

```
docs/decisions/
  0001-use-postgres.md
  0002-eventual-consistency.md
  0003-no-runtime-reflection.md
```
- Zero-padded, sequential, **never reused** — even a rejected or
  superseded ADR keeps its number forever, so a reference to
  "ADR-0007" always points at the same file.
- One decision per file — don't bundle "we chose Postgres and also
  decided on eventual consistency" into one ADR; they're two
  independently-referenceable decisions.

## The template (Michael Nygard's original shape)

```markdown
# ADR-0003: No runtime reflection

Status: accepted
Date: 2026-08-14

## Context

What situation, constraint, or forces made this decision
necessary? State the problem plainly enough that someone with none of
today's context can follow the reasoning - not just "we needed to pick
a library."

## Decision

The decision, stated as an active commitment - "We will use
X" - not a survey of the options considered. If alternatives were
seriously evaluated and rejected, a short "Alternatives considered"
subsection is worth including, with the reason each one lost.

## Consequences

What becomes easier, what becomes harder, and what new constraint
or risk this decision introduces - the honest trade-offs, not just the
upside. A decision with no downside worth naming rarely needed an
ADR in the first place.
```

## Status values

| Status | Means |
|---|---|
| `proposed` | Under discussion, not yet acted on |
| `accepted` | The current decision |
| `deprecated` | No longer recommended, but not yet fully replaced |
| `superseded by ADR-NNNN` | A later ADR replaced this one - link forward *and* have the newer ADR link back |

## Superseding, not editing

An accepted ADR is a historical record of a decision made with the
information available *at that time* — once circumstances change,
write a **new** ADR that supersedes it, rather than rewriting the old
one's `Decision`/`Consequences` in place. Set the old ADR's `Status` to
`superseded by ADR-0012` and have the new one's own text reference which
ADR it replaces and why. Editing history away defeats the purpose of
keeping one.

## When a decision is worth an ADR

Worth one: choosing a database, a cross-cutting architectural
pattern (sync vs. async, monolith vs. services), dropping support for
something users depend on, a security-relevant trade-off. Not
worth one: a variable name, which linter config to use, anything easily
reversible with no downstream cost — if reverting it tomorrow
would cost nothing, it doesn't need a permanent record.

## Referencing an ADR

Link to it by number from the code/commit/PR that implements the
decision (`// see ADR-0003`), and from any other ADR whose own decision
depended on it — the payoff of numbering is exactly this: a stable,
greppable reference that outlives which file happens to be open.
