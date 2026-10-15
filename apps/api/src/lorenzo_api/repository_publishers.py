"""Who published a repository, and where a report about it goes - ADR 0299, RFC 0038 section 6.

The publisher of a storefront or a Discover result is the repository's Owners, named by their
accounts (display name, else nickname) and by nothing the repository writes about itself, so a
repository cannot claim to be somebody else's. A reader of Discover is in no tenant, and a
membership is the tenant's own row, so each repository's Owners are read under that repository's
context, one after another, with the reader's own context put back afterwards: what leaves is the
names and nothing else of a membership.
"""

import uuid
from collections.abc import Sequence
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.dependencies import set_tenant_rls_context
from lorenzo_api.models import Membership, MembershipRole, User
from lorenzo_api.schemas.discover import PublisherOut

__all__ = ["PUBLISHERS_MAX", "UNNAMED_PUBLISHER", "publishers_of", "report_mailto"]

# "A handful": a repository with more Owners than this names the first five.
PUBLISHERS_MAX = 5

# What an Owner whose account has neither a display name nor a nickname is called.
UNNAMED_PUBLISHER = "A Lorenzo account"


def _name(display_name: str | None, nickname: str | None) -> str:
    return (display_name or "").strip() or (nickname or "").strip() or UNNAMED_PUBLISHER


async def publishers_of(
    session: AsyncSession, repository_ids: Sequence[uuid.UUID], *, current_tenant_id: uuid.UUID
) -> dict[uuid.UUID, list[PublisherOut]]:
    """The Owners of each repository by their account names, in the order they became Owners
    (then by id), at most `PUBLISHERS_MAX`. `current_tenant_id` is the context the session is in,
    which each read leaves it in: the repository's own for an Owner's request, no tenant at all
    for a visitor's."""
    found: dict[uuid.UUID, list[PublisherOut]] = {}
    try:
        for repository_id in repository_ids:
            await set_tenant_rls_context(session, repository_id)
            rows = await session.execute(
                select(User.display_name, User.nickname)
                .join(Membership, Membership.user_id == User.id)
                .where(
                    Membership.tenant_id == repository_id,
                    Membership.role == MembershipRole.OWNER,
                )
                .order_by(Membership.created_at, User.id)
                .limit(PUBLISHERS_MAX)
            )
            found[repository_id] = [
                PublisherOut(display_name=_name(display_name, nickname))
                for display_name, nickname in rows.all()
            ]
    finally:
        await set_tenant_rls_context(session, current_tenant_id)
    return found


def report_mailto(address: str | None, *, name: str, repository_id: uuid.UUID) -> str | None:
    """A `mailto:` to the report address with the repository's name and id in the subject, or
    none where no address is set. Everything is percent-encoded, so a name with a line break or an
    ampersand stays in the subject."""
    if not address:
        return None
    subject = f"Report a repository: {' '.join(name.split())} ({repository_id})"
    return f"mailto:{quote(address, safe='@+.-_')}?subject={quote(subject, safe='')}"
