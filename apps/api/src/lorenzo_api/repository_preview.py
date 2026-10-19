"""What a reader may look at of a repository before they copy it - ADR 0293, RFC 0038 section 5.

The Owner's switch (`preview` on the profile: `off`, `showcase`, `public`) and who is reading
decide how much of the entries is shown. A *holder* is a library with a grant, invited or from a
copy; a *visitor* is anyone else signed in, with or without a library:

| Reader | `off` | `showcase` | `public` |
| --- | --- | --- | --- |
| Visitor | no entries | the featured entries, with their text | every entry, with its text |
| Holder | every entry's name, kinds, parents | adds the featured text | every entry's text |

"Text" is Everyone's: the information rows that are `is_public`, their descriptions and
pictures, and the stat values the entry holds itself. A row that is GM only, or known to some, is
never read: nothing here looks at who knows a row, only at whether it is Everyone's, so no
preview route can return a row that is not.

What is read is the repository's current release (ADR 0286) for a public one and its rows for a
private one. A release's document is immutable, so its decoded content is kept in a small cache by
release id (`release_cache_entries`), where repeated looks at one repository would each read and
decode a document of tens of megabytes.
"""

import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.config import get_settings
from lorenzo_api.exceptions import PublicRepositoryHasNoReleaseError
from lorenzo_api.models import RepositoryProfile, RepositoryShowcase
from lorenzo_api.release_document_store import ReleaseDocumentNotFoundError, read_release_content
from lorenzo_api.repository_content import Content, load_content
from lorenzo_api.repository_releases import current_release
from lorenzo_api.repository_upstream import is_public
from lorenzo_api.schemas.repositories import EntityKindName
from lorenzo_api.schemas.repository_preview import (
    PreviewDescriptionOut,
    PreviewEntityOut,
    PreviewInformationOut,
    PreviewParentOut,
    PreviewPictureOut,
    PreviewStatOut,
)

__all__ = [
    "SHOWCASE_MAX",
    "Rules",
    "entity_out",
    "picture_of",
    "preview_of",
    "read_content",
    "rules_for",
    "showcase_ids",
]

# How many entries an Owner may feature (RFC 0038 section 5, the cap its open question asks for).
SHOWCASE_MAX = 12

_KIND_ORDER: tuple[EntityKindName, ...] = (
    "item",
    "item_instance",
    "being",
    "character",
    "fact",
    "calendar",
)

Reach = Literal["none", "showcase", "all"]


@dataclass(frozen=True)
class Rules:
    """How much of the entries a reader may look at: whose names (`names`) and whose text."""

    names: Reach
    text: Reach


def rules_for(preview: str, *, holder: bool) -> Rules:
    """The table above."""
    if preview == "public":
        return Rules("all", "all")
    if preview == "showcase":
        return Rules("all" if holder else "showcase", "showcase")
    return Rules("all" if holder else "none", "none")


async def preview_of(session: AsyncSession, repository_id: uuid.UUID) -> str:
    """The Owner's switch, `showcase` for a repository with no profile row. Read inside the
    gated read."""
    value = await session.scalar(
        select(RepositoryProfile.preview).where(RepositoryProfile.tenant_id == repository_id)
    )
    return value or "showcase"


async def showcase_ids(session: AsyncSession, repository_id: uuid.UUID) -> list[uuid.UUID]:
    """The featured entries, in the order the Owner chose. Read inside the gated read."""
    return list(
        await session.scalars(
            select(RepositoryShowcase.entity_id)
            .where(RepositoryShowcase.tenant_id == repository_id)
            .order_by(RepositoryShowcase.position, RepositoryShowcase.entity_id)
        )
    )


# --- The content a preview reads ---------------------------------------------------------------

_cache: OrderedDict[uuid.UUID, Content] = OrderedDict()


def _cached_entries() -> int:
    return sum(len(c.entities) for c in _cache.values())


