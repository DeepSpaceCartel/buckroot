# Site structure

## Group pages by the question a reader has, not by implementation area

The strongest signal for how to split a docs site isn't "what modules
does the code have" — it's "what is the reader trying to do right now."
Three questions cover almost everything a technical doc site needs:

- **"How does this work / why is it built this way?"** — concepts,
  architecture, the design decisions and their tradeoffs. Read once,
  understood, rarely revisited.
- **"What exactly does X do / what are all the options?"** — reference.
  Read in short bursts, looked up mid-task, needs to be exhaustive and
  scannable, not narrative.
- **"How do I install/operate/contribute to this?"** — project-level,
  operational. Read once per lifecycle event (setting it up, releasing
  it, onboarding).

Mirror that grouping in both the folder layout and `nav:` — they should
predict each other:

```
docs/
  index.md                        # landing page + a real quick start
  concepts/
    getting-started.md
    architecture.md
    conventions.md
  reference/
    <topic-a>.md
    <topic-b>.md
  project/
    installing.md
    development.md
```

```yaml
nav:
  - Home: index.md
  - Concepts:
      - Getting started: concepts/getting-started.md
      - Architecture: concepts/architecture.md
      - Conventions: concepts/conventions.md
  - Reference:
      - Topic A: reference/topic-a.md
      - Topic B: reference/topic-b.md
  - Project:
      - Installing: project/installing.md
      - Development: project/development.md
```

A page that's hard to place in this grouping is usually a sign it's
trying to be two pages — a reference page that opens with three
paragraphs of "why this exists" should probably have that intro moved
to a concepts page and linked from here instead.

## `index.md`: the landing page is also the site's own quick start

The root page should let a reader who has never seen the project
understand what it is, see one complete real example of it working end
to end, and know where to go next — in that order, in under a
screen-and-a-half. Resist turning it into a table of contents; that's
what `nav:` and grid cards (see
[`material-components.md`](material-components.md)) are for.

## `mkdocs.yml`: the settings worth setting deliberately

```yaml
site_name: <Project> <one-line role>
site_description: <one sentence — this becomes the <meta> description and search-engine snippet>
site_url: https://<org>.github.io/<repo>/
repo_url: https://github.com/<org>/<repo>
repo_name: <org>/<repo>
edit_uri: edit/main/docs/          # "edit this page" links straight to GitHub's editor

theme:
  name: material
  features:
    - navigation.sections          # top-level nav groups expand as sections, not a flat list
    - navigation.tabs               # top-level groups become horizontal tabs
    - navigation.tabs.sticky
    - navigation.top                # "back to top" affordance
    - navigation.footer              # prev/next page links
    - navigation.path                 # breadcrumb trail
    - navigation.instant               # SPA-style navigation, no full reload
    - navigation.instant.progress
    - navigation.instant.prefetch
    - toc.follow                       # page's own table of contents scrolls with reading position
    - search.highlight
    - search.suggest
    - search.share
    - content.code.copy                # copy button on every code block
    - content.code.annotate            # numbered callouts inside code blocks
    - content.action.edit               # per-page "edit" link (needs edit_uri above)
  palette:
    - media: "(prefers-color-scheme: light)"
      scheme: default
      toggle: { icon: material/brightness-7, name: Switch to dark mode }
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      toggle: { icon: material/brightness-4, name: Switch to light mode }
```

`edit_uri` + `content.action.edit` together are easy to forget and cheap
to add — they turn "I found a typo" into a two-click PR instead of a
GitHub issue nobody files.

## Pin the theme version

```
mkdocs>=1.6,<2
mkdocs-material>=9.7,<10
```

Material for MkDocs ships new features and extension support
frequently, and older pinned versions silently lack markdown extensions
or theme features a page might use (an admonition type, a `pymdownx`
feature) — pin a real floor you've actually verified renders everything
the site uses, not just whatever happened to be installed when the site
was first created. Re-verify the floor (and re-pin) the same day you
adopt a new component from
[`material-components.md`](material-components.md), not after a reader
reports it's broken.

## Keep a clearly-labeled escape hatch for non-public content

If the repo has internal-only material worth keeping in version control
near the docs (design-review notes, an agent's own planning history) but
not worth publishing, put it under its own folder and leave it out of
`nav:` deliberately — `mkdocs build` only warns ("exists but not in
nav"), it doesn't fail, so this is a safe, real pattern, not a
workaround. Document the convention once (in a contributing/development
page) so it doesn't look like an oversight.
