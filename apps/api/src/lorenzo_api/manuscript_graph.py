"""Source-normalized manuscript records and dependency validation (ADR 0438)."""

import uuid
from collections import defaultdict, deque
from typing import Any

from lorenzo_api.manuscript_comparison import bundle
from lorenzo_api.repository_content import Content

WRITING_KINDS = {"book", "edition", "chapter", "scene", "scene_telling", "carrier"}


def source_identities(content: Content) -> dict[str, str]:
    """Foreign repository entries resolve by origin, as in the ordinary copy planner."""
    identities = {str(id): str(content.links.entity.get(id, id)) for id in content.entities}
    identities.update({str(id): str(id) for id in content.payloads})
    identities.update({str(id): str(id) for id in content.carrier_coverage})
    return identities


def snapshots(
    content: Content, identities: dict[str, str] | None = None
) -> dict[str, dict[str, Any]]:
    def identity(value: uuid.UUID | None) -> str | None:
        if value is None:
            return None
        text = str(value)
        return text if identities is None else identities.get(text, "local:" + text)

    manuscripts: dict[uuid.UUID, Content] = {}
    owners = {}
    for info_id, info in content.information.items():
        if info.type == "manuscript":
            grouped = Content(tenant_id=content.tenant_id)
            grouped.information[info_id] = info
            manuscripts[info.entity_id] = grouped
            owners[info_id] = info.entity_id
    for payload_id, payload in content.payloads.items():
        if payload.information_id in owners:
            manuscripts[owners[payload.information_id]].payloads[payload_id] = payload
    coverage_by_carrier: dict[uuid.UUID, list[tuple[uuid.UUID, dict[str, Any]]]] = defaultdict(list)
    for coverage_id, covered in content.carrier_coverage.items():
        coverage_by_carrier[covered["carrier"]].append((coverage_id, covered))
    result = {}
    for id, name in content.entities.items():
        kinds = content.kinds.get(id, set()) & WRITING_KINDS
        if id in content.writing_biographies:
            kinds = kinds | {"biography"}
        own = bundle(manuscripts[id], id, identities) if id in manuscripts else None
        if not kinds and own is None:
            continue
        telling = content.tellings.get(id)
        placement = content.manuscript_placements.get(id)
        redirect = content.manuscript_redirects.get(id)
        coverage = [
            {
                "id": identity(key),
                **{
                    field: row[field] if field == "position" else identity(row[field])
                    for field in ("entry", "payload", "before", "position")
                },
            }
            for key, row in coverage_by_carrier[id]
        ]
        coverage.sort(key=lambda row: (row["position"], row["id"]))
        result[str(identity(id))] = {
            "name": name,
            "bundle": own,
            "structure": {
                "kinds": sorted(kinds),
                "book": identity(content.editions.get(id)),
                "telling": {
                    "scene": identity(telling["scene"]),
                    "viewpoint": identity(telling["viewpoint"]),
                    "shared": telling["shared"],
                }
                if telling
                else None,
                "placement": {
                    "parent": identity(placement["parent"]),
                    "before": identity(placement["before"]),
                    "position": placement["position"],
                }
                if placement
                else None,
                "redirect": {key: identity(value) for key, value in redirect.items()}
                if redirect
                else None,
                "coverage": coverage,
                "numbering": content.manuscript_numbering.get(id),
                "contents": content.manuscript_contents.get(id),
            },
        }
    return result


def references(record: dict[str, Any]) -> set[str]:
    structure = record["structure"]
    values = [structure.get("book")]
    for field, keys in (
        ("telling", ("scene", "viewpoint")),
        ("placement", ("parent", "before")),
        ("redirect", ("destination", "payload", "child")),
    ):
        row = structure.get(field)
        if row:
            values.extend(row.get(key) for key in keys)
    for row in structure.get("coverage", []):
        values.extend(row.get(key) for key in ("entry", "payload", "before"))
    return {value for value in values if value is not None}


