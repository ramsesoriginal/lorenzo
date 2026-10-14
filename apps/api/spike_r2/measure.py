"""The R2 measurements for one size (the repositories `seed.py` built).

    python -m spike_r2.measure 5000                 # every timing, writes results/timings_5000.json
    python -m spike_r2.measure 5000 --op NAME --visibility public|private
                                                    # one op in this fresh process: cold time and
                                                    # peak memory (RSS), writes results/mem_*.json
    python -m spike_r2.measure 5000 --op NAME --visibility public --tracemalloc
                                                    # the same with tracemalloc's peak instead
    python -m spike_r2.measure 5000 --profile NAME --visibility public
                                                    # cProfile of one op, top of the table

Timings are the median of five runs after one warm-up run, through the HTTP API (httpx against the
app in this process) for the routes and by calling the functions for the pieces; `first_run_ms` is
the first, warm-up run of the process. Statements and database time are the median run's.
"""

from __future__ import annotations

import argparse
import asyncio
import cProfile
import gzip
import io
import json
import pstats
import sys
import time
import tracemalloc
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from asgi_lifespan import LifespanManager
from fastapi_pagination import Params
from sqlalchemy import text

from lorenzo_api import release_document
from lorenzo_api.models import RepositoryRelease
from lorenzo_api.release_document_store import (
    read_release_content,
    read_release_copies,
    store_release_document,
)
from lorenzo_api.repository_access import reading_repository
from lorenzo_api.repository_content import Content, load_content
from lorenzo_api.repository_copying import plan_copy
from lorenzo_api.repository_digest import (
    assess,
    compare,
    descriptions_edited_since,
    detect,
    digest_of,
    live_rows,
    replace_stored_rows,
    stored_rows,
)
from lorenzo_api.repository_releases import current_release, latest_release
from lorenzo_api.repository_updates import compute_updates
from lorenzo_api.repository_upstream import entity_rows, load_upstream
from lorenzo_api.routers.repositories import entities_page
from spike_r2.common import (
    app,
    RESULT_DIR,
    Actor,
    Timing,
    admin_session_factory,
    load_state,
    new_client,
    probe,
    tenant_session,
    timed,
    write_result,
)

REPS = 5


# --- Helpers -----------------------------------------------------------------------------------


def pseudo(salt: str, *parts: str) -> str:
    key = ", ".join((f"'{salt}'", *parts))
    return f"(abs(hashtextextended(concat_ws(':', {key}), 7) % 1000000) / 1000000.0)"


@asynccontextmanager
async def in_tenant(tenant_id: uuid.UUID) -> AsyncIterator[Any]:
    session = await tenant_session(tenant_id)
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()


async def set_visibility(repositories: list[uuid.UUID], visibility: str) -> None:
    async with admin_session_factory() as session:
        for repository in repositories:
            await session.execute(
                text("UPDATE repository_profile SET visibility = :v WHERE tenant_id = :t"),
                {"v": visibility, "t": repository},
            )
        await session.commit()


