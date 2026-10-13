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
    Campaign,
    CampaignGm,
    CampaignInvite,
    CampaignProfilePicture,
    Character,
    CharacterPlayer,
    ComputedStat,
    ComputedStatComparison,
    ComputedStatContents,
    ComputedStatLinear,
    ComputedStatSum,
    ComputedStatSumTerm,
    Containment,
    ContentReference,
    Entity,
    EntityChange,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    EntityStatGroup,
    GroupMember,
    Information,
    Item,
    ItemInstance,
    Knowledge,
    Membership,
    Notification,
    Ownership,
    Payload,
    PayloadDescription,
    PayloadDocument,
    PayloadNumber,
    PayloadPicture,
    Player,
    RepositoryCopy,
    RepositoryCopyLinkAttachment,
    RepositoryCopyLinkEntity,
    RepositoryCopyLinkStatDefinition,
    RepositoryCopyLinkStatGroup,
    RepositoryRelease,
    RepositoryReleasedRow,
    StatDefinition,
    StatDefinitionEnumValue,
    StatGroup,
    TenantAdminCampaignOptOut,
    TenantProfilePicture,
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
    _rows(Item, "item", carried_by="entity"),
    _rows(ItemInstance, "item_instance", carried_by="entity"),
    _rows(Being, "being", carried_by="entity"),
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
    _rows(Information, "information"),
    _rows(Payload, "payload"),
    _rows(PayloadDescription, "payload_description", carried_by="payload"),
    _rows(PayloadNumber, "payload_number", carried_by="payload"),
    _rows(PayloadPicture, "payload_picture", carried_by="payload"),
    _rows(PayloadDocument, "payload_document", carried_by="payload"),
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
    # Copy bookkeeping of the tenant that copied (ADR 0172), not content a repository holds: what
    # a bridge attached is read from its entities.
    CopyableTable(
        "repository_copy_link_attachment", RepositoryCopyLinkAttachment, False, "attachment_link"
    ),
    # Relative to a player, a campaign or tenant administration, none of which a repository has
    # (RFC 0024 section 4).
    CopyableTable("audit_log", AuditLog, False, "none"),
    CopyableTable("campaign", Campaign, False, "none"),
    CopyableTable("campaign_gm", CampaignGm, False, "none"),
    CopyableTable("campaign_invite", CampaignInvite, False, "none"),
    CopyableTable("campaign_profile_picture", CampaignProfilePicture, False, "none"),
    CopyableTable("character_player", CharacterPlayer, False, "none"),
    CopyableTable("entity_change", EntityChange, False, "none"),
    CopyableTable("membership", Membership, False, "none"),
    CopyableTable("notification", Notification, False, "none"),
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
