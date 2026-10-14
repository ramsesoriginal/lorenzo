"""Prints the preview and release-list timings:  python -m spike_r2.previews 1000 5000 20000"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RESULTS = Path(os.environ.get("R2_RESULT_DIR", Path(__file__).resolve().parent / "results"))
for size in (int(a) for a in sys.argv[1:]):
    data = json.loads((RESULTS / f"timings_{size}.json").read_text())
    for key in ("preview_with_edits", "preview_public", "preview_bridge", "releases_list"):
        row = data[key]
        print(size, row["name"], row["median_ms"], "ms", row["statements"], "stmts", row.get("response_bytes"), "bytes")
