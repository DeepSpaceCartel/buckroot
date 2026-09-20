#!/usr/bin/env python3
"""Extract the values of a few Kconfig symbols from .config into a small JSON file.

  native_config.py --dot-config .config --symbols BR2_A BR2_B --out cfg.json

A native package declares exactly which symbols it reads. The output holds each symbol's
value as `make` would see it (the text after `=`, quotes included; "" when unset), sorted
and deterministic, so a change to any OTHER symbol leaves the file, and therefore the
package's action key, untouched. That is a much narrower interface than the per-package
`.config` slice the wrapped actions get.
"""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dot-config", required=True)
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    values = {s: "" for s in args.symbols}
    for line in Path(args.dot_config).read_text().splitlines():
        if line.startswith("BR2_") and "=" in line:
            k, v = line.split("=", 1)
            if k in values:
                values[k] = v
    Path(args.out).write_text(json.dumps(values, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
