"""Every tenant table, once, with what a copy of a repository needs to know about it (ADR 0218).

A table that holds tenant data is listed here, in the order a copy inserts it. From this one list
come the two sets of `repository_access` (the tables carrying the `repository_read` policy and the
rest, ADR 0118), the tables `repository_copying` writes (`write_rows`) and the copy links it keeps
and drops (`forget_copy`), and the tests that say a table has been classified, has a place in a
copy, and is carried by one.

It is deliberately thin. It lists; it does not generate. Which ids a copy re-targets, what
collides, and which fields the update diff shows or applies stay hand-written in
`repository_copying` and `repository_updates` (RFC 0041 section 1), since they differ for every
table. What the registry adds is that a table missing from it, or listed as copied without a step
in the planner that writes it, fails a test instead of being left out of a copy without a word.

A new tenant table is a migration, a model, and one line here. A kind is added by a migration and a
line here, never by a tenant (RFC 0041 section 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from lorenzo_api.db import Base
from lorenzo_api.models import (
    AuditLog,
    Being,
    Book,
    Calendar,
    CalendarImport,
    CalendarObservance,
    CalendarPeriod,
    CalendarReckoning,
    Campaign,
    CampaignGm,
    CampaignProfilePicture,
    Chapter,
    Character,
    CharacterPlayer,
    Clock,
    ClockRelationship,
    ComputedStat,
    ComputedStatComparison,
    ComputedStatContents,
    ComputedStatLinear,
    ComputedStatSum,
    ComputedStatSumTerm,
    Containment,
    ContentReference,
    Edition,
    Entity,
    EntityAudience,
    EntityChange,
    EntityKnowledge,
    EntityLocation,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    EntityStatGroup,
    EntryCalendarPeriod,
    EventClockReading,
    EventGroupCreation,
    EventLearning,
    EventParticipant,
    EventRelationship,
    Fact,
    FactAbout,
    GroupMember,
    Information,
    Invite,
    Item,
    ItemInstance,
    Knowledge,
    Location,
    LocationPart,
    ManuscriptExtraction,
    ManuscriptMove,
    ManuscriptPlacement,
    ManuscriptRevision,
    ManuscriptSplit,
    Map,
    MapPlacement,
    Membership,
    Notification,
    Ownership,
    Payload,
    PayloadDescription,
    PayloadDocument,
    PayloadNumber,
    PayloadPicture,
    Player,
    ReleaseFanout,
    RepositoryCopy,
    RepositoryCopyLinkAttachment,
    RepositoryCopyLinkEntity,
    RepositoryCopyLinkStatDefinition,
    RepositoryCopyLinkStatGroup,
    RepositoryProfile,
    RepositoryRelease,
    RepositoryReleaseBlob,
    RepositoryReleaseDocument,
    RepositoryReleasedRow,
    RepositoryShowcase,
    SceneTelling,
    StatDefinition,
    StatDefinitionEnumValue,
    StatGroup,
    StoryEvent,
    TenantAdminCampaignOptOut,
    TenantProfilePicture,
    WritingBiography,
    WritingReviewGrant,
    WritingReviewNote,
)
from lorenzo_api.models.lived_order import LivedBefore
from lorenzo_api.models.session_play import EventPresentation, SessionSequence
from lorenzo_api.models.story_context import (
    SceneBeing,
    SceneEvent,
    SceneFact,
    SessionEvent,
    SessionFact,
)
from lorenzo_api.models.story_session import (
    Scene,
    SceneAppearance,
    SessionCharacter,
    SessionGm,
    SessionPlayer,
    StorySession,
)

# What a copy does with a table's rows:
#   rows            the planner writes them under the key of the table's name, and `write_rows`
#                   inserts them in the order of REGISTRY;
#   link            a copy link (ADR 0119): the planner writes it under `link_<of>`, and
#                   `write_rows` inserts it after every `rows` table, its `<of>_id` column
#                   holding the copy's id;
#   attachment_link the link of an attachment (ADR 0172), written by `write_attachments`;
#   none            not copied: what a repository publishes for its libraries to read, or what
#                   belongs to a play tenant, a campaign or administration.
Copy = Literal["rows", "link", "attachment_link", "none"]
LinkOf = Literal["entity", "stat_group", "stat_definition"]


@dataclass(frozen=True)
class CopyableTable:
    name: str
    model: type[Base]
    # Can a repository hold it, so that a library may read it through the gated read (ADR 0118)?
    content: bool
    copy: Copy
    # The table whose planner step writes these rows along with its own, when the table has no
    # step of its own: a `payload_description` rides with its `payload`.
    carried_by: str | None = None
    # A `link` table's kind of row: `entity` for `repository_copy_link_entity`.
    link_of: LinkOf | None = None
    # A purge of a copy counts the tenant's own rows of this table that go with it (the queries
    # are hand-written in `forget_copy`).
    counted_on_purge: bool = False


def _rows(
    model: type[Base],
    name: str,
    *,
    carried_by: str | None = None,
    counted_on_purge: bool = False,
) -> CopyableTable:
    return CopyableTable(
        name, model, True, "rows", carried_by=carried_by, counted_on_purge=counted_on_purge
    )


def _link(model: type[Base], name: str, of: LinkOf) -> CopyableTable:
    return CopyableTable(name, model, True, "link", link_of=of)


# The order is the order a copy inserts its rows in: a table comes after every table it points to.
REGISTRY: tuple[CopyableTable, ...] = (
    _rows(StatGroup, "stat_group"),
    _rows(StatDefinition, "stat_definition", counted_on_purge=True),
    _rows(StatDefinitionEnumValue, "stat_definition_enum_value", carried_by="stat_definition"),
    _rows(Entity, "entity"),
    _rows(Fact, "fact", carried_by="entity"),
    _rows(Calendar, "calendar", carried_by="entity"),
    _rows(Clock, "clock", carried_by="entity"),
    _rows(Location, "location", carried_by="entity"),
    _rows(LocationPart, "location_part", counted_on_purge=True),
    _rows(EntityLocation, "entity_location", counted_on_purge=True),
    _rows(Map, "map", carried_by="entity"),
    _rows(MapPlacement, "map_placement", counted_on_purge=True),
    _rows(ClockRelationship, "clock_relationship", counted_on_purge=True),
    _rows(StoryEvent, "story_event", carried_by="entity"),
    _rows(EventClockReading, "event_clock_reading", counted_on_purge=True),
    _rows(CalendarReckoning, "calendar_reckoning", counted_on_purge=True),
    _rows(CalendarPeriod, "calendar_period"),
    _rows(CalendarObservance, "calendar_observance"),
    _rows(EntryCalendarPeriod, "entry_calendar_period"),
    _rows(EventRelationship, "event_relationship", counted_on_purge=True),
    _rows(EntityAudience, "entity_audience", carried_by="entity"),
    _rows(EntityKnowledge, "entity_knowledge", counted_on_purge=True),
    _rows(FactAbout, "fact_about", counted_on_purge=True),
    _rows(Item, "item", carried_by="entity"),
    _rows(ItemInstance, "item_instance", carried_by="entity"),
    _rows(Being, "being", carried_by="entity"),
    _rows(EventParticipant, "event_participant", counted_on_purge=True),
    _rows(Character, "character", carried_by="entity"),
    _rows(EntitySlug, "entity_slug", carried_by="entity"),
    _rows(EntityPrototype, "entity_prototype", counted_on_purge=True),
    _rows(EntityStatGroup, "entity_stat_group", counted_on_purge=True),
    _rows(EntityStat, "entity_stat", counted_on_purge=True),
    _rows(ComputedStat, "computed_stat", counted_on_purge=True),
    _rows(ComputedStatLinear, "computed_stat_linear", carried_by="computed_stat"),
    _rows(ComputedStatComparison, "computed_stat_comparison", carried_by="computed_stat"),
    _rows(ComputedStatSum, "computed_stat_sum", carried_by="computed_stat"),
    _rows(ComputedStatSumTerm, "computed_stat_sum_term", carried_by="computed_stat_sum"),
    _rows(ComputedStatContents, "computed_stat_contents", carried_by="computed_stat"),
    _rows(Containment, "containment", counted_on_purge=True),
    _rows(Ownership, "ownership", counted_on_purge=True),
    _rows(GroupMember, "group_member", counted_on_purge=True),
    _rows(Book, "book", carried_by="entity"),
    _rows(Chapter, "chapter", carried_by="entity"),
    _rows(WritingBiography, "writing_biography", carried_by="entity"),
    _rows(Edition, "edition", carried_by="entity"),
    _rows(Scene, "scene", carried_by="entity"),
    _rows(SceneTelling, "scene_telling", carried_by="entity"),
    _rows(SceneFact, "scene_fact", counted_on_purge=True),
    _rows(SceneEvent, "scene_event", counted_on_purge=True),
    _rows(SceneBeing, "scene_being", counted_on_purge=True),
    _rows(Information, "information"),
    _rows(LivedBefore, "lived_before", counted_on_purge=True),
    _rows(EventLearning, "event_learning", counted_on_purge=True),
    _rows(Payload, "payload"),
    _rows(PayloadDescription, "payload_description", carried_by="payload"),
    _rows(PayloadNumber, "payload_number", carried_by="payload"),
    _rows(PayloadPicture, "payload_picture", carried_by="payload"),
    _rows(PayloadDocument, "payload_document", carried_by="payload"),
    _rows(ManuscriptPlacement, "manuscript_placement", counted_on_purge=True),
    _rows(Knowledge, "knowledge", counted_on_purge=True),
    _rows(ContentReference, "content_reference", carried_by="payload_description"),
    _rows(RepositoryCopy, "repository_copy"),
    _link(RepositoryCopyLinkEntity, "repository_copy_link_entity", "entity"),
    _link(RepositoryCopyLinkStatGroup, "repository_copy_link_stat_group", "stat_group"),
    _link(
        RepositoryCopyLinkStatDefinition, "repository_copy_link_stat_definition", "stat_definition"
    ),
    # What a repository published (ADR 0207) and the hashes of it (ADR 0208): read by the
    # libraries it is granted to, never copied.
    CopyableTable("repository_release", RepositoryRelease, True, "none"),
    CopyableTable("repository_released_row", RepositoryReleasedRow, True, "none"),
    # What the repository says about itself (ADR 0213): a copy never carries it, but the libraries
    # it is granted to read it.
    CopyableTable("repository_profile", RepositoryProfile, True, "none"),
    # The entries an Owner features in the preview (ADR 0293): read by whoever looks at the preview
    # through the gated read, never copied.
    CopyableTable("repository_showcase", RepositoryShowcase, True, "none"),
    # The release document of a repository and the files it points at (ADR 0214): written once
    # for a release, read by the libraries the repository is granted to, never copied.
    CopyableTable("repository_release_document", RepositoryReleaseDocument, True, "none"),
    CopyableTable("repository_release_blob", RepositoryReleaseBlob, True, "none"),
    # Copy bookkeeping of the tenant that copied (ADR 0172), not content a repository holds: what
    # a bridge attached is read from its entities.
    CopyableTable(
        "repository_copy_link_attachment", RepositoryCopyLinkAttachment, False, "attachment_link"
    ),
    # Relative to a player, a campaign or tenant administration, none of which a repository has
    # (RFC 0024 section 4).
    CopyableTable("writing_review_grant", WritingReviewGrant, False, "none"),
    CopyableTable("writing_review_note", WritingReviewNote, False, "none"),
    CopyableTable("audit_log", AuditLog, False, "none"),
    CopyableTable("campaign", Campaign, False, "none"),
    CopyableTable("campaign_gm", CampaignGm, False, "none"),
    CopyableTable("calendar_import", CalendarImport, False, "none"),
    CopyableTable("event_group_creation", EventGroupCreation, False, "none"),
    CopyableTable("session_sequence", SessionSequence, False, "none"),
    CopyableTable("event_presentation", EventPresentation, False, "none"),
    CopyableTable("story_session", StorySession, False, "none"),
    CopyableTable("scene_appearance", SceneAppearance, False, "none"),
    CopyableTable("session_gm", SessionGm, False, "none"),
    CopyableTable("session_player", SessionPlayer, False, "none"),
    CopyableTable("session_character", SessionCharacter, False, "none"),
    CopyableTable("session_fact", SessionFact, False, "none"),
    CopyableTable("session_event", SessionEvent, False, "none"),
    CopyableTable("invite", Invite, False, "none"),
    CopyableTable("campaign_profile_picture", CampaignProfilePicture, False, "none"),
    CopyableTable("character_player", CharacterPlayer, False, "none"),
    CopyableTable("entity_change", EntityChange, False, "none"),
    CopyableTable("manuscript_move", ManuscriptMove, False, "none"),
    CopyableTable("manuscript_split", ManuscriptSplit, False, "none"),
    CopyableTable("manuscript_extraction", ManuscriptExtraction, False, "none"),
    CopyableTable("manuscript_revision", ManuscriptRevision, False, "none"),
    CopyableTable("membership", Membership, False, "none"),
    CopyableTable("notification", Notification, False, "none"),
    # The announcements a repository owes the libraries that hold it (ADR 0301): who copied it,
    # drained by a process that finishes them across repositories; never content, never copied.
    CopyableTable("release_fanout", ReleaseFanout, False, "none"),
    CopyableTable("player", Player, False, "none"),
    CopyableTable("tenant_admin_campaign_opt_out", TenantAdminCampaignOptOut, False, "none"),
    CopyableTable("tenant_profile_picture", TenantProfilePicture, False, "none"),
)

CONTENT_TABLES: frozenset[str] = frozenset(t.name for t in REGISTRY if t.content)
EXCLUDED_TABLES: frozenset[str] = frozenset(t.name for t in REGISTRY if not t.content)

# `write_rows`: the tables a plan's rows are inserted into, in order, by the key of the table.
COPIED_TABLES: tuple[tuple[str, type[Base]], ...] = tuple(
    (t.name, t.model) for t in REGISTRY if t.copy == "rows"
)

# `write_rows`, after those: each copy link as (planner key, model, the column of the copy's id).
COPY_LINKS: tuple[tuple[str, type[Base], str], ...] = tuple(
    (f"link_{t.link_of}", t.model, f"{t.link_of}_id") for t in REGISTRY if t.copy == "link"
)

# `forget_copy` drops the links of a repository, those of attachments included.
# Typed loosely: each has `tenant_id` and `source_tenant_id` columns, which `type[Base]` lacks.
LINK_MODELS: tuple[Any, ...] = tuple(
    t.model for t in REGISTRY if t.copy in ("link", "attachment_link")
)

# What a purge of a copy reports as the tenant's own rows that went with it (`also_removed`): the
# tables flagged, and an attachment, which is a prototype edge counted apart.
PURGE_COUNTED: frozenset[str] = frozenset(
    {t.name for t in REGISTRY if t.counted_on_purge} | {"attachment"}
)
