import uuid

from pydantic import BaseModel

from lorenzo_api.schemas.entities import EntityKind


class LinkPreviewStatOut(BaseModel):
    """One stat a card shows: its name as the library spells it and its effective value."""

    name: str
    value: int | str | float


class LinkPreviewOut(BaseModel):
    """GET .../entities/{id}/preview (ADR 0264): the small card a link to an entry shows when
    pointed at. `template` names the registry template that chose `stats` and the length of
    `excerpt` (`character`, `being`, `item_instance`, `item` or `entry`, the fallback for a bare
    entry). `excerpt` is plain words from the description the caller may read, empty when there
    is none. `picture_url` is the main picture, the entry's own or an ancestor's, null when it
    has none the caller may see."""

    entity_id: uuid.UUID
    name: str
    slug: str | None
    kinds: list[EntityKind]
    template: str
    picture_url: str | None
    stats: list[LinkPreviewStatOut]
    excerpt: str
