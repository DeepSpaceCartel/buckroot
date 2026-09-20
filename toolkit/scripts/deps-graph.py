#!/usr/bin/env python3
"""Readable package dependency graph from Buck2's own query output (Graphviz DOT).

  tools/buck2 uquery 'kind(br2_package, deps(//br2/generated:rootfs))' --output-format dot \\
      | scripts/deps-graph.py [--full] > package-deps.dot

Buck2 lists every direct dependency, so most packages point at host-skeleton, toolchain,
... which buries the structure. By default an edge A -> B is dropped when A already reaches
B through another dependency (transitive reduction); --full keeps everything. Colors come
from golden/model.json: blue = host tool, green = target package, dashed = virtual package.
Render with `dot -Tsvg`, or any Graphviz viewer/WASM build. Stdlib only.
"""
import json
import re
import sys
from pathlib import Path

MODEL = Path(__file__).resolve().parent.parent / "golden" / "model.json"


def parse(dot):
    nodes, edges = set(), []
    for a, b in re.findall(r'"([^"]+)"\s*->\s*"([^"]+)"', dot):
        edges.append((a, b))
        nodes |= {a, b}
    nodes |= set(re.findall(r'^\s*"([^"]+)"\s*\[', dot, flags=re.M))
    return nodes, edges


def short(label):
    return label.rsplit(":", 1)[-1]


def reduce_edges(nodes, edges):
    succ = {n: set() for n in nodes}
    for a, b in edges:
        succ[a].add(b)
    memo = {}

    def reach(n):                                    # all descendants of n
        if n not in memo:
            memo[n] = set()
            for m in succ[n]:
                memo[n] |= {m} | reach(m)
        return memo[n]

    return [(a, b) for a, b in edges
            if not any(b in reach(c) for c in succ[a] - {b})]


def main():
    full = "--full" in sys.argv
    nodes, edges = parse(sys.stdin.read())
    if not nodes:
        sys.exit("no graph on stdin (pipe `buck2 uquery ... --output-format dot`)")
    pkgs = json.loads(MODEL.read_text())["packages"]
    kept = edges if full else reduce_edges(nodes, edges)

    out = ["digraph packages {", "  rankdir=LR;",
           '  node [shape=box, fontname="Helvetica", fontsize=11];',
           '  edge [color="#666666", arrowsize=0.7];',
           f'  labelloc=t; label="Buildroot packages as Buck2 targets: {len(nodes)} nodes, '
           f'{len(kept)} edges shown ({"all" if full else "transitively reduced"}); '
           'A -> B means A depends on B";']
    for n in sorted(nodes):
        name = short(n)
        p = pkgs.get(name, {})
        fill = "#CFE2F3" if p.get("kind") == "host" else "#D9EAD3"
        style = "filled,rounded,dashed" if p.get("virtual") else "filled,rounded"
        out.append(f'  "{name}" [style="{style}", fillcolor="{fill}"];')
    for a, b in sorted(kept):
        out.append(f'  "{short(a)}" -> "{short(b)}";')
    out.append("}")
    print("\n".join(out))


if __name__ == "__main__":
    main()
