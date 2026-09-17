from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, UuidPk


class Notification(Base):
    """One in-app notification for one recipient - see ADR 0058. Fanned out
    at creation, not resolved at read time: a broadcast (e.g. every player
    in a campaign) writes one row per recipient, each fully self-contained
    (`title`/`body` copied in, not joined from live Campaign/Character data
    later) so `GET /me/notifications` never needs to join out to a
    tenant-scoped table.

    No `tenant`/`user` relationships declared - both directions are always
    reached by a plain query on a known id, not ORM navigation, matching
    the lean shape the profile-picture link tables (ADR 0056) already use.

    RLS baked in at table creation (not a follow-up `ALTER POLICY`), split
    by command - the first RLS'd table where the writer and the row's own
    "owner" are routinely different people. `SELECT`/`UPDATE` extend the
    self-access-OR-tenant-scoped shape `migrations/versions/
    a22dc991a926_*.py` already proved out for `player`/`campaign_gm` with a
    third clause, `created_by = app.user_id` - needed because `INSERT ...
    RETURNING` (what the ORM always uses to read a server-generated id/
    created_at back) re-checks the new row against this same SELECT policy,
    and a platform notification (no tenant_id, written *for* someone else)
    would otherwise satisfy none of the first two clauses. `INSERT` itself
    stays permissive (`WITH CHECK (true)`) - who may create one is fully
    authorized at the API layer instead, one gate per scope. See the
    migration's own comment for the full story.
    """

    __tablename__ = "notification"

    id: Mapped[UuidPk]
    # ADR 0061 - one value shared by every row a single creation call fans
    # out, so a sender can pull "everyone I sent this to" (GET /me/
    # notifications/sent?batch_id=...) in one query instead of correlating
    # by title/timestamp. Always set explicitly by lorenzo_api.notifications
    # - the column default only ever backfills a hypothetical pre-existing
    # row, never relied on for a real creation call.
    batch_id: Mapped[uuid.UUID] = mapped_column(index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    # Null for platform scope - no single tenant applies.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), index=True
    )
    # Free text, not a native enum - same reasoning Information.type already
    # uses (ADR 0017): caller-chosen categorization, not a fixed
    # schema-level discriminant. "platform" | "tenant" | "campaign" |
    # "character" by convention, not enforced.
    scope: Mapped[str]
    # The campaign id / character entity id this is about, for deep-linking -
    # null for platform/tenant scope, where tenant_id itself already
    # identifies the context.
    source_id: Mapped[uuid.UUID | None]
    # Free-form within scope, e.g. "tenant_invite", "session_reminder".
    type: Mapped[str]
    title: Mapped[str]
    body: Mapped[str]
    read_at: Mapped[datetime | None]
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[CreatedAt]
