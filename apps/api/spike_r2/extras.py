"""Measurements that need their own small experiments, on the state `seed.py` and `measure.py`
left (so run after them):  python -m spike_r2.extras 5000

- how many times a read of a document is repeated inside one request (copy-plan of the bridge,
  updates), by counting the calls;
- what a decoded `Content` holds in memory once it is kept (what a cache per release id would
  retain), and what the same `Content` loaded from the rows holds;
- the cost of `replace_stored_rows` and of `store_release_document` alone, and of the revision of
  a tenant (`tenant.export_revision`, ADR 0262) that could serve as a cache key;
- browsing a repository through ten consecutive pages, document path and rows path;
- the slowest statements of the library-side reads.
"""

from __future__ import annotations

import asyncio
import gc
import sys
import time
import tracemalloc
import uuid
from typing import Any
from unittest import mock

from asgi_lifespan import LifespanManager
from fastapi_pagination import Params
from sqlalchemy import text

from lorenzo_api import release_document, release_document_store
from lorenzo_api import repository_upstream as upstream_module
from lorenzo_api.models import RepositoryRelease
from lorenzo_api.release_document_store import read_release_content, store_release_document
from lorenzo_api.repository_content import load_content
from lorenzo_api.repository_digest import assess, replace_stored_rows
from lorenzo_api.repository_releases import latest_release
from lorenzo_api.routers.repositories import entities_page
from spike_r2.common import app, load_state, probe, timed, write_result
from spike_r2.measure import (
    OPS,
    World,
    _raise,
    in_tenant,
    set_visibility,
)


async def counting(w: World, op_name: str) -> dict[str, int]:
    """Calls of the document functions during one run of an op."""
    counts = {"read_release_content": 0, "read_release_copies": 0, "loads": 0, "decode": 0}
    real_content = release_document_store.read_release_content
    real_copies = release_document_store.read_release_copies
    real_loads = release_document.loads
    real_decode = release_document.decode

    async def content(*a: Any, **k: Any) -> Any:
        counts["read_release_content"] += 1
        return await real_content(*a, **k)

    async def copies(*a: Any, **k: Any) -> Any:
        counts["read_release_copies"] += 1
        return await real_copies(*a, **k)

    def loads(*a: Any, **k: Any) -> Any:
        counts["loads"] += 1
        return real_loads(*a, **k)

    def decode(*a: Any, **k: Any) -> Any:
        counts["decode"] += 1
        return real_decode(*a, **k)

    with (
        mock.patch.object(upstream_module, "read_release_content", content),
        mock.patch.object(upstream_module, "read_release_copies", copies),
        mock.patch.object(release_document, "loads", loads),
        mock.patch.object(release_document, "decode", decode),
    ):
        await OPS[op_name](w)
    return counts


async def retained(w: World) -> dict[str, Any]:
    """Memory a kept `Content` holds (tracemalloc, after a collection), loaded from the rows and
    read from the document."""
    out: dict[str, Any] = {}
    async with in_tenant(w.core) as s:
        release = await latest_release(s, w.core)
        assert release is not None
        for label, loader in (
            ("from_rows", lambda: load_content(s, w.core)),
            (
                "from_document",
                lambda: read_release_content(s, tenant_id=w.core, release_id=release.id),
            ),
        ):
            gc.collect()
            tracemalloc.start()
            before = tracemalloc.get_traced_memory()[0]
            content = await loader()
            gc.collect()
            held = tracemalloc.get_traced_memory()[0] - before
            tracemalloc.stop()
            out[f"kept_{label}_mb"] = round(held / 1e6, 1)
            out[f"kept_{label}_entities"] = len(content.entities)
            del content
    return out


