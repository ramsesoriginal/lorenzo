"""Prints the extras results as tables:  python -m spike_r2.summarize_extras 1000 5000 20000"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RESULTS = Path(os.environ.get("R2_RESULT_DIR", Path(__file__).resolve().parent / "results"))


def main(sizes: list[int]) -> None:
    data = {s: json.loads((RESULTS / f"extras_{s}.json").read_text()) for s in sizes}
    head = "| What | " + " | ".join(f"{s:,}" for s in sizes) + " |"
    rule = "| --- | " + " | ".join("---" for _ in sizes) + " |"
    print(head)
    print(rule)
    for op in ("copy_plan_core", "copy_plan_bridge", "updates_shelf_core", "updates_stack_bridge", "browse_page_core"):
        print(f"| calls in {op} | " + " | ".join(json.dumps(data[s][f"calls_public_{op}"]) for s in sizes) + " |")
    for key in ("kept_from_rows_mb", "kept_from_document_mb"):
        print(f"| {key} | " + " | ".join(str(data[s]["retained"][key]) for s in sizes) + " |")
    names = [r["name"] for r in data[sizes[0]]["write_pieces"]]
    for i, name in enumerate(names):
        print(f"| {name} | " + " | ".join(f"{data[s]['write_pieces'][i]['median_ms']:,.0f}" for s in sizes) + " |")
    for key in ("browse_ten_public", "browse_ten_private"):
        print(f"| {key} | " + " | ".join(f"{data[s][key]['median_ms']:,.0f}" for s in sizes) + " |")
    for mode in ("public", "private"):
        for op in ("updates_shelf_core", "copy_plan_bridge", "assess_core"):
            print(f"| db_ms/total statements {mode} {op} | " + " | ".join(
                f"{data[s][f'slowest_{mode}'][op]['db_ms']:,.0f} ms / {data[s][f'slowest_{mode}'][op]['statements']}" for s in sizes) + " |")
    for s in sizes:
        print(f"\nslowest at {s} (public):")
        for op, v in data[s]["slowest_public"].items():
            print(" ", op, json.dumps(v["slowest"][:3])[:400])


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]])
