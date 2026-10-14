"""Prints the database facts of each size (documents, rows, blobs, table sizes):
    python -m spike_r2.facts 1000 5000 20000"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RESULTS = Path(os.environ.get("R2_RESULT_DIR", Path(__file__).resolve().parent / "results"))

for size in (int(a) for a in sys.argv[1:]):
    facts = json.loads((RESULTS / f"timings_{size}.json").read_text())["facts_after_public"]
    print(f"== {size}")
    for repo in ("core", "bridge"):
        docs = [(r["number"], r["document_bytes"], r["blobs"]) for r in facts[f"{repo}_releases"]]
        print(repo, "releases (number, document bytes, blobs):", docs)
        print(repo, "rows:", facts[f"{repo}_rows"], "released rows:", facts[f"{repo}_released_rows"],
              "blob table:", facts[f"{repo}_blobs"])
    print("table sizes:", facts["table_sizes"])
