from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, same_tenant_fk

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity
    from lorenzo_api.models.stat_definition import StatDefinition


class EntityStat(Base):
    """An entity's direct (non-inherited) value for one stat_definition - see
    ADR 0014 and RFC 0001. Inherited values are resolved by the
    effective-stat views (ADR 0039), not here.
    """

    __tablename__ = "entity_stat"
    __table_args__ = (
        same_tenant_fk("entity_stat_entity_id_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
        same_tenant_fk(
            "entity_stat_stat_definition_id_fkey",
            ["stat_definition_id"],
            "stat_definition",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "num_nonnulls(value_int, value_text, value_float, value_bool, dice_count) = 1",
            name="entity_stat_exactly_one_value",
        ),
        # A dice value is a count and a number of sides, and a drop is a mode with a count (RFC 0056
        # section 1, ADR 0462); the limits are the notation's.
        CheckConstraint(
            "(dice_count IS NULL) = (dice_sides IS NULL) "
            "AND (dice_drop_mode IS NULL) = (dice_drop_count IS NULL) "
            "AND (dice_count IS NOT NULL OR dice_drop_mode IS NULL) "
            "AND (dice_count IS NULL OR (dice_count BETWEEN 1 AND 100 "
            "AND dice_sides BETWEEN 2 AND 1000)) "
            "AND (dice_drop_mode IS NULL OR (dice_drop_mode IN ('lowest', 'highest') "
            "AND dice_drop_count BETWEEN 1 AND dice_count - 1))",
            name="entity_stat_dice_parts",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    value_int: Mapped[int | None]
    value_text: Mapped[str | None]
    value_float: Mapped[float | None]
    value_bool: Mapped[bool | None]
    # A dice value as its parts (RFC 0056): all null unless the stat is a dice stat.
    dice_count: Mapped[int | None]
    dice_sides: Mapped[int | None]
    dice_drop_mode: Mapped[str | None]
    dice_drop_count: Mapped[int | None]
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    entity: Mapped[Entity] = relationship(
        foreign_keys="EntityStat.entity_id", lazy="raise_on_sql", back_populates="stats"
    )
    stat_definition: Mapped[StatDefinition] = relationship(
        foreign_keys="EntityStat.stat_definition_id",
        lazy="raise_on_sql",
        back_populates="entity_stats",
    )
