#!/usr/bin/env python3
"""How much CPU and memory did the remote actions use?  Reads Buildbarn's action results, not Buck2's log.

  scripts/br2-usage.py --log buck-out/v2/log/*_build_*_events.pb.zst          # every remote action of those builds
  scripts/br2-usage.py --digest HASH:SIZE [--digest ...]                      # specific actions
  scripts/br2-usage.py --log ... --top 15 --min-wall 60                       # the long ones only
  scripts/br2-usage.py --log ... --json > usage.json                          # raw rows, for jq or a spreadsheet

Buck2's own `execution_stats` are empty for remote actions (memory_peak 0, no CPU counters). The worker records
the real numbers in the ActionResult it stores in the action cache: `buildbarn.resourceusage.POSIXResourceUsage`
(user and system CPU time, ru_maxrss, faults, context switches, and `termination_signal`, "KILL" for an OOM kill)
in `execution_metadata.auxiliary_metadata`. So a result exists only when the run stored it (`remote-cache` mode),
and it is looked up under the run's REAPI instance name (`instance_name` in .buckconfig).

Needs: grpcurl on PATH (or --grpcurl), the Buildbarn frontend reachable (`kubectl -n buildbarn port-forward
svc/frontend 8980:8980`), and for --log a Buck2 binary (default tools/buck2 in the current directory).
Peak memory is ru_maxrss: the largest single process of the action, not the sum over parallel `make` jobs.
"""
import argparse
import base64
import collections
import json
import re
import shutil
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

AC_GET = "build.bazel.remote.execution.v2.ActionCache/GetActionResult"
BUCKETS = ((0, 5), (5, 20), (20, 60), (60, 300), (300, float("inf")))


def varint(b, i):
    n = shift = 0
    while True:
        c = b[i]
        i += 1
        n |= (c & 0x7F) << shift
        shift += 7
        if not c & 0x80:
            return n, i


def wire_fields(b):
    """Protobuf wire format -> {field number: value}; enough for POSIXResourceUsage (varints and length-delimited)."""
    i, out = 0, {}
    while i < len(b):
        key, i = varint(b, i)
        num, wt = key >> 3, key & 7
        if wt == 0:
            val, i = varint(b, i)
        elif wt == 2:
            n, i = varint(b, i)
            val, i = b[i:i + n], i + n
        elif wt == 1:
            val, i = b[i:i + 8], i + 8
        elif wt == 5:
            val, i = b[i:i + 4], i + 4
        else:
            raise ValueError(f"unsupported wire type {wt}")
        out[num] = val
    return out


def seconds(duration):
    d = wire_fields(duration)
    return d.get(1, 0) + d.get(2, 0) / 1e9


def digests_from_logs(logs, buck2):
    """(digest, category, identifier) of every remote command in Buck2 event logs, deduplicated."""
    seen = {}
    for log in logs:
        out = subprocess.run([buck2, "log", "show", log], capture_output=True, text=True, check=True).stdout
        for line in out.splitlines():
            if '"RemoteCommand"' not in line or '"SpanEnd"' not in line:
                continue
            try:
                action = json.loads(line)["Event"]["data"]["SpanEnd"]["data"]["ActionExecution"]
            except (KeyError, ValueError):
                continue
            for cmd in action.get("commands", []):
                rc = cmd["details"]["command_kind"]["command"].get("RemoteCommand")
                if rc:
                    seen.setdefault(rc["action_digest"], (action["name"]["category"], action["name"]["identifier"]))
    return [(d, *v) for d, v in seen.items()]


def lookup(args, item):
    digest, category, ident = item
    h, size = digest.split(":")
    req = json.dumps({"instance_name": args.instance, "action_digest": {"hash": h, "size_bytes": int(size)}})
    p = subprocess.run([args.grpcurl, "-plaintext", "-d", req, args.endpoint, AC_GET], capture_output=True, text=True)
    try:
        meta = json.loads(p.stdout)["executionMetadata"]
    except (ValueError, KeyError):
        return None                       # not in the action cache (NotFound), or the call failed
    wall = float(meta["virtualExecutionDuration"].rstrip("s"))
    for aux in meta.get("auxiliaryMetadata", []):
        if aux["@type"].endswith("buildbarn.resourceusage.POSIXResourceUsage"):
            u = wire_fields(base64.b64decode(aux["@value"]))
            cpu = seconds(u[1]) + seconds(u[2]) if 1 in u and 2 in u else 0.0
            return {
                "digest": digest, "category": category, "id": ident, "worker": meta.get("worker", ""),
                "wall_s": wall, "cpu_s": cpu, "cores": cpu / max(wall, 0.001),
                "max_rss_gib": u.get(3, 0) / 2**30, "major_faults": u.get(8, 0),
                "termination_signal": u.get(17, b"").decode(),
            }
    return None


