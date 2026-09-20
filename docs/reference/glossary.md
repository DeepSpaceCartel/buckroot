<title>Glossary</title>

# Glossary

Terms as buckroot uses them. Where Buildroot and Buck2 use the same word for different things, both are listed.

| Term | Meaning |
|---|---|
| **action** | one command Buck2 runs with declared inputs and outputs; a package action runs `make <pkg>` in a view |
| **action key** | the digest of an action's command, declared inputs and declared environment; equal keys mean a reusable result |
| **artifact** | an action's output: for a package, one tarball with its `per-package/<pkg>/{host,target}` tree and stamps |
| **auto.conf** | the file Buildroot's `prepare` step reads to skip Kconfig; each config slice ships one |
| **cache salt** | a string added to every action's environment so a measured cell misses the cache once; see [ADR-0010](../decisions/0010-cache-salt-per-cell.md) |
| **cell (Buck2)** | a root of Buck2 rules and targets (`root`, `prelude`); unrelated to the matrix |
| **cell (matrix)** | one variant x mode combination in a results table, run cold and (for cache modes) warm |
| **closure** | a package's dependencies, direct and transitive; its view contains their directories |
| **cold / warm** | a run that finds nothing in the cache / a run after `buck2 clean` that can be served from it |
| **delta** | what a package added to `host/` and `target/`, as opposed to the complete merged tree |
| **early cutoff** | Buck2 stops rerunning downstream actions when an action reruns but produces identical output |
| **extra view** | directories a package's `.mk` reads without depending on them; declared in `extra_view` |
| **golden** | the plain-`make` reference build a Buck2 result is compared with |
| **heavy** | a package that gets a weight so it runs alone |
| **manifest** | the JSON list of every path in an image with type, mode, owner, link target, size and hash |
| **native** | a package built by Buck2 actions instead of `make <pkg>`; see [Wrapped and native](../concepts/wrapped-and-native.md) |
| **owners** | the map from each `BR2_*` symbol to the directories that declare it (`//br2/generated:owners`) |
| **PPD** | Buildroot's per-package directories (`BR2_PER_PACKAGE_DIRECTORIES`): one output tree per package |
| **slice** | the part of `.config` a package can see; see [Views and config slices](../concepts/views-and-slices.md) |
| **stamp** | a `.stamp_*` file by which Buildroot's `make` knows a package step is done |
| **strict / dev** | whether the toolkit's scripts are action inputs; see [ADR-0009](../decisions/0009-dev-mode-vs-strict.md) |
| **target tuple** | the toolchain's name (`aarch64-buildroot-linux-gnu`), which names the sysroot directory |
| **variant** | `wrapped` or `native` |
| **view** | the allow-list of directories a package action can see inside its mount namespace |
| **virtual package** | a package name that several providers implement (`libgles`, `skeleton`); chosen by `BR2_PACKAGE_PROVIDES_*` |
| **weight** | the number of local CPU slots an action occupies |
| **wrapped** | a package built by Buildroot's own `make <pkg>` inside a Buck2 action |
