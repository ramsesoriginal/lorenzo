"""Direct manuscript snapshots for read-only repository comparison (ADR 0398)."""

import hashlib
import uuid
from typing import Any, Literal

from lorenzo_api.repository_content import Content


def bundle(
    content: Content, entity: uuid.UUID, identities: dict[str, str] | None = None
) -> dict[str, Any] | None:
    info = next(
        (
            (id, row)
            for id, row in content.information.items()
            if row.entity_id == entity and row.type == "manuscript"
        ),
        None,
    )
    if info is None:
        return None
    info_id, row = info
    payloads = []
    for id, payload in content.payloads.items():
        if payload.information_id != info_id:
            continue
        identity = str(id) if identities is None else identities.get(str(id), "local:" + str(id))
        fields: dict[str, Any] = {}
        for key, value in payload.fields.items():
            if isinstance(value, bytes):
                fields[key + "_sha256"] = hashlib.sha256(value).hexdigest()
            elif value is None or isinstance(value, str | int | float | bool):
                fields[key] = value
            else:
                fields[key] = str(value)
        payloads.append(
            {"id": identity, "order": payload.order, "kind": payload.kind, "fields": fields}
        )
    payloads.sort(key=lambda p: (p["order"], p["id"]))
    return {"title": row.title, "payloads": payloads}


def copy_baselines(
    content: Content,
    local_information: dict[uuid.UUID, uuid.UUID],
    local_payloads: dict[uuid.UUID, uuid.UUID],
) -> dict[uuid.UUID, dict[str, Any]]:
    # Build this once per copy step, rather than scanning all notes and payloads for every entry.
    manuscripts = {
        info_id: row
        for info_id, row in content.information.items()
        if row.type == "manuscript" and info_id in local_information
    }
    grouped = {info_id: Content(tenant_id=content.tenant_id) for info_id in manuscripts}
    for info_id, row in manuscripts.items():
        grouped[info_id].information[info_id] = row
    for payload_id, payload in content.payloads.items():
        if payload.information_id in grouped:
            grouped[payload.information_id].payloads[payload_id] = payload
    contexts = chapter_contexts(content)
    result = {}
    for info_id, row in manuscripts.items():
        value = bundle(grouped[info_id], row.entity_id)
        assert value is not None
        result[row.entity_id] = {
            "format": 1,
            "composition": contexts.get(row.entity_id),
            "bundle": value,
            "information_id": str(local_information[info_id]),
            "identities": {
                str(local_payloads[payload_id]): str(payload_id)
                for payload_id in grouped[info_id].payloads
                if payload_id in local_payloads
            },
        }
    return result


def state(
    base: dict[str, Any], local: dict[str, Any], upstream: dict[str, Any] | None
) -> Literal["unchanged", "local", "upstream", "matching", "conflict"]:
    if local == upstream:
        return "unchanged" if local == base else "matching"
    if upstream == base:
        return "local"
    if local == base:
        return "upstream"
    return "conflict"


def standalone(content: Content, entity: uuid.UUID) -> bool:
    if content.kinds.get(entity) not in ({"scene"}, {"chapter"}):
        return False
    if entity in content.manuscript_placements or any(
        row["parent"] == entity for row in content.manuscript_placements.values()
    ):
        return False
    if entity in content.tellings or any(
        row["scene"] == entity for row in content.tellings.values()
    ):
        return False
    if any(entity in (row["carrier"], row["entry"]) for row in content.carrier_coverage.values()):
        return False
    return not (
        entity in content.manuscript_redirects
        or any(
            entity in (row["destination"], row["child"])
            for row in content.manuscript_redirects.values()
        )
    )


def text_shape(value: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {**payload, "fields": {} if payload["kind"] == "description" else payload["fields"]}
        for payload in value["payloads"]
    ]


def update_reason(
    base: dict[str, Any], local: dict[str, Any], upstream: dict[str, Any] | None, independent: bool
) -> str | None:
    if not independent:
        return "This composition has changed, has no saved context, or needs a structural review."
    if upstream is None:
        return "The repository manuscript was removed. Your copy is kept."
    if not (text_shape(base) == text_shape(local) == text_shape(upstream)):
        return "Payload structure or attachments changed. This update needs a structural review."
    if upstream == base:
        return "There is no new repository writing to accept."
    return None


def chapter_contexts(
    content: Content, identities: dict[str, str] | None = None
) -> dict[uuid.UUID, dict[str, Any]]:
    """Eligible leaf placements in one linear pass; ids are in the source namespace."""

    def identity(value: uuid.UUID | None) -> str | None:
        if value is None:
            return None
        return (
            str(value) if identities is None else identities.get(str(value), "local:" + str(value))
        )

    dependent = set(content.tellings)
    dependent.update(row["scene"] for row in content.tellings.values())
    for row in content.carrier_coverage.values():
        dependent.update((row["carrier"], row["entry"]))
    dependent.update(content.manuscript_redirects)
    for row in content.manuscript_redirects.values():
        dependent.update((row["destination"], row["child"]))
    parents = {row["parent"] for row in content.manuscript_placements.values()}
    result = {}
    for chapter, placement in content.manuscript_placements.items():
        edition = placement["parent"]
        book = content.editions.get(edition)
        if (
            content.kinds.get(chapter) != {"chapter"}
            or content.kinds.get(edition) != {"edition"}
            or book is None
            or content.kinds.get(book) != {"book"}
            or chapter in parents
            or any(entry in dependent for entry in (chapter, edition, book))
        ):
            continue
        result[chapter] = {
            "edition": identity(edition),
            "book": identity(book),
            "before": identity(placement["before"]),
            "position": placement["position"],
        }
    return result
