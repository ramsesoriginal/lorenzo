"""Invite links of every kind, core mechanics only - see ADR 0092/RFC 0023, ADR 0220.

No auth and no commit (matching `notifications`/`activity_log`): the routes
in `routers/invites.py` (public preview/redeem), `routers/campaign_invites.py` (a
campaign's links) and `routers/tenant_invites.py` (a library's or repository's) call these, then
commit themselves.

The token itself is never stored or logged. It is 256 random bits; only its
SHA-256 is kept, so the lookup is one indexed equality on `token_hash`.
"""

import hashlib
import secrets
import uuid
from datetime import timedelta

from sqlalchemy import ColumnElement, and_, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import Invite

# A link always ends, and not too far off (ADR 0092). The one number in the
# design that was the ADR's own assumption rather than an answered
# question - a constant, trivial to change.
MAX_INVITE_LIFETIME = timedelta(days=30)

# A GM link is single use and shorter-lived than a player link (ADR 0177):
# an unredeemed one is the exposure, so it ends within a week.
MAX_GM_INVITE_LIFETIME = timedelta(days=7)

# The links of ADR 0220, which are not for a campaign and so are always capped. An Author or
# Organizer link ends within a week, as a GM link does: it hands over a role. A library-access
# link may live as long as a player link. A link made without an expiry gets the default, which
# is shorter than the longest. Only Author and library links may be raised above a single use,
# and no higher than the ceiling: one link can bring in a small team, never an unlimited one.
MAX_ROLE_INVITE_LIFETIME = timedelta(days=7)
DEFAULT_ROLE_INVITE_LIFETIME = timedelta(days=3)
MAX_LIBRARY_INVITE_LIFETIME = timedelta(days=30)
DEFAULT_LIBRARY_INVITE_LIFETIME = timedelta(days=7)
MAX_SHARED_INVITE_USES = 10


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    # No salt and no slow KDF: the input is already 256 unguessable bits.
    return hashlib.sha256(token.encode()).hexdigest()


def _is_live() -> ColumnElement[bool]:
    """Not revoked, not expired, and not out of uses (a NULL `max_uses`
    is unlimited). Evaluated in SQL against the database's own clock.
    """
    return and_(
        Invite.revoked_at.is_(None),
        Invite.expires_at > func.now(),
        or_(Invite.max_uses.is_(None), Invite.use_count < Invite.max_uses),
    )


async def find_live_invite(session: AsyncSession, token: str) -> Invite | None:
    """The invite for this token, or None - and None for *every* reason it
    might not be usable (unknown, expired, revoked, exhausted), so a caller
    can't tell them apart (ADR 0092). One indexed lookup either way.

    Sets `app.invite_token_hash` first: the caller doesn't know the tenant
    yet, so the select-only `invite_by_token` policy is what lets
    this one row be read at all. Transaction-local (`is_local=true`), so it
    lapses at the next commit.
    """
    token_hash = hash_token(token)
    await session.execute(
        text("SELECT set_config('app.invite_token_hash', :h, true)"), {"h": token_hash}
    )
    stmt = select(Invite).where(Invite.token_hash == token_hash, _is_live())
    return (await session.execute(stmt)).scalar_one_or_none()


async def consume_invite(session: AsyncSession, invite_id: uuid.UUID) -> bool:
    """Spends one use, atomically. A single `UPDATE ... WHERE <still live>
    RETURNING`, never read-then-write, so concurrent redemptions cannot
    push `use_count` past a set `max_uses`. Returns False if the invite
    stopped being live between the lookup and now (it ran out, expired, or
    was revoked in the meantime).
    """
    stmt = (
        update(Invite)
        .where(Invite.id == invite_id, _is_live())
        .values(use_count=Invite.use_count + 1)
        .returning(Invite.id)
    )
    return (await session.execute(stmt)).first() is not None
