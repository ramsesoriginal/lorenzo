"""Carrier identity and ordered manuscript coverage (ADR 0379)."""

import uuid

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, UuidPk, same_tenant_fk


class Carrier(Base):
    __tablename__ = "carrier"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="carrier_tenant_key"),
        same_tenant_fk("carrier_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]


class CarrierCoverage(Base):
    __tablename__ = "carrier_coverage"
    __table_args__ = (
        CheckConstraint(
            "(target_entity_id IS NULL) <> (target_payload_id IS NULL)",
            name="carrier_coverage_one_target",
        ),
        same_tenant_fk(
            "carrier_coverage_carrier_fkey",
            ["carrier_id"],
            "carrier",
            ["entity_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "carrier_coverage_entry_fkey", ["target_entity_id"], "entity", ondelete="CASCADE"
        ),
        same_tenant_fk(
            "carrier_coverage_payload_fkey", ["target_payload_id"], "payload", ondelete="CASCADE"
        ),
        same_tenant_fk(
            "carrier_coverage_anchor_fkey", ["before_payload_id"], "payload", ondelete="NO ACTION"
        ),
    )
    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    carrier_id: Mapped[uuid.UUID] = mapped_column(index=True)
    target_entity_id: Mapped[uuid.UUID | None]
    target_payload_id: Mapped[uuid.UUID | None]
    before_payload_id: Mapped[uuid.UUID | None]
    position: Mapped[int]
