from __future__ import annotations

import uuid

from sqlalchemy import UniqueConstraint, false, true
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


class Feature(Base):
    """A feature: an entry that something has, a character feature, a spell, a feat, a boon, a
    playbook move (ADR 0454, RFC 0054). A marker, as `item` is: its stats, description, parents
    and type (a category entry among its parents) are the entry's own. `repeatable` lets a holder
    hold it twice; `starts_inactive` makes its instances begin with `active` off.
    """

    __tablename__ = "feature"
    __table_args__ = (
        # ADR 0117: what same-tenant keys into this table reference (the rules of F2).
        UniqueConstraint("entity_id", "tenant_id", name="feature_entity_id_tenant_id_key"),
        same_tenant_fk("feature_entity_id_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    repeatable: Mapped[bool] = mapped_column(server_default=false(), default=False)
    starts_inactive: Mapped[bool] = mapped_column(server_default=false(), default=False)


class FeatureInstance(Base):
    """What a holder has of a feature (ADR 0454): an entry with one prototype, the feature, whose
    stats it inherits, and its own stats for what the holder keeps (`uses_spent`, `prepared`). It
    is contained by its holder, a being, an item instance or a group, and holds nothing. `active`
    is read by a formula that asks for what is switched on (ADR 0447), true unless the feature
    starts its instances inactive.
    """

    __tablename__ = "feature_instance"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="feature_instance_entity_id_tenant_id_key"),
        same_tenant_fk(
            "feature_instance_entity_id_fkey", ["entity_id"], "entity", ondelete="CASCADE"
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    active: Mapped[bool] = mapped_column(server_default=true(), default=True)