async def edit_core(core: uuid.UUID, n: int) -> dict[str, int]:
    """What an author does between two releases: about 1% of the entries renamed, 1% of the stat
    values changed, 0.5% entries added, 0.3% removed, 0.2% of the parent edges taken off, 1% of
    the descriptions edited. Written straight in the database."""
    counts: dict[str, int] = {}
    async with admin_session_factory() as session:

        async def run(label: str, sql: str, **params: Any) -> None:
            result = await session.execute(text(sql), {"t": core, **params})
            counts[label] = result.rowcount  # type: ignore[attr-defined]

        await run(
            "renamed",
            "UPDATE entity SET name = name || ' rev' WHERE tenant_id = :t AND "
            f"{pseudo('ren', 'id::text')} < 0.01",
        )
        await run(
            "stat_values_changed",
            "UPDATE entity_stat SET value_int = value_int + 1 WHERE tenant_id = :t AND "
            "value_int IS NOT NULL AND "
            f"{pseudo('sv', 'entity_id::text', 'stat_definition_id::text')} < 0.01",
        )
        await run(
            "parent_edges_removed",
            "DELETE FROM entity_prototype WHERE tenant_id = :t AND "
            f"{pseudo('pe', 'entity_id::text', 'prototype_id::text')} < 0.002",
        )
        await run(
            "entities_removed",
            "DELETE FROM entity WHERE tenant_id = :t AND "
            f"{pseudo('del', 'id::text')} < 0.003",
        )
        added = max(2, n // 200)
        await run(
            "entities_added",
            "WITH new AS (SELECT gen_random_uuid() AS id, g FROM generate_series(1, :added) g), "
            "e AS (INSERT INTO entity (id, tenant_id, name) SELECT id, :t, 'Added ' || g FROM new "
            "RETURNING id), i AS (INSERT INTO item (entity_id, tenant_id) SELECT id, :t FROM new "
            "RETURNING entity_id) INSERT INTO entity_prototype (entity_id, prototype_id, "
            "tenant_id, position) SELECT new.id, (SELECT id FROM entity WHERE tenant_id = :t "
            "AND name LIKE 'Longsword %' ORDER BY name LIMIT 1), :t, 0 FROM new",
            added=added,
        )
        await run(
            "descriptions_edited",
            "UPDATE payload_description SET content = content || ' (edited)' WHERE tenant_id = :t "
            f"AND {pseudo('de', 'payload_id::text')} < 0.01",
        )
        await run(
            "payloads_touched",
            "UPDATE payload SET updated_at = now() WHERE tenant_id = :t AND id IN (SELECT "
            "payload_id FROM payload_description WHERE tenant_id = :t AND content LIKE '%(edited)')",
        )
        await session.commit()
    return counts


async def edit_bridge(bridge: uuid.UUID) -> dict[str, int]:
    """Between two releases of the bridge: 5% of its own entries renamed, 1% removed, and a new
    parent for one copied entry in forty (attachments)."""
    counts: dict[str, int] = {}
    async with admin_session_factory() as session:
        result = await session.execute(
            text(
                "UPDATE entity SET name = name || ' rev' WHERE tenant_id = :t AND "
                "name LIKE 'Bridge piece%' AND " + pseudo("brn", "id::text") + " < 0.05"
            ),
            {"t": bridge},
        )
        counts["renamed"] = result.rowcount  # type: ignore[attr-defined]
        result = await session.execute(
            text(
                "DELETE FROM entity WHERE tenant_id = :t AND name LIKE 'Bridge piece%' AND "
                + pseudo("brd", "id::text")
                + " < 0.01"
            ),
            {"t": bridge},
        )
        counts["removed"] = result.rowcount  # type: ignore[attr-defined]
        result = await session.execute(
            text(
                "WITH copies AS (SELECT l.entity_id AS id, split_part(e.name, ' ', 2)::int AS n "
                "FROM repository_copy_link_entity l JOIN entity e ON e.id = l.entity_id AND "
                "e.tenant_id = l.tenant_id WHERE l.tenant_id = :t AND l.entity_id IS NOT NULL) "
                "INSERT INTO entity_prototype (entity_id, prototype_id, tenant_id, position) "
                "SELECT c.id, p.id, :t, 60 FROM copies c JOIN copies p ON p.n = 1 + floor("
                + pseudo("att2", "c.n::text")
                + " * (c.n - 1))::int WHERE c.n % 40 = 11 AND c.n > 1 ON CONFLICT DO NOTHING"
            ),
            {"t": bridge},
        )
        counts["attachments_added"] = result.rowcount  # type: ignore[attr-defined]
        await session.commit()
    return counts


async def touch_one(repository: uuid.UUID, k: int, like: str = "%") -> None:
    """The smallest edit: one entry renamed."""
    async with admin_session_factory() as session:
        await session.execute(
            text(
                "UPDATE entity SET name = name || ' ' || :k WHERE id = (SELECT id FROM entity "
                "WHERE tenant_id = :t AND name LIKE :like ORDER BY name LIMIT 1 OFFSET :o)"
            ),
            {"t": repository, "k": f"v{k}", "o": k, "like": like},
        )
        await session.commit()


async def database_facts(core: uuid.UUID, bridge: uuid.UUID) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    async with admin_session_factory() as session:
        for name, tenant in (("core", core), ("bridge", bridge)):
            rows = await session.execute(
                text(
                    "SELECT r.number, r.label, octet_length(d.content) AS gz, d.blobs "
                    "FROM repository_release r LEFT JOIN repository_release_document d "
                    "ON d.release_id = r.id WHERE r.tenant_id = :t ORDER BY r.number"
                ),
                {"t": tenant},
            )
            facts[f"{name}_releases"] = [
                {"number": r.number, "label": r.label, "document_bytes": r.gz,
                 "blobs": len(r.blobs) if r.blobs is not None else None}
                for r in rows
            ]  # fmt: skip
            facts[f"{name}_released_rows"] = (
                await session.execute(
                    text("SELECT count(*) FROM repository_released_row WHERE tenant_id = :t"),
                    {"t": tenant},
                )
            ).scalar_one()
            facts[f"{name}_blobs"] = dict(
                (
                    await session.execute(
                        text(
                            "SELECT count(*) AS blobs, coalesce(sum(octet_length(data)), 0) "
                            "AS bytes FROM repository_release_blob WHERE tenant_id = :t"
                        ),
                        {"t": tenant},
                    )
                ).one()._mapping
            )
            facts[f"{name}_rows"] = dict(
                (
                    await session.execute(
                        text(
                            "SELECT (SELECT count(*) FROM entity WHERE tenant_id = :t) AS entities,"
                            "(SELECT count(*) FROM entity_prototype WHERE tenant_id = :t) AS edges,"
                            "(SELECT count(*) FROM entity_stat WHERE tenant_id = :t) AS stats,"
                            "(SELECT count(*) FROM information WHERE tenant_id = :t) AS infos,"
                            "(SELECT count(*) FROM repository_copy_link_entity WHERE tenant_id = :t)"
                            " AS links"
                        ),
                        {"t": tenant},
                    )
                ).one()._mapping
            )
        facts["table_sizes"] = {
            row[0]: row[1]
            for row in await session.execute(
                text(
                    "SELECT relname, pg_total_relation_size(oid) FROM pg_class WHERE relname IN "
                    "('repository_release_document', 'repository_release_blob', "
                    "'repository_released_row', 'entity', 'entity_stat', 'information')"
                )
            )
        }
    return facts


# --- The measured ops (one run of each; both the timing run and the memory run use them) -------


class World:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state
        self.size: int = state["size"]
        u = uuid.UUID
        self.core, self.bridge = u(state["core"]), u(state["bridge"])
        self.shelf, self.stack, self.fresh = u(state["shelf"]), u(state["stack"]), u(state["fresh"])
        self.author, self.gm = u(state["author"]), u(state["gm"])

    async def core_release(self) -> Any:
        async with in_tenant(self.core) as s:
            return await latest_release(s, self.core)


Op = Callable[[World], Awaitable[Any]]


async def op_load_content(w: World) -> Any:
    async with in_tenant(w.core) as s:
        content = await load_content(s, w.core)
    return {"entities": len(content.entities)}


async def op_load_content_bridge(w: World) -> Any:
    async with in_tenant(w.bridge) as s:
        content = await load_content(s, w.bridge)
    return {"entities": len(content.entities)}


async def op_assess(w: World) -> Any:
    async with in_tenant(w.core) as s:
        a = await assess(s, w.core)
    return {"differing": a.comparison.differing, "live_rows": len(a.live)}


async def op_assess_bridge(w: World) -> Any:
    async with in_tenant(w.bridge) as s:
        a = await assess(s, w.bridge)
    return {"differing": a.comparison.differing, "live_rows": len(a.live)}


async def _build_document(w: World, repository: uuid.UUID) -> dict[str, Any]:
    """What a public publish does besides the release row: assess, the released rows, the
    document. In a transaction that is rolled back, so it can be repeated."""
    async with in_tenant(repository) as s:
        a = await assess(s, repository)
        number = 10_000 + int(time.time() * 1000) % 1_000_000
        release = RepositoryRelease(
            id=uuid.uuid4(), tenant_id=repository, number=number, label=f"spike-{number}"
        )
        s.add(release)
        await s.flush()
        await replace_stored_rows(s, repository, a.live.values())
        stored = await store_release_document(
            s, tenant_id=repository, release_id=release.id, content=a.content
        )
        await s.rollback()
    return {"document_bytes": stored.size, "files": stored.files}


async def op_publish_build_core(w: World) -> Any:
    return await _build_document(w, w.core)


async def op_publish_build_bridge(w: World) -> Any:
    return await _build_document(w, w.bridge)


async def op_publish_digest_only_core(w: World) -> Any:
    """A private publish's work besides the release row: assess and the released rows."""
    async with in_tenant(w.core) as s:
        a = await assess(s, w.core)
        await replace_stored_rows(s, w.core, a.live.values())
        await s.rollback()
    return {"live_rows": len(a.live)}


async def op_read_document_core(w: World) -> Any:
    async with in_tenant(w.core) as s:
        release = await latest_release(s, w.core)
        assert release is not None
        content = await read_release_content(s, tenant_id=w.core, release_id=release.id)
    return {"entities": len(content.entities)}


async def op_read_document_bridge(w: World) -> Any:
    async with in_tenant(w.bridge) as s:
        release = await latest_release(s, w.bridge)
        assert release is not None
        content = await read_release_content(s, tenant_id=w.bridge, release_id=release.id)
    return {"entities": len(content.entities)}


async def op_updates_shelf_core(w: World) -> Any:
    async with in_tenant(w.shelf) as s:
        updates = await compute_updates(s, tenant_id=w.shelf, repository_id=w.core)
    return {"changed": len(updates.changed), "added": len(updates.added),
            "removed": len(updates.removed)}  # fmt: skip


async def op_updates_stack_bridge(w: World) -> Any:
    async with in_tenant(w.stack) as s:
        updates = await compute_updates(s, tenant_id=w.stack, repository_id=w.bridge)
    return {"changed": len(updates.changed), "added": len(updates.added),
            "removed": len(updates.removed), "attachments": len(updates.attachments_added)}  # fmt: skip


async def op_updates_stack_core(w: World) -> Any:
    async with in_tenant(w.stack) as s:
        updates = await compute_updates(s, tenant_id=w.stack, repository_id=w.core)
    return {"changed": len(updates.changed), "added": len(updates.added),
            "removed": len(updates.removed)}  # fmt: skip


async def op_copy_plan_core(w: World) -> Any:
    async with in_tenant(w.fresh) as s:
        plan = await plan_copy(s, tenant_id=w.fresh, repository_id=w.core, user_id=w.gm, resolutions=[])
    return {"steps": len(plan.steps), "rows": sum(len(v) for v in plan.rows.values())}


async def op_copy_plan_bridge(w: World) -> Any:
    async with in_tenant(w.fresh) as s:
        plan = await plan_copy(s, tenant_id=w.fresh, repository_id=w.bridge, user_id=w.gm, resolutions=[])
    return {"steps": len(plan.steps), "rows": sum(len(v) for v in plan.rows.values())}


async def op_load_upstream_core(w: World) -> Any:
    async with in_tenant(w.shelf) as s:
        async with reading_repository(s, w.core):
            read = await load_upstream(s, w.core)
    return {"public": read.public, "entities": len(read.content.entities)}


async def op_browse_page_core(w: World) -> Any:
    """One page of the entities (50 of them), as a library browses a repository."""
    async with in_tenant(w.shelf) as s:
        page = await entities_page(s, w.core, Params(page=1, size=50), None, _raise)
    return {"total": page.total, "items": len(page.items)}


async def op_browse_search_core(w: World) -> Any:
    async with in_tenant(w.shelf) as s:
        page = await entities_page(s, w.core, Params(page=1, size=50), "sword", _raise)
    return {"total": page.total, "items": len(page.items)}


async def op_browse_last_page_core(w: World) -> Any:
    async with in_tenant(w.shelf) as s:
        last = max(1, (w.size + 49) // 50)
        page = await entities_page(s, w.core, Params(page=last, size=50), None, _raise)
    return {"total": page.total, "items": len(page.items)}


def _raise() -> Exception:
    return RuntimeError("not readable")


OPS: dict[str, Op] = {
    "load_content_core": op_load_content,
    "load_content_bridge": op_load_content_bridge,
    "assess_core": op_assess,
    "assess_bridge": op_assess_bridge,
    "publish_digest_only_core": op_publish_digest_only_core,
    "publish_build_core": op_publish_build_core,
    "publish_build_bridge": op_publish_build_bridge,
    "read_document_core": op_read_document_core,
    "read_document_bridge": op_read_document_bridge,
    "updates_shelf_core": op_updates_shelf_core,
    "updates_stack_core": op_updates_stack_core,
    "updates_stack_bridge": op_updates_stack_bridge,
    "copy_plan_core": op_copy_plan_core,
    "copy_plan_bridge": op_copy_plan_bridge,
    "load_upstream_core": op_load_upstream_core,
    "browse_page_core": op_browse_page_core,
    "browse_search_core": op_browse_search_core,
    "browse_last_page_core": op_browse_last_page_core,
}


# --- One op in a fresh process: cold time and peak memory ---------------------------------------


def _proc_kb(field: str) -> int:
    with open("/proc/self/status") as status:
        for line in status:
            if line.startswith(field + ":"):
                return int(line.split()[1])
    return 0


async def one_op(world: World, name: str, use_tracemalloc: bool) -> dict[str, Any]:
    await in_tenant_warm(world)
    baseline_kb = _proc_kb("VmRSS")
    if use_tracemalloc:
        tracemalloc.start()
        tracemalloc.reset_peak()
        before = tracemalloc.get_traced_memory()[0]
    else:
        with open("/proc/self/clear_refs", "w") as refs:
            refs.write("5")  # resets VmHWM, the peak resident size
    probe.reset()
    started = time.perf_counter()
    info = await OPS[name](world)
    wall = time.perf_counter() - started
    result: dict[str, Any] = {
        "op": name,
        "cold_ms": round(wall * 1000, 1),
        "statements": probe.statements,
        "db_ms": round(probe.db_seconds * 1000, 1),
        "info": info,
    }
    if use_tracemalloc:
        peak = tracemalloc.get_traced_memory()[1]
        result["tracemalloc_peak_mb"] = round((peak - before) / 1e6, 1)
        tracemalloc.stop()
    else:
        result["rss_baseline_mb"] = round(baseline_kb / 1024, 1)
        result["rss_peak_mb"] = round(_proc_kb("VmHWM") / 1024, 1)
        result["rss_peak_delta_mb"] = round((_proc_kb("VmHWM") - baseline_kb) / 1024, 1)
    return result


async def in_tenant_warm(world: World) -> None:
    """One trivial query first, so the connection and the first statements are not in the op."""
    async with in_tenant(world.shelf) as s:
        await s.execute(text("SELECT 1"))


# --- The timings -------------------------------------------------------------------------------


def http_get(
    actor: Actor, url: str, **kw: Any
) -> Callable[[], Awaitable[tuple[int, int]]]:
    async def run() -> tuple[int, int]:
        response = await actor.get(url, **kw)
        assert response.status_code == 200, (url, response.status_code, response.text[:300])
        return response.status_code, len(response.content)

    return run


def with_size(result: Any) -> dict[str, Any]:
    return {"response_bytes": result[1]}


async def measure_reads(
    w: World, author: Actor, gm: Actor, mode: str, out: dict[str, Any]
) -> None:
    """The routes and pieces a library and its author use against the repositories as they are
    now (`mode`: the visibility they have, so which read path)."""
    rows: list[dict[str, Any]] = out.setdefault(f"reads_{mode}", [])

    async def add(timing: Timing) -> None:
        rows.append(timing.as_dict())
        print(f"  [{mode}] {timing.name}: {timing.median * 1000:.0f} ms "
              f"({timing.statements} stmts)", flush=True)  # fmt: skip

    base = f"/tenants/{w.fresh}/repositories"
    await add(await timed("GET copy-plan core (Fresh)", http_get(gm, f"{base}/{w.core}/copy-plan"),
                          reps=REPS, extra=with_size))  # fmt: skip
    await add(await timed("GET copy-plan bridge (Fresh; Core and Bridge)",
                          http_get(gm, f"{base}/{w.bridge}/copy-plan"), reps=REPS,
                          extra=with_size))  # fmt: skip
    await add(await timed("GET updates core (Shelf)",
                          http_get(gm, f"/tenants/{w.shelf}/repositories/{w.core}/updates"),
                          reps=REPS, extra=with_size))  # fmt: skip
    await add(await timed("GET updates core (Stack)",
                          http_get(gm, f"/tenants/{w.stack}/repositories/{w.core}/updates"),
                          reps=REPS, extra=with_size))  # fmt: skip
    await add(await timed("GET updates bridge (Stack)",
                          http_get(gm, f"/tenants/{w.stack}/repositories/{w.bridge}/updates"),
                          reps=REPS, extra=with_size))  # fmt: skip
    shelf = f"/tenants/{w.shelf}/repositories/{w.core}"
    await add(await timed("GET entities page 1 of 50", http_get(gm, f"{shelf}/entities",
                          params={"page": 1, "size": 50}), reps=REPS, extra=with_size))  # fmt: skip
    await add(await timed("GET entities q=sword", http_get(gm, f"{shelf}/entities",
                          params={"page": 1, "size": 50, "q": "sword"}), reps=REPS,
                          extra=with_size))  # fmt: skip
    await add(await timed("GET entities last page", http_get(gm, f"{shelf}/entities",
                          params={"page": max(1, (w.size + 49) // 50), "size": 50}), reps=REPS,
                          extra=with_size))  # fmt: skip
    await add(await timed("GET stat-groups", http_get(gm, f"{shelf}/stat-groups"), reps=REPS,
                          extra=with_size))  # fmt: skip
    await add(await timed("GET dependencies bridge (Fresh)",
                          http_get(gm, f"{base}/{w.bridge}/dependencies"), reps=REPS,
                          extra=with_size))  # fmt: skip
    await add(await timed("GET repositories of Shelf (the listing, no content)",
                          http_get(gm, f"/tenants/{w.shelf}/repositories"), reps=REPS,
                          extra=with_size))  # fmt: skip
    await add(await timed("GET repositories of Stack (the listing, no content)",
                          http_get(gm, f"/tenants/{w.stack}/repositories"), reps=REPS,
                          extra=with_size))  # fmt: skip
    # Direct pieces on the library side.
    for name in ("load_upstream_core",):
        timing = await timed(name, lambda name=name: OPS[name](w), reps=REPS)
        await add(timing)


async def measure_documents(w: World, out: dict[str, Any], phase: str) -> None:
    """The pieces of building and reading a document, on Core's and Bridge's current content."""
    pieces: list[dict[str, Any]] = out.setdefault("pieces", [])

    async def add(timing: Timing) -> None:
        pieces.append({"phase": phase, **timing.as_dict()})
        print(f"  [pieces {phase}] {timing.name}: {timing.median * 1000:.0f} ms "
              f"({timing.statements} stmts) {timing.extra}", flush=True)  # fmt: skip

    for label, repository in (("core", w.core), ("bridge", w.bridge)):
        async with in_tenant(repository) as s:
            content: Content = await load_content(s, repository)
            release = await latest_release(s, repository)
            stored = await stored_rows(s, repository)

        async def load(repository: uuid.UUID = repository) -> int:
            async with in_tenant(repository) as s2:
                return len((await load_content(s2, repository)).entities)

        await add(await timed(f"{label}: load_content", load, reps=REPS))
        holder: dict[str, Any] = {}

        async def sync(fn: Callable[[], Any]) -> Any:
            return fn()

        def do_live() -> Any:
            holder["live"] = live_rows(content)
            return holder["live"]

        await add(
            await timed(f"{label}: live_rows (hash every row)", lambda: sync(do_live), reps=REPS,
                        extra=lambda r: {"rows": len(r)})
        )  # fmt: skip
        live = holder["live"]
        await add(await timed(f"{label}: digest_of", lambda: sync(lambda: digest_of(live.values())),
                              reps=REPS))  # fmt: skip

        async def stored_load(repository: uuid.UUID = repository) -> int:
            async with in_tenant(repository) as s2:
                return len(await stored_rows(s2, repository))

        await add(await timed(f"{label}: stored_rows", stored_load, reps=REPS,
                              extra=lambda r: {"rows": r}))  # fmt: skip
        await add(await timed(f"{label}: compare + detect", lambda: sync(lambda: detect(compare(stored, live))),
                              reps=REPS))  # fmt: skip

        async def desc(repository: uuid.UUID = repository) -> int:
            async with in_tenant(repository) as s2:
                return await descriptions_edited_since(s2, repository, release.created_at if release else None)

        await add(await timed(f"{label}: descriptions_edited_since", desc, reps=REPS))
        await add(await timed(f"{label}: assess (all of the above)",
                              lambda label=label: OPS[f"assess_{label}"](w), reps=REPS))  # fmt: skip

        encoded: dict[str, Any] = {}

        def do_encode() -> Any:
            encoded["doc"], encoded["files"] = release_document.encode(content)
            return encoded["doc"]

        await add(await timed(f"{label}: encode", lambda: sync(do_encode), reps=REPS))
        doc = encoded["doc"]
        plain = json.dumps(doc, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
        gz_holder: dict[str, bytes] = {}

        def do_dumps() -> Any:
            gz_holder["gz"] = release_document.dumps(doc)
            return gz_holder["gz"]

        timing = await timed(f"{label}: dumps (JSON + gzip)", lambda: sync(do_dumps), reps=REPS)
        timing.extra |= {"plain_bytes": len(plain), "gzip_bytes": len(gz_holder["gz"]),
                         "files": len(encoded["files"]),
                         "file_bytes": sum(len(v) for v in encoded["files"].values())}  # fmt: skip
        await add(timing)

        for level in (9, 6, 1):
            levels: dict[int, bytes] = {}

            def do_gz(level: int = level, levels: dict[int, bytes] = levels) -> Any:
                levels[level] = gzip.compress(plain, compresslevel=level, mtime=0)
                return levels[level]

            timing = await timed(
                f"{label}: gzip level {level} of the JSON", lambda f=do_gz: sync(f), reps=REPS
            )
            timing.extra["gzip_bytes"] = len(levels[level])
            await add(timing)
        composition = {
            key: len(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode())
            for key, value in doc.items()
        }
        composition_gz = {
            key: len(
                gzip.compress(
                    json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode(),
                    compresslevel=6,
                    mtime=0,
                )
            )
            for key, value in doc.items()
        }
        pieces.append(
            {
                "phase": phase,
                "name": f"{label}: composition of the document",
                "median_ms": 0,
                "plain": composition,
                "gzip6": composition_gz,
            }
        )

        def do_json() -> Any:
            return json.dumps(doc, separators=(",", ":"), ensure_ascii=False, allow_nan=False)

        await add(await timed(f"{label}: JSON text alone", lambda: sync(do_json), reps=REPS))
        gz = gz_holder["gz"]
        await add(await timed(f"{label}: gunzip + json.loads", lambda: sync(lambda: release_document.loads(gz)),
                              reps=REPS))  # fmt: skip
        files = encoded["files"]
        await add(await timed(f"{label}: decode (document to Content)",
                              lambda: sync(lambda: release_document.decode(doc, files)), reps=REPS))  # fmt: skip

        async def build(label: str = label) -> Any:
            return await OPS[f"publish_build_{label}"](w)

        await add(await timed(f"{label}: assess + released rows + document, as a publish does it (rolled back)",
                              build, reps=3))  # fmt: skip
        if label == "core":
            await add(await timed("core: publish without a document (assess + released rows)",
                                  lambda: OPS["publish_digest_only_core"](w), reps=3))  # fmt: skip

        async def read(label: str = label) -> Any:
            return await OPS[f"read_document_{label}"](w)

        # A document exists once the repository has been published public (phase 2).
        if out.get("documents_exist"):
            await add(await timed(f"{label}: read_release_content (select + gunzip + decode)", read, reps=REPS))

            async def copies(repository: uuid.UUID = repository) -> Any:
                async with in_tenant(repository) as s2:
                    rel = await latest_release(s2, repository)
                    assert rel is not None
                    return await read_release_copies(s2, tenant_id=repository, release_id=rel.id)

            await add(await timed(f"{label}: read_release_copies (the manifest's read)", copies, reps=REPS))

            async def fetch(repository: uuid.UUID = repository) -> Any:
                async with in_tenant(repository) as s2:
                    rel = await latest_release(s2, repository)
                    assert rel is not None
                    row = (await s2.execute(text(
                        "SELECT content FROM repository_release_document WHERE release_id = :r"),
                        {"r": rel.id})).one()
                    return len(bytes(row[0]))

            await add(await timed(f"{label}: SQL fetch of the document alone", fetch, reps=REPS))


async def measure_page_of_decoded(w: World, out: dict[str, Any]) -> None:
    """What a browse costs when the `Content` is already in memory (the case a per-release cache
    would serve): entity_rows plus the paging of it."""
    rows: list[dict[str, Any]] = out.setdefault("pieces", [])
    async with in_tenant(w.core) as s:
        content = await load_content(s, w.core)

    async def page() -> Any:
        found = entity_rows(content, None)
        return len(found[:50])

    timing = await timed("core: entity_rows of an in-memory Content (a cached browse)", page, reps=REPS)
    rows.append(timing.as_dict())
    print(f"  [pieces] {timing.name}: {timing.median * 1000:.0f} ms", flush=True)


async def measure_all(size: int) -> None:
    global REPS
    REPS = 7 if size <= 5000 else 5
    state = load_state(size)
    w = World(state)
    out: dict[str, Any] = {"size": size, "state": state}
    async with LifespanManager(app):
        async with new_client() as client:
            author, gm = Actor(client, w.author), Actor(client, w.gm)

            print(f"== size {size}: publish while private", flush=True)
            out["edits"] = await edit_core(w.core, size)
            out["edits_bridge"] = await edit_bridge(w.bridge)
            out["facts_before_publish"] = await database_facts(w.core, w.bridge)

            # The live digest and the preview, with the edits in.
            out["preview_with_edits"] = (
                await timed("GET release-preview core (with edits)",
                            http_get(author, f"/tenants/{w.core}/release-preview"), reps=REPS,
                            extra=with_size)
            ).as_dict()  # fmt: skip
            print("  preview with edits:", out["preview_with_edits"]["median_ms"], "ms", flush=True)

            publishes: list[dict[str, Any]] = out.setdefault("publishes", [])

            async def publish(repository: uuid.UUID, label: str, mode: str, ack: bool) -> None:
                probe.reset()
                started = time.perf_counter()
                response = await author.put(
                    f"/tenants/{repository}/published",
                    json={"label": label, "notes": "spike", "acknowledge_breaking": ack},
                )
                wall = time.perf_counter() - started
                assert response.status_code == 200, (response.status_code, response.text[:400])
                publishes.append({
                    "repository": "core" if repository == w.core else "bridge",
                    "mode": mode, "label": label, "wall_ms": round(wall * 1000, 1),
                    "statements": probe.statements, "db_ms": round(probe.db_seconds * 1000, 1),
                    "slowest": probe.slowest(4),
                })  # fmt: skip
                print(f"  publish {label} ({mode}) of {publishes[-1]['repository']}: "
                      f"{wall * 1000:.0f} ms, {probe.statements} stmts", flush=True)  # fmt: skip

            await publish(w.core, "2.0", "private, edits (with breaking removals)", True)
            await touch_one(w.core, 1)
            await publish(w.core, "2.1", "private, one edit", False)
            await touch_one(w.core, 2)
            await publish(w.core, "2.2", "private, one edit", False)
            await publish(w.bridge, "1.1", "private, edits (with removals)", True)

            print("== pieces on private content", flush=True)
            await measure_documents(w, out, "private")
            await measure_page_of_decoded(w, out)

            print("== live (private) reads", flush=True)
            await measure_reads(w, author, gm, "private_before_public", out)

            print("== publish as public", flush=True)
            await set_visibility([w.core, w.bridge], "public")
            await touch_one(w.core, 3)
            await publish(w.core, "3.0", "public (document)", False)
            await touch_one(w.core, 4)
            await publish(w.core, "3.1", "public (document)", False)
            await touch_one(w.core, 5)
            await publish(w.core, "3.2", "public (document)", False)
            await touch_one(w.bridge, 2, "Bridge piece%")
            await publish(w.bridge, "2.0", "public (document)", False)
            await touch_one(w.bridge, 3, "Bridge piece%")
            await publish(w.bridge, "2.1", "public (document)", False)
            out["documents_exist"] = True
            out["facts_after_public"] = await database_facts(w.core, w.bridge)

            print("== document pieces", flush=True)
            await measure_documents(w, out, "public")

            print("== document (public) reads", flush=True)
            await measure_reads(w, author, gm, "public", out)

            print("== the live preview and the release list", flush=True)
            out["preview_public"] = (
                await timed("GET release-preview core (public, unchanged)",
                            http_get(author, f"/tenants/{w.core}/release-preview"), reps=REPS,
                            extra=with_size)
            ).as_dict()  # fmt: skip
            out["preview_bridge"] = (
                await timed("GET release-preview bridge", http_get(author, f"/tenants/{w.bridge}/release-preview"),
                            reps=REPS, extra=with_size)
            ).as_dict()  # fmt: skip
            out["releases_list"] = (
                await timed("GET releases core", http_get(author, f"/tenants/{w.core}/releases"),
                            reps=REPS, extra=with_size)
            ).as_dict()  # fmt: skip

            print("== live (private) reads, same content as the release", flush=True)
            await set_visibility([w.core, w.bridge], "private")
            await measure_reads(w, author, gm, "private", out)
            await set_visibility([w.core, w.bridge], "public")
    write_result(f"timings_{size}", out)


async def mem_op(size: int, name: str, visibility: str, use_tracemalloc: bool) -> None:
    w = World(load_state(size))
    await set_visibility([w.core, w.bridge], visibility)
    async with LifespanManager(app):
        result = await one_op(w, name, use_tracemalloc)
    result |= {"size": size, "visibility": visibility}
    kind = "tracemalloc" if use_tracemalloc else "rss"
    write_result(f"mem_{kind}_{size}_{visibility}_{name}", result)
    print(json.dumps(result))


async def profile_op(size: int, name: str, visibility: str) -> None:
    w = World(load_state(size))
    await set_visibility([w.core, w.bridge], visibility)
    async with LifespanManager(app):
        await in_tenant_warm(w)
        await OPS[name](w)  # warm-up
        profiler = cProfile.Profile()
        profiler.enable()
        await OPS[name](w)
        profiler.disable()
    buffer = io.StringIO()
    stats = pstats.Stats(profiler, stream=buffer).strip_dirs()
    buffer.write("\n--- by cumulative time\n")
    stats.sort_stats("cumulative").print_stats(28)
    buffer.write("\n--- by own time\n")
    stats.sort_stats("tottime").print_stats(18)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    (RESULT_DIR / f"profile_{size}_{visibility}_{name}.txt").write_text(buffer.getvalue())
    print(buffer.getvalue()[:3500])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("size", type=int)
    parser.add_argument("--op")
    parser.add_argument("--profile")
    parser.add_argument("--visibility", default="public")
    parser.add_argument("--tracemalloc", action="store_true")
    args = parser.parse_args()
    if args.profile:
        asyncio.run(profile_op(args.size, args.profile, args.visibility))
    elif args.op:
        asyncio.run(mem_op(args.size, args.op, args.visibility, args.tracemalloc))
    else:
        asyncio.run(measure_all(args.size))


if __name__ == "__main__":
    sys.exit(main())
