from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base

# The types information_singleton_type's partial index keeps one per entity
# (ADR 0101). The index predicate can't read this table, so this list (which
# models/information.py builds the predicate from) and the migration's copy
# are separate facts from the seeded rows; a test checks they agree.
SINGLETON_INFORMATION_TYPES = ("description", "main_picture")


class InformationType(Base):
    """The fixed, code-dependent subset of Information.type values - see
    ADR 0101/RFC 0015. A global catalog, not tenant data: no tenant_id, no
    RLS, and the app role can only read it. Free-form types a GM invents
    (`note`, `handout`, ...) deliberately have no row.
    """

    __tablename__ = "information_type"

    name: Mapped[str] = mapped_column(primary_key=True)
    is_singleton: Mapped[bool]
    # "technical" (system-managed) or "gm_authored" - lets a client hide
    # system-managed types from a notes editor.
    category: Mapped[str]
