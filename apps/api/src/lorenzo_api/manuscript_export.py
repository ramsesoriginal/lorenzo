"""A bounded, permission-projected saved manuscript export (ADR 0478)."""

import base64
import hashlib
import io
import json
import uuid
import zipfile
from typing import Any, Literal

from fastapi import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.chapter_numbering import projection
from lorenzo_api.dependencies import CurrentUser
from lorenzo_api.exceptions import ManuscriptExportError
from lorenzo_api.manuscript_contents import contents_tree, visible_contents
from lorenzo_api.models import (
    Entity,
    Information,
    ManuscriptContents,
    ManuscriptNumbering,
    Payload,
    PayloadDescription,
    PayloadPicture,
)
from lorenzo_api.routers.chapter_numbering import read_numbering
from lorenzo_api.routers.manuscript_contents import read_contents
from lorenzo_api.routers.writing import Element, JoinedDestination, result, writing_kind
from lorenzo_api.routers.writing_reviews import scope, sources

MAX_ENTRIES = 5_000
MAX_OCCURRENCES = 20_000
MAX_BYTES = 50 * 1024 * 1024


class ExportPayload(BaseModel):
    id: uuid.UUID
    kind: Literal["text", "picture"]
    information_id: uuid.UUID
    locale: str | None = None
    content: str | None = None
    media_type: str | None = None
    data: str | None = None
    sha256: str


class ExportEntry(BaseModel):
    id: uuid.UUID
    name: str
    kind: str
    elements: list[Element]
    scene_id: uuid.UUID | None = None
    viewpoint_id: uuid.UUID | None = None
    uses_scene_manuscript: bool = False
    joined: bool = False
    joined_destination: JoinedDestination | None = None
    number: str | None = None
    numbering: dict[str, Any] | None = None
    contents_settings: dict[str, Any] | None = None
    contents: list[dict[str, Any]] | None = None


class ExportSnapshot(BaseModel):
    format: Literal["lorenzo-writing/1"] = "lorenzo-writing/1"
    root_id: uuid.UUID
    version: str = ""
    entries: list[ExportEntry]
    payloads: list[ExportPayload] = Field(default_factory=list)


def too_large() -> ManuscriptExportError:
    return ManuscriptExportError(
        detail="This writing is too large to export together. Choose a smaller section."
    )


async def ordinary_entries(
    session: AsyncSession, tenant: uuid.UUID, root: uuid.UUID, user: CurrentUser
) -> list[ExportEntry]:
    loaded: dict[uuid.UUID, ExportEntry] = {}
    whole: set[uuid.UUID] = set()
    selected: dict[uuid.UUID, set[uuid.UUID]] = {}
    tasks: list[tuple[uuid.UUID, uuid.UUID | None]] = [(root, None)]
    while tasks:
        id, payload = tasks.pop()
        if id in whole or (payload is not None and payload in selected.get(id, set())):
            continue
        if payload is None:
            whole.add(id)
        else:
            selected.setdefault(id, set()).add(payload)
        if id not in loaded:
            if len(loaded) >= MAX_ENTRIES:
                raise too_large()
            view = await result(session, tenant, id, user, Response())
            if (
                sum(len(entry.elements) for entry in loaded.values()) + len(view.elements)
                > MAX_OCCURRENCES
            ):
                raise too_large()
            if view.kind == "book":
                raise ManuscriptExportError(detail="Choose an Edition of this Book to export.")
            loaded[id] = ExportEntry(
                id=id,
                name=view.name,
                kind=view.kind,
                elements=view.elements,
                scene_id=view.scene_id,
                viewpoint_id=view.viewpoint_id,
                uses_scene_manuscript=view.uses_scene_manuscript,
                joined=view.joined,
                joined_destination=view.joined_destination,
            )
        if payload is None:
            for element in reversed(loaded[id].elements):
                if element.kind == "coverage" and element.target_id:
                    tasks.append((element.target_id, element.payload_id))
                elif element.kind in {"chapter", "scene_telling"}:
                    tasks.append((element.id, None))
    for id, entry in loaded.items():
        if id not in whole:
            entry.elements = [
                item
                for item in entry.elements
                if item.kind == "payload" and item.id in selected[id]
            ]
        if entry.kind in {"edition", "chapter"} and not entry.joined:
            numbers = await read_numbering(session, tenant, id, user, Response())
            entry.number = numbers.labels.get(id)
            contents = await read_contents(session, tenant, id, user, Response())
            if (
                id == contents.root_id and contents.root_enabled
            ) or id in contents.contents_chapters:
                entry.contents = [
                    row.model_dump(mode="json") for row in contents.rows if row.id in loaded
                ]
    return list(loaded.values())


