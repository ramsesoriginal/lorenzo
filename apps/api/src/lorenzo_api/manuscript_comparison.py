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
    result = {}
    for info_id, row in manuscripts.items():
        value = bundle(grouped[info_id], row.entity_id)
        assert value is not None
        result[row.entity_id] = {
            "format": 1,
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
