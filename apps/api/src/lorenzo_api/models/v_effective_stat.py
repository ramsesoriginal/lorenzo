from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base

if TYPE_CHECKING:
    from lorenzo_api.models.computed_stat import ComputedStat
    from lorenzo_api.models.stat_definition import StatDefinition


class VEffectiveStat(Base):
    """Read-only view resolving every stat_definition's effective value for
    every entity through the prototype graph - see ADR 0037 (the resolution
    rule) and ADR 0039 (this view's own extraction and generalization from
    v_item/v_item_instance's own formerly-inlined copy of it). One row per
    (entity, stat_definition) pair that resolves to *something* - an entity
    with neither a direct nor an inherited value for a given stat has no
    row here at all, not a row with every value_* column NULL.

    No real constraints (views can't have any); (entity_id,
    stat_definition_id) is declared as a composite primary_key purely so
    the ORM has an identity to key rows on, matching no actual PRIMARY KEY
    constraint in the database.
    """

    __tablename__ = "v_effective_stat"

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[uuid.UUID]
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    value_int: Mapped[int | None]
    value_text: Mapped[str | None]
    value_float: Mapped[float | None]
    value_bool: Mapped[bool | None]
    # Set when a formula won (ADR 0104): the ancestor entity holding the
    # computed_stat row. Every value_* column is then null - the value is
    # computed in Python (stat_evaluation.evaluate), never read from here.
    computed_entity_id: Mapped[uuid.UUID | None] = mapped_column()

    # No real ForeignKey (views have none) - primaryjoin/foreign_keys= spell
    # out the join explicitly instead of relying on a constraint to infer
    # it from, same as VItem/VItemInstance's own `entity` relationship.
    stat_definition: Mapped[StatDefinition] = relationship(
        primaryjoin="VEffectiveStat.stat_definition_id == StatDefinition.id",
        foreign_keys=[stat_definition_id],
        viewonly=True,
        lazy="raise_on_sql",
    )
    computed_stat: Mapped[ComputedStat | None] = relationship(
        primaryjoin=(
            "and_(VEffectiveStat.computed_entity_id == ComputedStat.entity_id, "
            "VEffectiveStat.stat_definition_id == ComputedStat.stat_definition_id)"
        ),
        foreign_keys=[computed_entity_id, stat_definition_id],
        viewonly=True,
        uselist=False,
        lazy="raise_on_sql",
    )