async def review_entries(
    session: AsyncSession, tenant: uuid.UUID, root: uuid.UUID, user: CurrentUser
) -> list[ExportEntry]:
    # Reuse the review grant's authority, but never load notes or unbounded prose.
    _, _, reachable, placements = await scope(session, tenant, root, user)
    if len(reachable) > MAX_ENTRIES:
        raise too_large()
    manuscript_sources = await sources(session, tenant, reachable)
    rows = list(
        await session.scalars(
            select(Entity)
            .where(Entity.tenant_id == tenant, Entity.id.in_(reachable))
            .order_by(Entity.id)
        )
    )
    kinds = {item.id: await writing_kind(session, item.id) for item in rows}
    payloads = list(
        await session.execute(
            select(Payload.id, Information.entity_id)
            .join(Information, Information.id == Payload.information_id)
            .where(
                Payload.tenant_id == tenant,
                Information.tenant_id == tenant,
                Information.type == "manuscript",
                Information.entity_id.in_(set(manuscript_sources.values())),
            )
            .order_by(Payload.order, Payload.id)
            .limit(MAX_OCCURRENCES + 1)
        )
    )
    if len(payloads) > MAX_OCCURRENCES:
        raise too_large()
    numbers = await projection(session, tenant, root, reachable, placements)
    presentation, contents = await contents_tree(session, tenant, root, reachable, placements)
    entries = []
    for item in rows:
        elements: list[Element] = []
        children: dict[uuid.UUID | None, list[Element]] = {}
        for link in placements:
            if link.parent_entity_id == item.id:
                children.setdefault(link.before_payload_id, []).append(
                    Element(
                        id=link.child_entity_id,
                        kind="scene_telling"
                        if kinds[link.child_entity_id] == "scene_telling"
                        else "chapter",
                    )
                )
        for payload_id, source_id in payloads:
            if source_id == manuscript_sources[item.id]:
                elements.extend(children.get(payload_id, []))
                elements.append(Element(id=payload_id, kind="payload"))
        elements.extend(children.get(None, []))
        selected_contents = visible_contents(root, item.id, presentation, contents)
        entries.append(
            ExportEntry(
                id=item.id,
                name=item.name,
                kind=kinds[item.id],
                elements=elements,
                uses_scene_manuscript=manuscript_sources[item.id] != item.id,
                number=numbers.get(item.id),
                contents=[row.model_dump(mode="json") for row in selected_contents]
                if selected_contents is not None
                else None,
            )
        )
    return entries


def check_occurrences(snapshot: ExportSnapshot) -> dict[uuid.UUID, int]:
    entries = {entry.id: entry for entry in snapshot.entries}
    path: set[uuid.UUID] = set()
    tasks: list[tuple[uuid.UUID, uuid.UUID | None, bool]] = [(snapshot.root_id, None, False)]
    count = 0
    payload_counts: dict[uuid.UUID, int] = {}
    while tasks:
        id, payload, leaving = tasks.pop()
        if leaving:
            path.remove(id)
            continue
        count += 1
        if count > MAX_OCCURRENCES:
            raise too_large()
        if id in path:
            raise ManuscriptExportError(
                detail="This writing contains a cycle and cannot be exported."
            )
        path.add(id)
        tasks.append((id, payload, True))
        for element in reversed(entries[id].elements):
            if payload is not None and element.id != payload:
                continue
            if element.kind == "payload":
                payload_counts[element.id] = payload_counts.get(element.id, 0) + 1
                count += 1
                if count > MAX_OCCURRENCES:
                    raise too_large()
            elif element.kind == "coverage" and element.target_id:
                tasks.append((element.target_id, element.payload_id, False))
            elif element.kind in {"chapter", "scene_telling"}:
                tasks.append((element.id, None, False))

    return payload_counts


