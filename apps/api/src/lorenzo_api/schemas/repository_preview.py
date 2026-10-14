"""The preview of a repository and its showcase - ADR 0293, RFC 0038 section 5."""

import uuid
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from lorenzo_api.schemas.repositories import EntityKindName
from lorenzo_api.schemas.repository_profiles import Preview

__all__ = [
    "PreviewDescriptionOut",
    "PreviewEntityOut",
    "PreviewInformationOut",
    "PreviewOut",
    "PreviewParentOut",
    "PreviewPictureOut",
    "PreviewStatOut",
    "ShowcaseEntryOut",
    "ShowcaseOut",
    "ShowcaseUpdate",
]


class PreviewParentOut(BaseModel):
    id: uuid.UUID
    name: str


class PreviewDescriptionOut(BaseModel):
    """One description of a row of Everyone's text, in a locale."""

    locale: str
    content: str


class PreviewPictureOut(BaseModel):
    """A picture on a row of Everyone's text: `GET .../entities/{id}/pictures/{id}` reads it."""

    id: uuid.UUID
    file_type: str


class PreviewInformationOut(BaseModel):
    """A row of an entry's text that is Everyone's: its title, its descriptions and its pictures.
    A row that is GM only, or known to some only, is never here."""

    id: uuid.UUID
    title: str
    type: str
    descriptions: list[PreviewDescriptionOut]
    pictures: list[PreviewPictureOut]


class PreviewStatOut(BaseModel):
    """A stat value the entry holds itself, with the stat's name and its group (not an inherited
    or a computed one)."""

    definition_id: uuid.UUID
    name: str
    group: str
    value: Any


class PreviewEntityOut(BaseModel):
    """An entry as looked at before copying (ADR 0293): its name, kinds and parents, and, when
    the reader may see its text, the Everyone's text, pictures and stat values on it.
    `text_visible` says whether they were left out because the reader may not see them
    (`information` and `stats` are then empty), and `featured` whether the Owner put it in the
    showcase."""

    id: uuid.UUID
    name: str
    kinds: list[EntityKindName]
    parents: list[PreviewParentOut]
    featured: bool
    text_visible: bool
    information: list[PreviewInformationOut]
    stats: list[PreviewStatOut]


class PreviewOut(BaseModel):
    """`GET .../preview`: the Owner's switch and the entries they feature, in the order they
    chose, as far as this reader may look: none while the reader may see no text."""

    preview: Preview
    entries: list[PreviewEntityOut]


class ShowcaseEntryOut(BaseModel):
    id: uuid.UUID
    name: str


class ShowcaseOut(BaseModel):
    """`GET`/`PUT .../showcase`: the entries an Owner features, in order, and how many they may."""

    limit: int
    entries: list[ShowcaseEntryOut]


class ShowcaseUpdate(BaseModel):
    """`PUT .../showcase`: the entries to feature, in order, replacing the ones there. At most
    `limit` of them, each an entry of this repository, none twice."""

    model_config = ConfigDict(extra="forbid")

    entity_ids: Annotated[list[uuid.UUID], Field(max_length=100)]
