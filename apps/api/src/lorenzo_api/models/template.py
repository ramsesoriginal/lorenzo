from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk, same_tenant_fk

__all__ = ["Template", "TemplateSlot", "TemplateSlotExclusion", "TemplateSlotStat"]

SLOT_KINDS = ("stats", "information", "held", "tags", "features")


class Template(Base):
    """A read-side view of an entry, as data - ADR 0451, RFC 0052. It says which stats and notes a
    sheet shows, in what order and under which labels (its slots), and which entries it is for:
    those of one kind and under one ancestor (`required_kind`, `required_ancestor_entry_id`, both
    optional, both applied when set). A template reads and never writes; what it shows is what the
    caller may read by the rules each source already has.

    `system_id` only names the game system the template is for, so a campaign that names one can
    pick its templates; it is not part of the filter. A template whose ancestor entry is deleted
    goes with it (the key cascades): without its ancestor it would match every entry.
    """

    __tablename__ = "template"
    __table_args__ = (
        # ADR 0117: what same-tenant keys into this table reference.
        UniqueConstraint("id", "tenant_id", name="template_id_tenant_id_key"),
        UniqueConstraint("tenant_id", "name", name="template_tenant_id_name_key"),
        same_tenant_fk("template_system_id_fkey", ["system_id"], "system"),
        same_tenant_fk(
            "template_required_ancestor_entry_id_fkey",
            ["required_ancestor_entry_id"],
            "entity",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    name: Mapped[str]
    system_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    required_kind: Mapped[str | None]
    required_ancestor_entry_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    slots: Mapped[list[TemplateSlot]] = relationship(
        foreign_keys="[TemplateSlot.template_id]",
        order_by="TemplateSlot.position",
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TemplateSlot(Base):
    """One block of a template, in the order written - ADR 0451. `kind` says what it shows:
    `stats` (a stat group, or an ordered list of stats with a label each), `information` (the
    entry's notes of a type), `held` (the things the entry holds, a column for each stat of a group
    or list), `features` (the features it holds, by type, with the same columns; ADR 0457) or
    `tags` (the `bool` stats that are true, of a group or of any).
    """

    __tablename__ = "template_slot"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="template_slot_id_tenant_id_key"),
        UniqueConstraint("template_id", "position", name="template_slot_template_id_position_key"),
        same_tenant_fk(
            "template_slot_template_id_fkey", ["template_id"], "template", ondelete="CASCADE"
        ),
        # Deleting a stat group a slot uses is refused by the API.
        same_tenant_fk("template_slot_stat_group_id_fkey", ["stat_group_id"], "stat_group"),
        CheckConstraint(
            "kind IN ('stats', 'information', 'held', 'tags', 'features')",
            name="template_slot_kind",
        ),
        CheckConstraint(
            "held_order IS NULL OR held_order IN ('name', 'prototype')",
            name="template_slot_held_order",
        ),
        CheckConstraint(
            "(kind = 'information') = (information_type IS NOT NULL)",
            name="template_slot_information_type",
        ),
        CheckConstraint(
            "(kind = 'held') = (held_order IS NOT NULL)", name="template_slot_held_order_of_held"
        ),
        CheckConstraint(
            "kind <> 'information' OR stat_group_id IS NULL",
            name="template_slot_information_has_no_group",
        ),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    template_id: Mapped[uuid.UUID] = mapped_column(index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str]
    label: Mapped[str | None]
    stat_group_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    information_type: Mapped[str | None]
    held_order: Mapped[str | None]

    stats: Mapped[list[TemplateSlotStat]] = relationship(
        foreign_keys="[TemplateSlotStat.slot_id]",
        order_by="TemplateSlotStat.position",
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    exclusions: Mapped[list[TemplateSlotExclusion]] = relationship(
        foreign_keys="[TemplateSlotExclusion.slot_id]",
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TemplateSlotStat(Base):
    """A stat a slot lists, in the order written, with the label it is shown under - ADR 0451.
    Deleting a stat a slot lists is refused by the API."""

    __tablename__ = "template_slot_stat"
    __table_args__ = (
        UniqueConstraint(
            "slot_id",
            "stat_definition_id",
            name="template_slot_stat_slot_id_stat_definition_id_key",
        ),
        same_tenant_fk(
            "template_slot_stat_slot_id_fkey", ["slot_id"], "template_slot", ondelete="CASCADE"
        ),
        same_tenant_fk(
            "template_slot_stat_stat_definition_id_fkey",
            ["stat_definition_id"],
            "stat_definition",
        ),
    )

    slot_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[TenantFk]
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(index=True)
    label: Mapped[str | None]


class TemplateSlotExclusion(Base):
    """A stat a slot that shows a whole group leaves out - ADR 0451."""

    __tablename__ = "template_slot_exclusion"
    __table_args__ = (
        same_tenant_fk(
            "template_slot_exclusion_slot_id_fkey",
            ["slot_id"],
            "template_slot",
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "template_slot_exclusion_stat_definition_id_fkey",
            ["stat_definition_id"],
            "stat_definition",
        ),
    )

    slot_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