def connected(root: str, *graphs: dict[str, dict[str, Any]]) -> set[str]:
    """Follow both old and new dependencies; removed edges still matter to the review."""
    owners = {}
    for graph in graphs:
        for id, record in graph.items():
            for payload in (record.get("bundle") or {}).get("payloads", []):
                owners[payload["id"]] = id
    edges: dict[str, set[str]] = defaultdict(set)
    known = set().union(*(set(graph) for graph in graphs))
    for graph in graphs:
        for id, record in graph.items():
            for reference in references(record):
                target = owners.get(reference, reference)
                if target in known:
                    edges[id].add(target)
                    edges[target].add(id)
    seen = {root}
    pending = deque([root])
    while pending:
        for next_id in edges[pending.popleft()] - seen:
            seen.add(next_id)
            pending.append(next_id)
    return seen


def validate(graph: dict[str, dict[str, Any]], external: set[str]) -> None:
    """Reject incoherent mixed choices before any SQL mutation."""
    owners: dict[str, str] = {}
    for id, record in graph.items():
        orders = set()
        for payload in (record.get("bundle") or {}).get("payloads", []):
            if payload["id"] in owners or payload["order"] in orders:
                raise ValueError("Each stable element needs one owner and one position.")
            owners[payload["id"]] = id
            orders.add(payload["order"])
    available = set(graph) | set(owners) | external
    parents = {}
    for id, record in graph.items():
        if references(record) - available:
            raise ValueError(
                "A selected change needs writing or a world entry that is not copied. "
                "Review its dependencies first."
            )
        structure = record["structure"]
        kinds = set(structure["kinds"])
        book = structure["book"]
        if book and (
            "edition" not in kinds
            or "book" not in graph.get(book, {}).get("structure", {}).get("kinds", [])
        ):
            raise ValueError("An Edition needs its Book.")
        placement = structure["placement"]
        if placement:
            parent = placement["parent"]
            parent_kinds = set(graph.get(parent, {}).get("structure", {}).get("kinds", []))
            if not kinds & {"chapter", "scene_telling"} or not parent_kinds & {
                "chapter",
                "edition",
            }:
                raise ValueError("Only Chapters and tellings belong in an Edition or Chapter.")
            if placement["before"] and owners.get(placement["before"]) != parent:
                raise ValueError(
                    "A placement needs its stable element in the selected parent manuscript."
                )
            parents[id] = parent
        telling = structure["telling"]
        if telling:
            scene = graph.get(telling["scene"], {}).get("structure", {})
            if "scene" not in scene.get("kinds", []):
                raise ValueError("A telling needs its Scene.")
            if telling["shared"] and record.get("bundle") is not None:
                raise ValueError(
                    "A shared telling uses its Scene manuscript; choose the matching manuscript "
                    "change too."
                )
        for row in structure["coverage"]:
            if "carrier" not in kinds or bool(row["entry"]) == bool(row["payload"]):
                raise ValueError("Carrier coverage needs exactly one entry or stable element.")
            target_id = row["entry"] or owners.get(row["payload"])
            target_kinds = set(graph.get(target_id or "", {}).get("structure", {}).get("kinds", []))
            if not target_kinds & {"edition", "chapter", "scene", "scene_telling"}:
                raise ValueError("Carrier coverage needs an Edition, Chapter, Scene or telling.")
            if row["before"] and owners.get(row["before"]) != id:
                raise ValueError(
                    "Carrier coverage needs its insertion element in the Carrier manuscript."
                )
        redirect = structure["redirect"]
        if redirect and redirect["destination"]:
            destination = redirect["destination"]
            if redirect["payload"] and owners.get(redirect["payload"]) != destination:
                raise ValueError("A joined Chapter needs its destination element.")
            if (
                redirect["child"]
                and (graph[redirect["child"]]["structure"]["placement"] or {}).get("parent")
                != destination
            ):
                raise ValueError("A joined Chapter needs its destination subchapter.")
    # Iterative traversal handles deep chapter outlines without Python recursion.
    done = set()
    for id in parents:
        path = set()
        current = id
        while current in parents and current not in done:
            if current in path:
                raise ValueError("The selected outline contains a Chapter cycle.")
            path.add(current)
            current = parents[current]
        done.update(path)
