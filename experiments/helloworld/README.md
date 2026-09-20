# helloworld

The original experiment: a minimal Buildroot 2025.02.18 image (aarch64, musl, Bootlin external
toolchain, one local package `hello`) used to develop the Buck2 instrumentation in
`../../toolkit/`. 29 packages, 61 Buck2 actions.

```
scripts/br2 setup && scripts/br2 extract && scripts/br2 golden     # once
scripts/br2 matrix                                                # the 8 build configurations
python3 tests/test-tier0.py                                       # QEMU boot test (uses a Buck2-built rootfs via TIER0_ROOTFS)
```

## Results: 2 variants x 4 modes (4 cores, 7.9 GB, Buildbarn worker on the same machine)

`wrapped`: every package runs Buildroot's own `make <pkg>` in a Buck2 action.
`native`: the 12 packages in `project.json` (`hello`'s whole dependency closure) are built by Buck2 actions.
Cache modes run twice: cold (populates the cache) and warm (after `buck2 clean`). Every cell's rootfs
manifest is compared with the plain-`make` golden. A per-cell salt in the action environment makes a
cold run really cold (Buildbarn's local storage ignores instance names).

| variant | mode | run | ok | seconds | commands | cached | remote | local | manifest |
|---|---|---|---|---|---|---|---|---|---|
| wrapped | local | cold | True | 338.0 | 61 | 0 | 0 | 61 | IDENTICAL |
| wrapped | local-cache | cold | True | 363.8 | 61 | 0 | 0 | 61 | IDENTICAL |
| wrapped | local-cache | warm | True | 8.5 | 61 | 61 | 0 | 0 | IDENTICAL |
| wrapped | remote | cold | True | 363.4 | 61 | 0 | 61 | 0 | IDENTICAL |
| wrapped | remote-cache | cold | True | 416.8 | 61 | 0 | 61 | 0 | IDENTICAL |
| wrapped | remote-cache | warm | True | 9.0 | 61 | 61 | 0 | 0 | IDENTICAL |
| native | local | cold | True | 346.0 | 56 | 0 | 0 | 56 | IDENTICAL |
| native | local-cache | cold | True | 355.2 | 56 | 0 | 0 | 56 | IDENTICAL |
| native | local-cache | warm | True | 23.2 | 56 | 55 | 0 | 1 | IDENTICAL |
| native | remote | cold | True | 354.9 | 56 | 0 | 56 | 0 | IDENTICAL |
| native | remote-cache | cold | True | 317.3 | 56 | 0 | 56 | 0 | IDENTICAL |
| native | remote-cache | warm | True | 11.9 | 56 | 56 | 0 | 0 | IDENTICAL |

Reading it: the build is dominated by compiling upstream tarballs (busybox, e2fsprogs, util-linux...),
which are still `make` in both variants, so `native` saves 4-5 actions of 61 and little wall time here.
Warm cache rebuilds take 8-23 s for the whole graph. Remote execution on the same 4 cores costs about
what local does (no extra hardware), and the cold cache modes cost 5-15 % for uploading results.
