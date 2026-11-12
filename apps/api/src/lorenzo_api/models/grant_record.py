from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, CreatedBy, TenantFk, UuidPk, same_tenant_fk

__all__ = ["GrantRecord"]

RECORD_STATES = ("active", "revoked")
REVOKED_REASONS = ("source", "conditions", "removed")


class GrantRecord(Base):
    """How a holder came to have a feature - ADR 0456, RFC 0054. A rule's grant has its rule and
    the source it was made from (an ancestor entry of the holder, or an instance the holder
    holds); an award has neither. While `active` it has its instance; when `revoked` it keeps its
    feature and loses the instance, which is deleted, with the `revoked_reason` (`source` gone or
    inactive, `conditions` no longer holding, or `removed` by hand: a grant removed by hand is not
    made again at the next apply).

    A (holder, rule, source, feature) pair has one active record, so applying twice grants nothing
    new. A deleted rule leaves its records, which then read as awards. A record goes with its
    holder, its feature and its instance (the keys cascade); one whose source entry is deleted
    keeps its row with no source, and is revoked at the next check if its rule lasts while its
    source does. The requests that remove a source revoke its records first.
    """

    __tablename__ = "grant_record"
    __table_args__ = (
        same_tenant_fk("grant_record_holder_id_fkey", ["holder_id"], "entity", ondelete="CASCADE"),
        same_tenant_fk("grant_record_rule_id_fkey", ["rule_id"], "grant_rule", ondelete="SET NULL"),
        same_tenant_fk(
            "grant_record_source_ref_id_fkey", ["source_ref_id"], "entity", ondelete="SET NULL"
        ),
        same_tenant_fk(
            "grant_record_feature_id_fkey", ["feature_id"], "entity", ondelete="CASCADE"
        ),
        same_tenant_fk(
            "grant_record_feature_instance_id_fkey",
            ["feature_instance_id"],
            "feature_instance",
            ["entity_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("state IN ('active', 'revoked')", name="grant_record_state"),
        CheckConstraint(
            "revoked_reason IS NULL OR revoked_reason IN ('source', 'conditions', 'removed')",
            name="grant_record_revoked_reason",
        ),
        CheckConstraint(
            "state = 'revoked' OR feature_instance_id IS NOT NULL",
            name="grant_record_active_has_one",
        ),
        CheckConstraint(
            "(state = 'revoked') = (revoked_reason IS NOT NULL)",
            name="grant_record_reason_if_revoked",
        ),
        Index(
            "grant_record_active_once",
            "holder_id",
            "rule_id",
            "source_ref_id",
            "feature_id",
            unique=True,
            postgresql_where=text("state = 'active' AND rule_id IS NOT NULL"),
        ),
        Index(
            "grant_record_instance_once",
            "feature_instance_id",
            unique=True,
            postgresql_where=text("feature_instance_id IS NOT NULL"),
        ),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    holder_id: Mapped[uuid.UUID] = mapped_column(index=True)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    source_ref_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    feature_id: Mapped[uuid.UUID] = mapped_column(index=True)
    feature_instance_id: Mapped[uuid.UUID | None]
    state: Mapped[str] = mapped_column(server_default="active")
    revoked_reason: Mapped[str | None]
    created_at: Mapped[CreatedAt]
    created_by: Mapped[CreatedBy]
