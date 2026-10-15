"""A repository's profile - ADR 0213, RFC 0038 §2. What a request may say, and the limits it is
kept to: one place for them, so the ADR and the tests have one set of numbers to name."""

import re
from datetime import datetime
from typing import Annotated, Any, Literal, Self
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

__all__ = [
    "CreditIn",
    "CreditOut",
    "DelistedOut",
    "LicenceIn",
    "LicenceOut",
    "MemberProfileOut",
    "RepositoryProfileOut",
    "RepositoryProfileUpdate",
]

Visibility = Literal["private", "public"]
Preview = Literal["off", "showcase", "public"]

SUMMARY_MAX = 280
LICENCE_LABEL_MAX = 80
CREDITS_MAX = 20
CREDIT_NAME_MAX = 80
CREDIT_ROLE_MAX = 60
TAGS_MAX = 12
TAG_MAX = 32
SYSTEM_MAX = 40
LANGUAGES_MAX = 8
URL_MAX = 500

# A language code as the content is tagged with it: `en`, `de`, `pt-br`, `zh-hans`.
_LANGUAGE = re.compile(r"^[a-z]{2,3}(-[a-z0-9]{2,8}){0,2}$")


def _words(value: str) -> str:
    """Whitespace runs, newlines included, become one space; the ends are dropped. A profile's
    one-line fields never hold a line break, and nothing that is not printable."""
    text = " ".join(value.split())
    if not text.isprintable():
        raise ValueError("Use plain text, without control characters")
    return text


def _plain(limit: int, what: str) -> Any:
    def check(value: str) -> str:
        text = _words(value)
        if not text:
            raise ValueError(f"{what} can't be empty")
        if len(text) > limit:
            raise ValueError(f"{what} is at most {limit} characters")
        return text

    return AfterValidator(check)


def _https(value: str) -> str:
    """A link is stored only when it is an `https` address with a host and no password in it
    (RFC 0038 §2): no other scheme is kept, so none can be put on a page as a link."""
    text = value.strip()
    if len(text) > URL_MAX:
        raise ValueError(f"A link is at most {URL_MAX} characters")
    if not text.lower().startswith("https://"):
        raise ValueError("A link must start with https://")
    if any(ch.isspace() or not ch.isprintable() for ch in text):
        raise ValueError("A link can't hold spaces")
    try:
        parts = urlsplit(text)
        host = parts.hostname
    except ValueError as error:
        raise ValueError("That isn't a web address") from error
    if not host:
        raise ValueError("A link needs a host, as in https://example.com")
    if parts.username is not None or parts.password is not None:
        raise ValueError("A link can't hold a user name or a password")
    return "https://" + text[len("https://") :]


Link = Annotated[str, AfterValidator(_https)]


class LicenceIn(BaseModel):
    """A licence: the label (a name from a short list, or the author's words) and, optionally,
    a link to its text. Having none is `licence: null`, which says "no licence stated"."""

    model_config = ConfigDict(extra="forbid")

    label: Annotated[str, _plain(LICENCE_LABEL_MAX, "A licence label")]
    url: Link | None = None


class LicenceOut(BaseModel):
    label: str
    url: str | None


class CreditIn(BaseModel):
    """Who made some of it: a name, what they did, and optionally a link. Not the publisher,
    which is the Owners' account names (RFC 0038 §6)."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, _plain(CREDIT_NAME_MAX, "A name")]
    role: Annotated[str, _plain(CREDIT_ROLE_MAX, "A role")] | None = None
    url: Link | None = None

    @field_validator("role", mode="before")
    @classmethod
    def _blank_role_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value


class CreditOut(BaseModel):
    name: str
    role: str | None
    url: str | None


class RepositoryProfileUpdate(BaseModel):
    """`PATCH .../profile`. Every field is optional and a field left out is unchanged; `null`
    clears the licence and the system, `[]` clears a list. An unknown field is refused. What
    is kept: tags in lower case without repeats, a system and a summary on one line,
    languages as lower-case codes."""

    model_config = ConfigDict(extra="forbid")

    visibility: Visibility | None = None
    preview: Preview | None = None
    summary: Annotated[str, Field(max_length=2000)] | None = None
    licence: LicenceIn | None = None
    credits: Annotated[list[CreditIn], Field(max_length=CREDITS_MAX)] | None = None
    tags: Annotated[list[str], Field(max_length=100)] | None = None
    system: Annotated[str, Field(max_length=2000)] | None = None
    languages: Annotated[list[str], Field(max_length=100)] | None = None

    @field_validator("summary")
    @classmethod
    def _summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = _words(value)
        if len(text) > SUMMARY_MAX:
            raise ValueError(f"A summary is at most {SUMMARY_MAX} characters")
        return text

    @field_validator("system")
    @classmethod
    def _system(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = _words(value)
        if len(text) > SYSTEM_MAX:
            raise ValueError(f"A system is at most {SYSTEM_MAX} characters")
        return text or None

    @field_validator("tags")
    @classmethod
    def _tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        tags: list[str] = []
        for raw in value:
            tag = _words(raw).lower()
            if not tag:
                raise ValueError("A tag can't be empty")
            if len(tag) > TAG_MAX:
                raise ValueError(f"A tag is at most {TAG_MAX} characters")
            if tag not in tags:
                tags.append(tag)
        if len(tags) > TAGS_MAX:
            raise ValueError(f"At most {TAGS_MAX} tags")
        return tags

    @field_validator("languages")
    @classmethod
    def _languages(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        codes: list[str] = []
        for raw in value:
            code = raw.strip().lower()
            if not _LANGUAGE.match(code):
                raise ValueError(f"'{raw}' isn't a language code such as en, de or pt-br")
            if code not in codes:
                codes.append(code)
        if len(codes) > LANGUAGES_MAX:
            raise ValueError(f"At most {LANGUAGES_MAX} languages")
        return codes

    @model_validator(mode="after")
    def _only_a_licence_and_a_system_are_cleared_by_null(self) -> Self:
        for name in ("visibility", "preview", "summary", "credits", "tags", "languages"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} can't be null; leave it out to keep it")
        return self


class DelistedOut(BaseModel):
    """That the platform's operators took a repository off Discover, and why: read by the
    repository's own members and by nobody else (ADR 0297). Never who: the operators are the
    platform's, not a person."""

    reason: str
    at: datetime


class RepositoryProfileOut(BaseModel):
    """A repository's profile: what the Owner says of it, and whether it has a cover (the
    picture is `GET .../profile/cover`)."""

    visibility: Visibility
    preview: Preview
    summary: str
    licence: LicenceOut | None
    credits: list[CreditOut]
    tags: list[str]
    system: str | None
    languages: list[str]
    has_cover: bool
    updated_at: datetime


class MemberProfileOut(RepositoryProfileOut):
    """What the repository's own members read of its profile (ADR 0297): the profile, and
    `delisted` while the platform's operators have it off Discover (`null` while it is listed).
    A visitor's and a library's view are `RepositoryProfileOut` and have no such field at all:
    they cannot read a delisted repository."""

    delisted: DelistedOut | None = None
