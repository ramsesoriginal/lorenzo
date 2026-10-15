"""The flips between private and public - ADR 0290, RFC 0038 section 7."""

import uuid
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from lorenzo_api.schemas.discover import PublisherOut
from lorenzo_api.schemas.repositories import BuiltOnBehindOut, PublishRequest
from lorenzo_api.schemas.repository_profiles import SUMMARY_MAX, Preview, Visibility, _words

__all__ = [
    "BuiltOnPublicOut",
    "FlipCheckOut",
    "MadePrivateOut",
    "MakePublicRequest",
    "PublicDependentOut",
]


class MakePublicRequest(PublishRequest):
    """`PUT .../public`: the first public release, as `PUT .../published` makes one (`label`,
    `notes`, `breaking`, `acknowledge_breaking`), and what the repository says about itself as
    it goes public. `summary` is kept if given (a repository must have one, here or already);
    `preview` is the Owner's switch for what a visitor may look at before copying (RFC 0038
    section 5), `showcase` unless they choose.

    `accept_terms` is the terms line the Owner agrees to in the dialog, and it must be `true`
    (`422 terms-not-accepted` otherwise; a client that does not send it is refused). Draft
    wording, the maintainer's to approve: I have the right to publish this repository.
    Publishing cannot be recalled: libraries that copied it keep their copies."""

    preview: Preview = "showcase"
    summary: Annotated[str, Field(max_length=2000)] | None = None
    accept_terms: bool = False

    @field_validator("summary")
    @classmethod
    def _summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = _words(value)
        if len(text) > SUMMARY_MAX:
            raise ValueError(f"A summary is at most {SUMMARY_MAX} characters")
        return text


class BuiltOnPublicOut(BaseModel):
    """A repository this one is built on that is not public, and whether the caller owns it (so
    the dialog can offer to make it public first)."""

    id: uuid.UUID
    name: str
    owned: bool


class PublicDependentOut(BaseModel):
    """A public repository built on this one, and whether the caller owns it."""

    id: uuid.UUID
    name: str
    owned: bool


class FlipCheckOut(BaseModel):
    """`GET .../flip-check` (ADR 0290): what a flip of this repository would run into, for the
    dialog to say before the Owner asks. `available` is false while the deployment does not
    accept public repositories (RFC 0038 section 1). Going public needs `built_on_not_public` and
    `built_on_behind` empty and a summary; going private needs `public_dependents` empty and says
    how many libraries it cuts off (`public_libraries`, which copied it by themselves, against
    `invited_libraries`, which it invited and keeps)."""

    available: bool
    visibility: Visibility
    has_summary: bool
    built_on_not_public: list[BuiltOnPublicOut]
    built_on_behind: list[BuiltOnBehindOut]
    public_dependents: list[PublicDependentOut]
    public_libraries: int
    invited_libraries: int
    # The Owners' account names a storefront will say published it (ADR 0299): the dialog shows
    # them, since the repository is published as them and nothing else.
    publishers: list[PublisherOut]


class MadePrivateOut(BaseModel):
    """`DELETE .../public`: how many libraries' own grants were revoked."""

    revoked: int
