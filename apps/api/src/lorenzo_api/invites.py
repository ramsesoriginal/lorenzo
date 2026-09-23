"""Campaign invite links, core mechanics only - see ADR 0092/RFC 0023.

No auth and no commit (matching `notifications`/`activity_log`): the routes
in `routers/invites.py` (public preview/redeem) and
`routers/campaign_invites.py` (management) call these, then commit
themselves.

The token itself is never stored or logged. It is 256 random bits; only its
SHA-256 is kept, so the lookup is one indexed equality on `token_hash`.
"""

import hashlib
import secrets
import uuid
from datetime import timedelta

from sqlalchemy import ColumnElement, and_, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import CampaignInvite

# A link always ends, and not too far off (ADR 0092). The one number in the
# design that was the ADR's own assumption rather than an answered
# question - a constant, trivial to change.
MAX_INVITE_LIFETIME = timedelta(days=30)


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
        CampaignInvite.revoked_at.is_(None),
        CampaignInvite.expires_at > func.now(),
        or_(CampaignInvite.max_uses.is_(None), CampaignInvite.use_count < CampaignInvite.max_uses),
    )


async def find_live_invite(session: AsyncSession, token: str) -> CampaignInvite | None:
    """The invite for this token, or None - and None for *every* reason it
    might not be usable (unknown, expired, revoked, exhausted), so a caller
    can't tell them apart (ADR 0092). One indexed lookup either way.

    Sets `app.invite_token_hash` first: the caller doesn't know the tenant
    yet, so the select-only `campaign_invite_by_token` policy is what lets
    this one row be read at all. Transaction-local (`is_local=true`), so it
    lapses at the next commit.
    """
    token_hash = hash_token(token)
    await session.execute(
        text("SELECT set_config('app.invite_token_hash', :h, true)"), {"h": token_hash}
    )
    stmt = select(CampaignInvite).where(CampaignInvite.token_hash == token_hash, _is_live())
    return (await session.execute(stmt)).scalar_one_or_none()


async def consume_invite(session: AsyncSession, invite_id: uuid.UUID) -> bool:
    """Spends one use, atomically. A single `UPDATE ... WHERE <still live>
    RETURNING`, never read-then-write, so concurrent redemptions cannot
    push `use_count` past a set `max_uses`. Returns False if the invite
    stopped being live between the lookup and now (it ran out, expired, or
    was revoked in the meantime).
    """
    stmt = (
        update(CampaignInvite)
        .where(CampaignInvite.id == invite_id, _is_live())
        .values(use_count=CampaignInvite.use_count + 1)
        .returning(CampaignInvite.id)
    )
    return (await session.execute(stmt)).first() is not None
