"""Whether the cyclic garbage collector is a large part of building a big `Content`:
    python -m spike_r2.gcexp 5000
Needs only what seed.py built. Each read runs with the collector on (as the app runs) and with it
off for the length of the read; a collection is made before each run, outside the time."""

from __future__ import annotations

import asyncio
import gc
import json
import statistics
import sys
import time
from typing import Any

from asgi_lifespan import LifespanManager

from lorenzo_api import release_document
from lorenzo_api.repository_content import load_content
from spike_r2.common import app, load_state, write_result
from spike_r2.measure import World, in_tenant


async def run(size: int) -> None:
    w = World(load_state(size))
    rows: list[dict[str, Any]] = []
    async with LifespanManager(app):
        async with in_tenant(w.core) as s:
            content = await load_content(s, w.core)
        document, files = release_document.encode(content)
        text = json.dumps(document, separators=(",", ":"), ensure_ascii=False)
        gz = release_document.dumps(document)

        async def load() -> Any:
            async with in_tenant(w.core) as s:
                return await load_content(s, w.core)

        async def decode() -> Any:
            return release_document.decode(document, files)

        async def loads() -> Any:
            return json.loads(text)

        async def gunzip_loads() -> Any:
            return release_document.loads(gz)

        for name, op in (
            ("load_content", load),
            ("decode (document to Content)", decode),
            ("json.loads of the document", loads),
            ("gunzip + json.loads", gunzip_loads),
        ):
            for mode in ("gc on", "gc off"):
                walls = []
                for i in range(6):
                    gc.collect()
                    if mode == "gc off":
                        gc.disable()
                    started = time.perf_counter()
                    kept = await op()
                    wall = time.perf_counter() - started
                    gc.enable()
                    del kept
                    if i:
                        walls.append(wall)
                rows.append(
                    {"name": f"{name}, {mode}", "median_ms": round(statistics.median(walls) * 1000, 1)}
                )
                print("  ", rows[-1], flush=True)
    write_result(f"gc_{size}", rows)


if __name__ == "__main__":
    asyncio.run(run(int(sys.argv[1])))