async def write_pieces(w: World) -> list[dict[str, Any]]:
    """`replace_stored_rows`, `store_release_document` and a read of the tenant's revision, each
    alone and in a transaction that is rolled back."""
    rows: list[dict[str, Any]] = []
    async with in_tenant(w.core) as s:
        assessed = await assess(s, w.core)

    async def replace() -> int:
        async with in_tenant(w.core) as s:
            await replace_stored_rows(s, w.core, assessed.live.values())
            await s.rollback()
        return len(assessed.live)

    t = await timed("replace_stored_rows (delete the set, insert it again), core", replace, reps=5)
    rows.append(t.as_dict())

    async def store() -> int:
        async with in_tenant(w.core) as s:
            number = 20_000 + int(time.time() * 1000) % 1_000_000
            release = RepositoryRelease(
                id=uuid.uuid4(), tenant_id=w.core, number=number, label=f"x-{number}"
            )
            s.add(release)
            await s.flush()
            stored = await store_release_document(
                s, tenant_id=w.core, release_id=release.id, content=assessed.content
            )
            await s.rollback()
        return stored.size

    rows.append((await timed("store_release_document alone, core", store, reps=5)).as_dict())

    async def revision() -> int:
        async with in_tenant(w.core) as s:
            value = await s.scalar(
                text("SELECT export_revision FROM tenant WHERE id = :t"), {"t": w.core}
            )
        return int(value or 0)

    rows.append((await timed("read tenant.export_revision, core", revision, reps=7)).as_dict())

    async def list_releases() -> int:
        async with in_tenant(w.core) as s:
            return len(
                (
                    await s.execute(
                        text("SELECT id, number, label, digest FROM repository_release "
                             "WHERE tenant_id = :t"),
                        {"t": w.core},
                    )
                ).all()
            )

    rows.append((await timed("read the release list, core", list_releases, reps=7)).as_dict())
    for row in rows:
        print("  ", row["name"], row["median_ms"], "ms", flush=True)
    return rows


async def browse_ten_pages(w: World, mode: str) -> dict[str, Any]:
    async def ten() -> int:
        total = 0
        for page in range(1, 11):
            async with in_tenant(w.shelf) as s:
                result = await entities_page(s, w.core, Params(page=page, size=50), None, _raise)
                total += len(result.items)
        return total

    t = await timed(f"ten consecutive browse pages ({mode})", ten, reps=3)
    print("  ", t.name, round(t.median * 1000), "ms", flush=True)
    return t.as_dict()


async def slowest(w: World) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in ("updates_shelf_core", "copy_plan_bridge", "assess_core"):
        probe.reset()
        await OPS[name](w)
        out[name] = {
            "statements": probe.statements,
            "db_ms": round(probe.db_seconds * 1000, 1),
            "slowest": [(k, round(v * 1000, 1), n) for k, v, n in probe.slowest(6)],
        }
    return out


async def run(size: int) -> None:
    w = World(load_state(size))
    results: dict[str, Any] = {"size": size}
    async with LifespanManager(app):
        await set_visibility([w.core, w.bridge], "public")
        print("== document reads inside one request (public)", flush=True)
        for name in ("copy_plan_core", "copy_plan_bridge", "updates_shelf_core", "updates_stack_bridge", "browse_page_core"):
            results[f"calls_public_{name}"] = await counting(w, name)
            print("  ", name, results[f"calls_public_{name}"], flush=True)
        print("== retained memory", flush=True)
        results["retained"] = await retained(w)
        print("  ", results["retained"], flush=True)
        print("== write pieces", flush=True)
        results["write_pieces"] = await write_pieces(w)
        print("== browse, ten pages", flush=True)
        results["browse_ten_public"] = await browse_ten_pages(w, "document")
        results["slowest_public"] = await slowest(w)
        await set_visibility([w.core, w.bridge], "private")
        results["browse_ten_private"] = await browse_ten_pages(w, "rows")
        results["slowest_private"] = await slowest(w)
        await set_visibility([w.core, w.bridge], "public")
    write_result(f"extras_{size}", results)


if __name__ == "__main__":
    asyncio.run(run(int(sys.argv[1])))
