"""Prints the results of a run as tables:  python -m spike_r2.summarize 1000 5000 20000

Reads results/timings_N.json, results/mem_*_N_*.json and the state files; writes nothing.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RESULTS = Path(os.environ.get("R2_RESULT_DIR", Path(__file__).resolve().parent / "results"))


def load(name: str) -> dict:
    return json.loads((RESULTS / name).read_text())


def find(rows: list[dict], needle: str, phase: str | None = None) -> dict | None:
    for row in rows:
        if needle in row["name"] and (phase is None or row.get("phase") == phase):
            return row
    return None


def ms(row: dict | None, key: str = "median_ms") -> str:
    return "-" if row is None else f"{row[key]:,.0f}"


def table(title: str, header: list[str], rows: list[list[str]]) -> None:
    print(f"\n### {title}\n")
    print("| " + " | ".join(header) + " |")
    print("| " + " | ".join("---" for _ in header) + " |")
    for row in rows:
        print("| " + " | ".join(row) + " |")


def main(sizes: list[int]) -> None:
    data = {s: load(f"timings_{s}.json") for s in sizes}
    head = ["What", *[f"{s:,}" for s in sizes]]

    # Content facts
    rows = []
    for key, label in (("entities", "entities"), ("edges", "prototype edges"), ("stats", "stat values"),
                       ("infos", "information rows"), ("links", "copy links")):
        for repo in ("core", "bridge"):
            rows.append([f"{repo}: {label}"] + [
                f"{data[s]['facts_before_publish'][f'{repo}_rows'][key]:,}" for s in sizes])
    table("What was built (before the edits)", head, rows)

    # Publish
    rows = []
    for label, repo, mode_prefix in (
        ("publish core, first release, no baseline (private)", "core", None),
    ):
        rows.append([label] + [f"{data[s]['state']['publish_core_first_s'] * 1000:,.0f}" for s in sizes])
    for repo in ("core", "bridge"):
        for mode in ("private", "public"):
            samples = {s: [p for p in data[s]["publishes"] if p["repository"] == repo and p["mode"].startswith(mode)] for s in sizes}
            for index in range(max(len(v) for v in samples.values())):
                label = f"PUT published {repo}, {mode}, run {index + 1}"
                row = [label]
                for s in sizes:
                    v = samples[s]
                    row.append(f"{v[index]['wall_ms']:,.0f} ({v[index]['statements']} stmts)" if index < len(v) else "-")
                if any(c != "-" for c in row[1:]):
                    rows.append(row)
    table("Publish through the API (ms)", head, rows)

    # Pieces
    names = [
        "load_content", "live_rows", "digest_of", "stored_rows", "compare + detect",
        "descriptions_edited_since", "assess (all", "encode", "JSON text alone", "dumps",
        "gzip level 9", "gzip level 6", "gzip level 1",
        "gunzip + json.loads", "decode", "as a publish does it", "publish without a document",
        "SQL fetch", "read_release_content", "read_release_copies",
    ]
    for repo in ("core", "bridge"):
        rows = []
        for needle in names:
            for phase in ("private", "public"):
                cells = [find([r for r in data[s]["pieces"] if r["name"].startswith(repo)], needle, phase) for s in sizes]
                if all(c is None for c in cells):
                    continue
                rows.append([f"{needle} [{phase}]"] + [ms(c) for c in cells])
        table(f"Pieces, {repo} (median ms)", head, rows)
    rows = []
    for repo in ("core", "bridge"):
        for key in ("plain_bytes", "gzip_bytes", "files", "file_bytes"):
            cells = [find([r for r in data[s]["pieces"] if r["name"].startswith(repo)], "dumps", "public") for s in sizes]
            rows.append([f"{repo}: {key}"] + [f"{c[key]:,}" if c else "-" for c in cells])
    table("Document size", head, rows)

    for repo in ("core", "bridge"):
        for kind in ("plain", "gzip6"):
            keys: list[str] = []
            for s in sizes:
                comp = find([r for r in data[s]["pieces"] if r["name"].startswith(repo)], "composition", "public")
                keys = sorted(set(keys) | set((comp or {}).get(kind, {})))
            rows = []
            for key in keys:
                cells = []
                for s in sizes:
                    comp = find([r for r in data[s]["pieces"] if r["name"].startswith(repo)], "composition", "public")
                    cells.append(f"{comp[kind].get(key, 0):,}" if comp else "-")
                rows.append([key] + cells)
            table(f"Document composition, {repo} ({kind} bytes per top-level key)", head, rows)

    # Reads
    for mode in ("private_before_public", "public", "private"):
        names = sorted({r["name"] for s in sizes for r in data[s].get(f"reads_{mode}", [])})
        rows = []
        for needle in names:
            cells = [find(data[s].get(f"reads_{mode}", []), needle) for s in sizes]
            rows.append([needle] + [f"{ms(c)} ({c['statements']} st, first {c['first_run_ms']:,.0f})" if c else "-" for c in cells])
        table(f"Reads, {mode} (median ms)", head, rows)

    # Memory
    rows = []
    ops = sorted({p.name.split("_", 4)[-1] for p in RESULTS.glob("mem_rss_*")})
    for vis in ("public", "private"):
        for op in sorted({"_".join(p.stem.split("_")[4:]) for p in RESULTS.glob(f"mem_rss_*_{vis}_*")}):
            cells = []
            for s in sizes:
                a, b = RESULTS / f"mem_rss_{s}_{vis}_{op}.json", RESULTS / f"mem_tracemalloc_{s}_{vis}_{op}.json"
                if a.exists() and b.exists():
                    ra, rb = json.loads(a.read_text()), json.loads(b.read_text())
                    cells.append(f"cold {ra['cold_ms']:,.0f} ms; RSS +{ra['rss_peak_delta_mb']:,.0f} MB; py {rb['tracemalloc_peak_mb']:,.0f} MB")
                else:
                    cells.append("-")
            rows.append([f"{op} [{vis}]"] + cells)
    table("Cold first run in a fresh process, peak memory", head, rows)

    # Database facts
    rows = []
    for s in sizes:
        f = data[s]["facts_after_public"]
        rows.append([f"{s:,}", json.dumps(f["core_releases"]), json.dumps(f["bridge_releases"]),
                     json.dumps(f["core_released_rows"]), json.dumps(f["bridge_released_rows"]),
                     json.dumps(f["core_blobs"]), json.dumps(f["table_sizes"])])
    table("After the public publishes", ["size", "core releases", "bridge releases", "core released rows",
                                          "bridge released rows", "core blobs", "table sizes (bytes)"], rows)
    for s in sizes:
        print(f"\nedits at {s}: {data[s]['edits']}")
        print(f"seed/copy at {s}: " + json.dumps({k: v for k, v in data[s]['state'].items() if k.endswith('_s')}))


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or [1000])
