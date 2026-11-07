"""The flips between private, protected and public - ADR 0290, ADR 0434, RFC 0038 section 7."""

import uuid
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from lorenzo_api.schemas.discover import PublisherOut
from lorenzo_api.schemas.repositories import (
    BuiltOnBehindOut,
    IncludableOut,
    InclusionName,
    PublishRequest,
    ReleaseAuthoredOut,
)
from lorenzo_api.schemas.repository_profiles import (
    SUMMARY_MAX,
    DelistedOut,
    DeprecatedOut,
    Preview,
    Visibility,
    _words,
)

__all__ = [
    "BuiltOnPublicOut",
    "BuiltOnSourceOut",
    "FlipCheckOut",
    "MadePrivateOut",
    "MadeProtectedOut",
    "MakeProtectedRequest",
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
    (`422 terms-not-accepted` otherwise; a client that does not send it is refused). The wording is
    the maintainer's, approved on 2026-10-16: I have the right to publish this repository.
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


class MakeProtectedRequest(PublishRequest):
    """`PUT .../protected` (ADR 0434): the first release of a private repository made protected,
    as `PUT .../published` makes one (`label`, `notes`, `breaking`, `acknowledge_breaking`). A
    protected repository needs no summary and no terms line: nothing says what it is to anybody
    who does not hold it. `acknowledge_revokes` is for a public repository made protected: the
    libraries that copied it by themselves are told what they lose, as for going private."""

    acknowledge_revokes: bool = False


class BuiltOnPublicOut(BaseModel):
    """A repository this one is built on that cannot be reached (it is neither public nor
    protected, and is not included), and whether the caller owns it (so the dialog can offer to
    make it public first)."""

    id: uuid.UUID
    name: str
    owned: bool


class BuiltOnSourceOut(BaseModel):
    """A repository this one is built on, as its Owner sees it before making this one public (ADR
    0431): whether it is public, whether the caller owns it, how this repository carries it
    (`inclusion`), whether the caller may include it and why (`includable`), and how the current
    public release carried it (`in_release`, null when none did or it was built on later). A
    private one that is not included stops this repository being made public; one that is
    included does not, and says so."""

    id: uuid.UUID
    name: str
    public: bool
    owned: bool
    inclusion: InclusionName
    includable: IncludableOut
    in_release: InclusionName | None
    # It is protected (ADR 0434): a library reads it only as a step of the copy of a public
    # repository built on it. `public` and `protected` are both false for a source this repository
    # cannot read just now.
    protected: bool = False
    # Whether the caller may keep it separate and visible and why (`showable`, as `includable`), and
    # whether its terms say a repository built on it may show it at all (`may_be_shown`): a source
    # that says no leaves `include` as the way to carry it, unless the caller owns it.
    showable: IncludableOut | None = None
    may_be_shown: bool = True


class PublicDependentOut(BaseModel):
    """A public or protected repository built on this one, and whether the caller owns it."""

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
    # Whether Discover lists it while it is public (ADR 0432); true for a repository that is not.
    listed: bool = True
    built_on_not_public: list[BuiltOnPublicOut]
    built_on_behind: list[BuiltOnBehindOut]
    # Every repository it is built on, with the choice made for each (ADR 0431).
    built_on: list[BuiltOnSourceOut]
    public_dependents: list[PublicDependentOut]
    public_libraries: int
    invited_libraries: int
    # The Owners' account names a storefront will say published it (ADR 0299): the dialog shows
    # them, since the repository is published as them and nothing else.
    publishers: list[PublisherOut]
    # Set while the platform's operators have the repository off Discover (ADR 0303): it cannot be
    # made public until they list it again. Owner only, like the rest of the check.
    delisted: DelistedOut | None = None
    # Set while the Owner has the repository retired (ADR 0384): it cannot be made public until it
    # is brought back. Owner only, like the rest of the check.
    deprecated: DeprecatedOut | None = None


class MadePrivateOut(BaseModel):
    """`DELETE .../public`: how many libraries' own grants were revoked."""

    revoked: int


class MadeProtectedOut(BaseModel):
    """`PUT .../protected` (ADR 0434): the release made with the flip for a private repository (none
    for a public one, which has its releases already) and how many grants libraries had given
    themselves while it was public, which are `protected` ones now."""

    release: ReleaseAuthoredOut | None
    turned: int
