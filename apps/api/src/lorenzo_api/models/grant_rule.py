from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, Integer, Numeric, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk, same_tenant_fk

__all__ = ["FeaturePrerequisite", "GrantRule", "GrantRuleCondition", "GrantRuleOption"]

RULE_MODES = ("all", "choose")
RULE_LASTS = ("while_source", "permanent")
CONDITION_SUBJECTS = ("holder", "source")
COMPARATORS = ("lt", "le", "eq", "ne", "ge", "gt")


class GrantRule(Base):
    """What a source entitles its holder to - ADR 0455, RFC 0054. It hangs on a source entry (a
    race, a class, an archetype, a feature, an item prototype, any entry), applies to a holder that
    has the entry among its ancestors or holds an active instance of it, and says which features
    that gives: `all` of its options, or `choose` between `min_count` and a maximum (a constant, or
    a stat of the holder read when the rule is applied). Its options are an explicit list or the
    features under a category entry. It holds while its conditions all hold. `lasts` says whether a
    grant outlives its source, and `changeable` whether a pick can be swapped.

    A rule goes with its source and with its category entry (the keys cascade). Nothing reads a rule
    here but the vocabulary's own routes; granting is the apply of a later slice (ADR 0456).
    """

    __tablename__ = "grant_rule"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="grant_rule_id_tenant_id_key"),
        same_tenant_fk("grant_rule_entry_id_fkey", ["entry_id"], "entity", ondelete="CASCADE"),
        same_tenant_fk(
            "grant_rule_count_stat_definition_id_fkey",
            ["count_stat_definition_id"],
            "stat_definition",
        ),
        same_tenant_fk(
            "grant_rule_option_category_entry_id_fkey",
            ["option_category_entry_id"],
            "entity",
            ondelete="CASCADE",
        ),
        CheckConstraint("mode IN ('all', 'choose')", name="grant_rule_mode"),
        CheckConstraint("lasts IN ('while_source', 'permanent')", name="grant_rule_lasts"),
        CheckConstraint("min_count >= 0", name="grant_rule_min_count"),
        CheckConstraint("max_count IS NULL OR max_count >= 1", name="grant_rule_max_count"),
        CheckConstraint(
            "max_count IS NULL OR min_count <= max_count", name="grant_rule_min_within_max"
        ),
        CheckConstraint(
            "(mode = 'choose' AND num_nonnulls(max_count, count_stat_definition_id) = 1) "
            "OR (mode = 'all' AND num_nonnulls(max_count, count_stat_definition_id) = 0 "
            "AND min_count = 0 AND NOT changeable)",
            name="grant_rule_count_of_mode",
        ),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    entry_id: Mapped[uuid.UUID] = mapped_column(index=True)
    label: Mapped[str | None]
    position: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str]
    min_count: Mapped[int] = mapped_column(Integer, server_default="0")
    max_count: Mapped[int | None] = mapped_column(Integer)
    count_stat_definition_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    option_category_entry_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    lasts: Mapped[str] = mapped_column(server_default="while_source")
    changeable: Mapped[bool] = mapped_column(server_default=false())
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    conditions: Mapped[list[GrantRuleCondition]] = relationship(
        foreign_keys="[GrantRuleCondition.rule_id]",
        order_by="GrantRuleCondition.position",
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    options: Mapped[list[GrantRuleOption]] = relationship(
        foreign_keys="[GrantRuleOption.rule_id]",
        order_by="GrantRuleOption.position",
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class GrantRuleCondition(Base):
    """One comparison a rule needs to hold, with all of its conditions ANDed (an OR is a separate
    rule): `subject` is the holder or the source, the stat is read on it, and the right side is a
    constant or another stat of the same subject - ADR 0455, the comparators of ADR 0104."""

    __tablename__ = "grant_rule_condition"
    __table_args__ = (
        UniqueConstraint("rule_id", "position", name="grant_rule_condition_rule_id_position_key"),
        same_tenant_fk(
            "grant_rule_condition_rule_id_fkey", ["rule_id"], "grant_rule", ondelete="CASCADE"
        ),
        same_tenant_fk(
            "grant_rule_condition_stat_definition_id_fkey",
            ["stat_definition_id"],
            "stat_definition",
        ),
        same_tenant_fk(
            "grant_rule_condition_right_stat_definition_id_fkey",
            ["right_stat_definition_id"],
            "stat_definition",
        ),
        CheckConstraint("subject IN ('holder', 'source')", name="grant_rule_condition_subject"),
        CheckConstraint(
            "comparator IN ('lt', 'le', 'eq', 'ne', 'ge', 'gt')",
            name="grant_rule_condition_comparator",
        ),
        CheckConstraint(
            "num_nonnulls(right_stat_definition_id, right_constant) = 1",
            name="grant_rule_condition_one_right_side",
        ),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    rule_id: Mapped[uuid.UUID] = mapped_column(index=True)
    position: Mapped[int] = mapped_column(Integer)
    subject: Mapped[str]
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(index=True)
    comparator: Mapped[str]
    right_constant: Mapped[Decimal | None] = mapped_column(Numeric())
    right_stat_definition_id: Mapped[uuid.UUID | None] = mapped_column(index=True)


class GrantRuleOption(Base):
    """A feature an explicit rule offers, in the order written - ADR 0455. It goes with the entry
    (the key cascades); a rule that names a category entry has none of these."""

    __tablename__ = "grant_rule_option"
    __table_args__ = (
        UniqueConstraint("rule_id", "position", name="grant_rule_option_rule_id_position_key"),
        same_tenant_fk(
            "grant_rule_option_rule_id_fkey", ["rule_id"], "grant_rule", ondelete="CASCADE"
        ),
        same_tenant_fk(
            "grant_rule_option_option_entry_id_fkey",
            ["option_entry_id"],
            "entity",
            ondelete="CASCADE",
        ),
    )

    rule_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    option_entry_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, index=True)
    tenant_id: Mapped[TenantFk]
    position: Mapped[int] = mapped_column(Integer)


class FeaturePrerequisite(Base):
    """What a holder needs to have a feature, whichever rule offers it: a comparison on the holder,
    the same as a rule's condition - ADR 0455. All of a feature's prerequisites must hold. They go
    with the feature kind (the key cascades)."""

    __tablename__ = "feature_prerequisite"
    __table_args__ = (
        UniqueConstraint(
            "feature_id", "position", name="feature_prerequisite_feature_id_position_key"
        ),
        same_tenant_fk(
            "feature_prerequisite_feature_id_fkey",
            ["feature_id"],
            "feature",
            ["entity_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "feature_prerequisite_stat_definition_id_fkey",
            ["stat_definition_id"],
            "stat_definition",
        ),
        same_tenant_fk(
            "feature_prerequisite_right_stat_definition_id_fkey",
            ["right_stat_definition_id"],
            "stat_definition",
        ),
        CheckConstraint(
            "comparator IN ('lt', 'le', 'eq', 'ne', 'ge', 'gt')",
            name="feature_prerequisite_comparator",
        ),
        CheckConstraint(
            "num_nonnulls(right_stat_definition_id, right_constant) = 1",
            name="feature_prerequisite_one_right_side",
        ),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    feature_id: Mapped[uuid.UUID] = mapped_column(index=True)
    position: Mapped[int] = mapped_column(Integer)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(index=True)
    comparator: Mapped[str]
    right_constant: Mapped[Decimal | None] = mapped_column(Numeric())
    right_stat_definition_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