def pct(values, p):
    v = sorted(values)
    return v[min(len(v) - 1, int(len(v) * p))]


def report(rows, top, total):
    wall = sum(r["wall_s"] for r in rows)
    cpu = sum(r["cpu_s"] for r in rows)
    print(f"{len(rows)} of {total} actions have a stored result | wall {wall / 3600:.2f} h | cpu {cpu / 3600:.2f} h | "
          f"average {cpu / wall:.2f} cores while running")
    print(f"\n{'wall time':>12} {'actions':>8} {'% of wall':>10} {'avg cores':>10} {'p90 cores':>10} {'max RSS GiB':>12}")
    for lo, hi in BUCKETS:
        rs = [r for r in rows if lo <= r["wall_s"] < hi]
        if rs:
            w = sum(r["wall_s"] for r in rs)
            label = f"{lo}-{'inf' if hi == float('inf') else hi} s"
            print(f"{label:>12} {len(rs):>8} {100 * w / wall:>10.1f} {sum(r['cpu_s'] for r in rs) / w:>10.2f} "
                  f"{pct([r['cores'] for r in rs], .9):>10.2f} {max(r['max_rss_gib'] for r in rs):>12.2f}")
    killed = [r for r in rows if r["termination_signal"]]
    print(f"\nactions that ended on a signal: {len(killed)}" + ("  (KILL = the OOM killer or a kill)" if killed else ""))
    print(f"\nlongest {top}:")
    print(f"{'id':32} {'category':14} {'wall s':>8} {'cores':>6} {'RSS GiB':>8} {'signal':>7}")
    for r in sorted(rows, key=lambda r: -r["wall_s"])[:top]:
        print(f"{r['id'][:32]:32} {r['category'][:14]:14} {r['wall_s']:>8.1f} {r['cores']:>6.2f} "
              f"{r['max_rss_gib']:>8.2f} {r['termination_signal']:>7}")


def default_instance():
    try:
        m = re.search(r"^\s*instance_name\s*=\s*(\S+)", open(".buckconfig").read(), re.M)
        return m.group(1) if m else None
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", nargs="+", default=[], help="Buck2 event logs (*_events.pb.zst) to take remote action digests from")
    ap.add_argument("--digest", action="append", default=[], help="an action digest HASH:SIZE (repeatable)")
    ap.add_argument("--instance", default=default_instance(), help="REAPI instance name (default: instance_name in ./.buckconfig)")
    ap.add_argument("--endpoint", default="localhost:8980", help="Buildbarn frontend (default localhost:8980)")
    ap.add_argument("--grpcurl", default=shutil.which("grpcurl"), help="path to grpcurl")
    ap.add_argument("--buck2", default="tools/buck2", help="Buck2 binary used to read --log files")
    ap.add_argument("--top", type=int, default=10, help="rows in the longest-actions table")
    ap.add_argument("--min-wall", type=float, default=0, help="ignore actions that ran shorter than this many seconds")
    ap.add_argument("--json", action="store_true", help="print one JSON row per action instead of the report")
    args = ap.parse_args()
    if not args.grpcurl:
        sys.exit("grpcurl not found: see docs/guides/action-resource-usage.md, step 1")
    if args.instance is None:
        sys.exit("no instance name: pass --instance NAME (it is instance_name in the project's .buckconfig)")
    if not args.log and not args.digest:
        ap.error("give --log or --digest")

    items = digests_from_logs(args.log, args.buck2) if args.log else []
    items += [(d, "", d[:12]) for d in args.digest]
    with ThreadPoolExecutor(8) as pool:
        rows = [r for r in pool.map(lambda it: lookup(args, it), items) if r and r["wall_s"] >= args.min_wall]
    if not rows:
        sys.exit(f"no stored results found for {len(items)} actions under instance '{args.instance}' "
                 "(is the frontend reachable, and was the run in remote-cache mode?)")
    if args.json:
        json.dump(rows, sys.stdout, indent=1)
    else:
        report(rows, args.top, len(items))


if __name__ == "__main__":
    main()
