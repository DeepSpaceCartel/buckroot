# toolkit: buckroot's Buck2 instrumentation for Buildroot projects

Everything generic lives here; an experiment directory keeps only what is specific to its project.

```
toolkit/                        the toolkit (this directory)
  br2/          Starlark rules + Python actions (one Buck2 target per Buildroot package, config slices,
                narrow input views, native package rules) and br2/native/: generic native packages
  scripts/      br2 (CLI), br2buck.py (model extraction + BUCK generation), br2-ns.sh (fixed-path mount
                namespace), fs-manifest.py, compare-pkg.py, check-narrow.py, show-inputs.py, ...
  platforms/    execution platform with remote-cache / remote-execution switches
  infra/buildbarn/   docker compose: cache + scheduler + worker (with the tool-baseline image)
  bin/br2-sync  vendor the toolkit into an experiment
  templates/    .buckconfig and root BUCK templates
experiments/<name>/             one experiment = one project
  project.json  the only project-specific input (name, defconfig, external tree, native list...)
  buildroot-src/, buildroot-external/, common/, native/, golden/, results/
```

Use it:

```
toolkit/bin/br2-sync experiments/<name>     # vendor the toolkit (scripts/, br2/, ...; git-ignored)
cd experiments/<name>
scripts/br2 setup        # buck2 binary, Buildroot tree, external tree
scripts/br2 extract      # defconfig -> golden/model.json -> BUCK files
scripts/br2 fetch        # downloads Buck2's http_file cannot express (git, sha512-only)
scripts/br2 golden       # plain `make` reference build -> golden/rootfs.manifest.json
scripts/br2 matrix       # variants {wrapped,native} x modes {local,local-cache,remote,remote-cache}
```

Documentation: <https://deepspacecartel.github.io/buckroot/> (sources in `../docs/`).
