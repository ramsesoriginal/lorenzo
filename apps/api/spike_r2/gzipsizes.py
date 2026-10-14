"""Prints the gzipped sizes by level:  python -m spike_r2.gzipsizes 1000 5000 20000"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RESULTS = Path(os.environ.get("R2_RESULT_DIR", Path(__file__).resolve().parent / "results"))
for size in (int(a) for a in sys.argv[1:]):
    pieces = json.loads((RESULTS / f"timings_{size}.json").read_text())["pieces"]
    for row in pieces:
        if row.get("phase") == "public" and "gzip level" in row["name"]:
            print(size, row["name"], row["gzip_bytes"], row["median_ms"], "ms")
