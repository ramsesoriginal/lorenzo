"""Build an explicit, conditional review of connected manuscript records."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import InvalidRepositoryUpdateError, RepositoryNotFoundError
from lorenzo_api.manuscript_graph import connected, references, snapshots, source_identities
from lorenzo_api.models import (
    Information,
    ManuscriptRepositoryUpdate,
    RepositoryCopyLinkEntity,
    User,
)
from lorenzo_api.repository_access import reading_repository
from lorenzo_api.repository_content import Content, load_content
from lorenzo_api.repository_upstream import load_upstream
from lorenzo_api.routers.entities import authorize_information_edit
from lorenzo_api.routers.writing import entry


class ReviewRow(BaseModel):
    id: str
    name: str
    field: Literal["entry", "bundle", "structure"]
    baseline_known: bool
    base: dict[str, Any] | None
    local: dict[str, Any] | None
    upstream: dict[str, Any] | None
    state: Literal["upstream", "local", "matching", "conflict", "unknown", "removed"]
    selectable: bool = True


class CompositionReview(BaseModel):
    version: str
    affected_entries: list[uuid.UUID]
    names: dict[str, str]
    rows: list[ReviewRow]


@dataclass
class Review:
    result: CompositionReview
    links: dict[str, RepositoryCopyLinkEntity]
    identities: dict[str, str]
    local_content: Content
    source_content: Content
    local: dict[str, dict[str, Any]]
    source: dict[str, dict[str, Any]]
    baseline: dict[str, dict[str, Any]]
    connected: set[str]
    repository_id: uuid.UUID


async def review(session: AsyncSession, tenant: uuid.UUID, root: uuid.UUID, user: User) -> Review:
    await entry(session, tenant, root, user)
    root_link = await session.scalar(
        select(RepositoryCopyLinkEntity).where(
            RepositoryCopyLinkEntity.tenant_id == tenant,
            RepositoryCopyLinkEntity.entity_id == root,
        )
    )
    if root_link is None:
        raise InvalidRepositoryUpdateError(detail="This writing was not copied from a repository.")
    links = {
        str(link.source_id): link
        for link in await session.scalars(
            select(RepositoryCopyLinkEntity).where(
                RepositoryCopyLinkEntity.tenant_id == tenant,
                RepositoryCopyLinkEntity.source_tenant_id == root_link.source_tenant_id,
            )
        )
    }
    local_content = await load_content(session, tenant)
    identities = {str(local): str(origin) for local, origin in local_content.links.entity.items()}
    baseline = {}
    for source_id, baseline_link in links.items():
        saved = baseline_link.manuscript_baseline or {}
        identities.update(saved.get("identities", {}))
        identities.update(saved.get("coverage_identities", {}))
        if "structure" in saved:
            baseline[source_id] = {"structure": saved["structure"], "bundle": saved.get("bundle")}
    async with reading_repository(session, root_link.source_tenant_id) as allowed:
        if not allowed:
            raise RepositoryNotFoundError()
        source_content = (await load_upstream(session, root_link.source_tenant_id)).content
    source = snapshots(source_content, source_identities(source_content))
    foreign_sources = {str(origin) for origin in source_content.links.entity.values()}
    local = snapshots(local_content, identities)
    selected = connected(str(root_link.source_id), baseline, local, source)
    local_by_source = {source: uuid.UUID(own) for own, source in identities.items()}
    affected = sorted(
        {
            uuid.UUID(key[6:]) if key.startswith("local:") else local_by_source[key]
            for key in selected & local.keys()
        }
    )
    # A repository review is an editing/history surface, never a way around either gate.
    for entity_id in sorted(affected):
        await entry(session, tenant, entity_id, user)
        info = await session.scalar(
            select(Information).where(
                Information.tenant_id == tenant,
                Information.entity_id == entity_id,
                Information.type == "manuscript",
            )
        )
        if info:
            await authorize_information_edit(
                session, tenant_id=tenant, user=user, information=info, history_read=True
            )
    rows = []
    for source_id in sorted(selected):
        if source_id.startswith("local:") or source_id in foreign_sources:
            continue
        upstream = source.get(source_id)
        mine = local.get(source_id)
        link = links.get(source_id)
        saved = link.manuscript_baseline or {} if link else {}
        name = (mine or upstream or {}).get("name", "Retained writing")
        if upstream is None:
            if mine is not None:
                rows.append(
                    ReviewRow(
                        id=source_id + ":entry",
                        name=name,
                        field="entry",
                        baseline_known=bool(saved),
                        base=baseline.get(source_id),
                        local=mine,
                        upstream=None,
                        state="removed",
                        selectable=False,
                    )
                )
            continue
        if mine is None:
            # A local deletion is not an invitation to silently resurrect it.
            rows.append(
                ReviewRow(
                    id=source_id + ":entry",
                    name=name,
                    field="entry",
                    baseline_known=link is None,
                    base=None,
                    local=None,
                    upstream=upstream,
                    state="upstream" if link is None else "conflict",
                    selectable=link is None,
                )
            )
            continue
        for field in ("bundle", "structure"):
            known = field in saved
            base, own, incoming = saved.get(field), mine[field], upstream[field]
            if known and base == incoming:
                continue
            if not known and own == incoming:
                # Still offer explicit adoption of this previously unknown baseline.
                state = "unknown"
            elif not known:
                state = "unknown"
            elif own == incoming:
                state = "matching"
            elif own == base:
                state = "upstream"
            else:
                state = "conflict"
            rows.append(
                ReviewRow(
                    id=source_id + ":" + field,
                    name=name,
                    field=field,
                    baseline_known=known,
                    base=base,
                    local=own,
                    upstream=incoming,
                    state=state,
                )
            )
    last_review = await session.scalar(
        select(ManuscriptRepositoryUpdate.id)
        .where(
            ManuscriptRepositoryUpdate.tenant_id == tenant,
            ManuscriptRepositoryUpdate.entry_id == root,
        )
        .order_by(
            ManuscriptRepositoryUpdate.created_at.desc(), ManuscriptRepositoryUpdate.id.desc()
        )
        .limit(1)
    )
    # Include dependency state, including unchanged rows, in the conditional token.
    version = (
        '"'
        + hashlib.sha256(
            json.dumps(
                [
                    {
                        key: link.manuscript_baseline
                        for key, link in links.items()
                        if key in selected
                    },
                    {key: value for key, value in local.items() if key in selected},
                    {key: value for key, value in source.items() if key in selected},
                    str(last_review),
                ],
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        + '"'
    )
    names = {
        key: record["name"]
        for graph in (source, local)
        for key, record in graph.items()
        if key in selected
    }
    source_map = source_identities(source_content)
    source_names = {source_map[str(key)]: name for key, name in source_content.entities.items()}
    for key in selected & source.keys():
        for reference in references(source[key]):
            if reference in source_names:
                names.setdefault(reference, source_names[reference])
    for graph in (source, local):
        for key, record in graph.items():
            if key not in selected:
                continue
            for index, payload in enumerate((record.get("bundle") or {}).get("payloads", []), 1):
                names[payload["id"]] = f"Writing element {index} in {record['name']}"
    return Review(
        CompositionReview(version=version, affected_entries=affected, names=names, rows=rows),
        links,
        identities,
        local_content,
        source_content,
        local,
        source,
        baseline,
        selected,
        root_link.source_tenant_id,
    )