async def assemble(
    session: AsyncSession, tenant: uuid.UUID, root: uuid.UUID, user: CurrentUser, *, review: bool
) -> ExportSnapshot:
    entries = await (review_entries if review else ordinary_entries)(session, tenant, root, user)
    snapshot = ExportSnapshot(root_id=root, entries=entries)
    occurrences = check_occurrences(snapshot)
    entry_ids = {entry.id for entry in entries}
    payload_ids = {el.id for entry in entries for el in entry.elements if el.kind == "payload"}
    for model, field in (
        (ManuscriptNumbering, "numbering"),
        (ManuscriptContents, "contents_settings"),
    ):
        settings = {
            row.entity_id: row.settings
            for row in await session.execute(
                select(model.entity_id, model.settings).where(
                    model.tenant_id == tenant, model.entity_id.in_(entry_ids)
                )
            )
        }
        for entry in entries:
            setattr(entry, field, settings.get(entry.id))
    # Refuse oversized binary/text data before transferring it from PostgreSQL.
    sizes = await session.execute(
        select(
            Payload.id,
            func.coalesce(func.octet_length(PayloadDescription.content), 0)
            + func.coalesce(func.octet_length(PayloadPicture.data), 0),
        )
        .select_from(Payload)
        .outerjoin(PayloadDescription, PayloadDescription.payload_id == Payload.id)
        .outerjoin(PayloadPicture, PayloadPicture.payload_id == Payload.id)
        .where(Payload.tenant_id == tenant, Payload.id.in_(payload_ids))
    )
    if sum(size * occurrences[id] for id, size in sizes) > MAX_BYTES:
        raise too_large()
    size = 0
    rows = await session.execute(
        select(Payload, PayloadDescription, PayloadPicture)
        .join(Information, Information.id == Payload.information_id)
        .outerjoin(PayloadDescription, PayloadDescription.payload_id == Payload.id)
        .outerjoin(PayloadPicture, PayloadPicture.payload_id == Payload.id)
        .where(
            Payload.tenant_id == tenant,
            Information.tenant_id == tenant,
            Information.type == "manuscript",
            Payload.id.in_(payload_ids),
        )
        .order_by(Payload.id)
    )
    for payload, description, picture in rows:
        if description is not None:
            raw = description.content.encode("utf-8")
            item = ExportPayload(
                id=payload.id,
                information_id=payload.information_id,
                kind="text",
                content=description.content,
                locale=description.locale,
                sha256=hashlib.sha256(raw).hexdigest(),
            )
        elif picture is not None:
            raw = picture.data
            item = ExportPayload(
                id=payload.id,
                information_id=payload.information_id,
                kind="picture",
                media_type=picture.file_type,
                data=base64.b64encode(raw).decode("ascii"),
                sha256=hashlib.sha256(raw).hexdigest(),
            )
        else:
            raise ManuscriptExportError(detail="This manuscript contains an unsupported element.")
        size += len(raw) * occurrences[payload.id]
        if size > MAX_BYTES:
            raise too_large()
        snapshot.payloads.append(item)
    found = {payload.id for payload in snapshot.payloads}
    if found != payload_ids:
        raise ManuscriptExportError(detail="This writing changed. Open the export preview again.")
    # Do not include identifiers of world references outside the selected export graph.
    for entry in entries:
        if entry.scene_id not in entry_ids:
            entry.scene_id = None
        if entry.viewpoint_id not in entry_ids:
            entry.viewpoint_id = None
    snapshot.version = (
        'W/"'
        + hashlib.sha256(snapshot.model_dump_json(exclude={"version"}).encode("utf-8")).hexdigest()
        + '"'
    )
    return snapshot


def source_archive(snapshot: ExportSnapshot) -> bytes:
    manifest = snapshot.model_dump(mode="json")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for payload in manifest["payloads"]:
            content = payload.pop("content")
            data = payload.pop("data")
            if payload["kind"] == "text":
                path = f"text/{payload['id']}.lorenzoscript"
                raw = content.encode("utf-8")
            else:
                extension = {
                    "image/png": "png",
                    "image/jpeg": "jpg",
                    "image/webp": "webp",
                    "image/gif": "gif",
                    "image/svg+xml": "svg",
                }.get(payload["media_type"], "bin")
                path = f"pictures/{payload['id']}.{extension}"
                raw = base64.b64decode(data, validate=True)
            payload["path"] = path
            archive.writestr(path, raw)
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr(
            "README.txt",
            (
                "Lorenzo Writing source archive (lorenzo-writing/1)\n\n"
                "manifest.json records the selected, authorized saved composition and stable IDs.\n"
                "Text files are exact UTF-8 LorenzoScript; "
                "picture files retain their original bytes.\n"
                "Follow entry elements in order; "
                "coverage may repeat an entry or select one payload.\n"
                "Notes, private material you cannot read, "
                "history and unsent drafts are not included.\n"
                "This is manuscript source, not a library backup. An importer is not provided.\n"
            ),
        )
    return output.getvalue()
