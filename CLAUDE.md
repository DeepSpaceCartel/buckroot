# buckroot

Buck2 instrumentation for Buildroot projects. `toolkit/` is the reusable part, `experiments/<name>/`
is one project each (only a `project.json` plus its golden reference and results), `docs/` is the
MkDocs Material site.

## Working rules

- One commit per finished phase (a project's golden build, a matrix milestone, a toolkit change with
  its verification); push to `origin` `main`. Conventional Commits style, imperative subject.
- Never commit build output, vendored sources, logs or `buck-out`. Experiment directories git-ignore the
  toolkit copies that `toolkit/bin/br2-sync` vendors in; edit the toolkit, then re-run `br2-sync`.
- A result is only a result if it came from a strict, clean run (`br2 build` / `br2 matrix`). `br2 dev`
  is for iteration and never produces numbers.
- Record real measurements and real failure modes in `docs/project/results.md` and the relevant
  concept page. A new design decision gets an ADR in `docs/decisions/` (see the `adr` skill).
- Docs follow the Divio split (tutorial / how-to / reference / explanation); see the `docs` and `mkdocs`
  skills. `mkdocs build --strict` must pass.
