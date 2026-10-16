"""ADR 0285: resolve_information_reader resolves only as much as `can_see` needs.

Nothing for rows that are all public, the tier alone for an admin, and for anyone else, with a row
that is not public among them, exactly what resolve_information_visibility gives.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from _admin_db import admin_engine, admin_session_factory
from conftest import make_campaign, make_player
from sqlalchemy import event

from lorenzo_api.information_visibility import (
    SEES_EVERYTHING,
    InformationVisibility,
    resolve_information_reader,
    resolve_information_visibility,
)
from lorenzo_api.models import (
    Information,
    Membership,
    MembershipRole,
    Tenant,
    TenantAdminCampaignOptOut,
    User,
)


def _row(*, public: bool) -> Information:
    """An Information row as a reader meets it, with no knowledge links."""
    row = Information(entity_id=uuid.uuid4(), tenant_id=uuid.uuid4(), is_public=public)
    row.knowledge_links = []
    return row


@contextmanager
def _statements() -> Iterator[list[str]]:
    seen: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        seen.append(statement)

    event.listen(admin_engine.sync_engine, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(admin_engine.sync_engine, "before_cursor_execute", record)


async def _tenant_and_user(role: MembershipRole | None) -> tuple[uuid.UUID, uuid.UUID]:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = User(authgear_subject_id=f"authgear|info-reader-{uuid.uuid4()}")
        session.add_all([tenant, user])
        await session.flush()
        if role is not None:
            session.add(Membership(tenant_id=tenant.id, user_id=user.id, role=role))
        await session.commit()
        return tenant.id, user.id


async def _remove(tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_public_rows_only_check_for_an_outer_gate() -> None:
    """Public rows need one indexed entry-gate query and no role/knower resolution."""
    tenant_id, user_id = await _tenant_and_user(None)
    try:
        async with admin_session_factory() as session:
            with _statements() as seen:
                reader = await resolve_information_reader(
                    session,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    information=[_row(public=True), _row(public=True)],
                )
            assert reader is SEES_EVERYTHING
            assert len(seen) == 1
            assert "entity_audience" in seen[0]
            assert reader.can_see(_row(public=True))
    finally:
        await _remove(tenant_id, user_id)


async def test_no_rows_at_all_resolve_nothing() -> None:
    tenant_id, user_id = await _tenant_and_user(None)
    try:
        async with admin_session_factory() as session:
            with _statements() as seen:
                reader = await resolve_information_reader(
                    session, user_id=user_id, tenant_id=tenant_id, information=[]
                )
            assert reader is SEES_EVERYTHING
            assert seen == []
    finally:
        await _remove(tenant_id, user_id)


async def test_an_admin_resolves_their_tier_and_nothing_else() -> None:
    """An owner reads a hidden row, and what that costs is their Membership and the opt-out check:
    no player, no character, no GM reach."""
    tenant_id, user_id = await _tenant_and_user(MembershipRole.OWNER)
    try:
        async with admin_session_factory() as session:
            with _statements() as seen:
                reader = await resolve_information_reader(
                    session,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    information=[_row(public=True), _row(public=False)],
                )
            assert reader is SEES_EVERYTHING
            assert reader.can_see(_row(public=False))
            assert len(seen) <= 4, seen
    finally:
        await _remove(tenant_id, user_id)


async def test_an_admin_who_opted_out_is_resolved_in_full() -> None:
    """The opt-out suppresses the bypass (ADR 0096): such an owner reads what a participant reads,
    so the shortcut for admins must not be taken for them."""
    tenant_id, user_id = await _tenant_and_user(MembershipRole.OWNER)
    try:
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=tenant_id)
            session.add(
                TenantAdminCampaignOptOut(
                    tenant_id=tenant_id, user_id=user_id, campaign_id=campaign.id
                )
            )
            await session.commit()
            reader = await resolve_information_reader(
                session,
                user_id=user_id,
                tenant_id=tenant_id,
                information=[_row(public=False)],
            )
            assert isinstance(reader, InformationVisibility)
            assert reader == await resolve_information_visibility(
                session, user_id=user_id, tenant_id=tenant_id
            )
            assert reader.is_admin is False
            assert not reader.can_see(_row(public=False))
    finally:
        await _remove(tenant_id, user_id)


async def test_anyone_else_with_a_hidden_row_gets_the_full_visibility() -> None:
    """A player of a campaign reading a row that is not public: what they may read is resolved
    as it always was."""
    tenant_id, _ = await _tenant_and_user(None)
    try:
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=tenant_id)
            player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
            await session.commit()
            user_id = player.user_id
            reader = await resolve_information_reader(
                session,
                user_id=user_id,
                tenant_id=tenant_id,
                information=[_row(public=True), _row(public=False)],
            )
            assert isinstance(reader, InformationVisibility)
            assert reader == await resolve_information_visibility(
                session, user_id=user_id, tenant_id=tenant_id
            )
            assert reader.player_ids == {player.id}
            assert not reader.can_see(_row(public=False))
            assert reader.can_see(_row(public=True))
    finally:
        async with admin_session_factory() as session:
            await session.delete(await session.get_one(Tenant, tenant_id))
            await session.delete(await session.get_one(User, user_id))
            await session.commit()
