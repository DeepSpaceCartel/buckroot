# buck2-toy

The three-target Buck2 project used in the walkthrough's "Buck2 from scratch" page. It needs a `buck2` binary
(any `experiments/<name>/tools/buck2` after `scripts/br2 setup` will do) and nothing else:

```console
$ cd examples/buck2-toy
$ ../../experiments/helloworld/tools/buck2 build //:banner --show-output
```