async def read_content(session: AsyncSession, repository_id: uuid.UUID) -> Content:
    """The repository's content as a preview reads it: the current release's document, kept by
    release id while it fits the cache, for a public repository; its rows for a private one.
    `409 public-repository-has-no-release` for a public one with nothing to read. The caller
    only reads what it returns: it is shared."""
    if not await is_public(session, repository_id):
        return await load_content(session, repository_id)
    release = await current_release(session, repository_id)
    if release is None:
        raise PublicRepositoryHasNoReleaseError(
            detail=f"Repository {repository_id} is public and has not made a release: nothing "
            "to read yet"
        )
    held = _cache.get(release.id)
    if held is not None:
        _cache.move_to_end(release.id)
        return held
    try:
        content = await read_release_content(
            session, tenant_id=repository_id, release_id=release.id
        )
    except ReleaseDocumentNotFoundError:
        raise PublicRepositoryHasNoReleaseError(
            detail=f"Repository {repository_id} is public and its release {release.label} has "
            "no document: nothing to read yet"
        ) from None
    limit = get_settings().release_cache_entries
    if 0 < len(content.entities) <= limit:
        _cache[release.id] = content
        while _cache and _cached_entries() > limit:
            _cache.popitem(last=False)
    return content


# --- An entry --------------------------------------------------------------------------


def _information(content: Content, entity_id: uuid.UUID) -> list[PreviewInformationOut]:
    """The rows of text on the entry that are Everyone's, in their order, with their descriptions
    and pictures. A row that is not `is_public` is skipped before anything of it is looked at."""
    rows = [
        (i, info)
        for i, info in content.information.items()
        if info.entity_id == entity_id and info.is_public
    ]
    rows.sort(key=lambda r: (r[1].order, str(r[0])))
    out: list[PreviewInformationOut] = []
    for information_id, info in rows:
        payloads = sorted(
            (p for p in content.payloads.items() if p[1].information_id == information_id),
            key=lambda p: (p[1].order, str(p[0])),
        )
        out.append(
            PreviewInformationOut(
                id=information_id,
                title=info.title,
                type=info.type,
                descriptions=[
                    PreviewDescriptionOut(
                        locale=str(p.fields["locale"]), content=str(p.fields["content"])
                    )
                    for _, p in payloads
                    if p.kind == "description"
                ],
                pictures=[
                    PreviewPictureOut(id=pid, file_type=str(p.fields["file_type"]))
                    for pid, p in payloads
                    if p.kind == "picture"
                ],
            )
        )
    return out


def _stats(content: Content, entity_id: uuid.UUID) -> list[PreviewStatOut]:
    found: list[tuple[int, int, str, PreviewStatOut]] = []
    for (stat_entity, definition_id), value in content.stats.items():
        if stat_entity != entity_id:
            continue
        definition = content.definitions.get(definition_id)
        if definition is None:
            continue
        group = content.groups.get(definition["group"], {})
        found.append(
            (
                -int(group.get("priority", 0)),
                int(definition.get("position") or 0),
                definition["name"],
                PreviewStatOut(
                    definition_id=definition_id,
                    name=definition["name"],
                    group=str(group.get("name", "")),
                    value=value.as_json(),
                ),
            )
        )
    return [f[3] for f in sorted(found, key=lambda f: f[:3])]


def entity_out(
    content: Content, entity_id: uuid.UUID, *, text: bool, featured: bool
) -> PreviewEntityOut | None:
    """The entry as it is looked at, or none if the content has no such entry. Without `text` the
    entry is its name, kinds and parents only."""
    name = content.entities.get(entity_id)
    if name is None or not content.entry_audiences.get(entity_id, True):
        return None
    kinds = content.kinds.get(entity_id, set())
    return PreviewEntityOut(
        id=entity_id,
        name=name,
        kinds=[k for k in _KIND_ORDER if k in kinds],
        parents=[
            PreviewParentOut(id=parent, name=content.entities[parent])
            for child, parent in content.prototypes
            if child == entity_id
            and parent in content.entities
            and content.entry_audiences.get(parent, True)
        ],
        featured=featured,
        text_visible=text,
        information=_information(content, entity_id) if text else [],
        stats=_stats(content, entity_id) if text else [],
    )


def picture_of(
    content: Content, entity_id: uuid.UUID, payload_id: uuid.UUID
) -> tuple[bytes, str] | None:
    """The bytes and type of a picture on a row of the entry's text that is Everyone's, or none:
    a picture of any other row, of another entry or that does not exist is the same answer."""
    if not content.entry_audiences.get(entity_id, True):
        return None
    payload = content.payloads.get(payload_id)
    if payload is None or payload.kind != "picture":
        return None
    info = content.information.get(payload.information_id)
    if info is None or info.entity_id != entity_id or not info.is_public:
        return None
    return bytes(payload.fields["data"]), str(payload.fields["file_type"])
