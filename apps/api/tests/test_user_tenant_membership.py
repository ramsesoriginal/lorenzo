import uuid

import pytest
from _admin_db import admin_session_factory
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from lorenzo_api.db import engine
from lorenzo_api.models import Membership, MembershipRole, Tenant, User


async def test_create_and_read_user() -> None:
    """Not RLS-focused - app_user has no tenant_id at all (ADR 0022)."""
    async with admin_session_factory() as session:
        user = User(authgear_subject_id="authgear|abc123")
        session.add(user)
        await session.commit()

        assert user.id is not None
        assert user.created_at is not None
        assert user.updated_at is not None

        fetched = await session.get(User, user.id)
        assert fetched is not None
        assert fetched.authgear_subject_id == "authgear|abc123"

        await session.delete(fetched)
        await session.commit()


async def test_authgear_subject_id_is_globally_unique() -> None:
    async with admin_session_factory() as session:
        session.add_all(
            [
                User(authgear_subject_id="authgear|dupe"),
                User(authgear_subject_id="authgear|dupe"),
            ]
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


async def test_create_and_read_membership_with_role() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        user = User(authgear_subject_id="authgear|owner-1")
        session.add_all([tenant, user])
        await session.flush()

        session.add(Membership(tenant_id=tenant.id, user_id=user.id, role=MembershipRole.OWNER))
        await session.commit()
        tenant_id, user_id = tenant.id, user.id

        fetched = await session.get(Membership, (tenant_id, user_id))
        assert fetched is not None
        assert fetched.role is MembershipRole.OWNER

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_deleting_user_or_tenant_cascades_membership() -> None:
    """The one deliberate exception ADR 0019 already established
    (owner_entity_id -> SET NULL) doesn't apply here - a Membership can't
    meaningfully outlive either side of the (user, tenant) pair it joins.
    """
    async with admin_session_factory() as session:
        tenant_a = Tenant()
        tenant_b = Tenant()
        user_a = User(authgear_subject_id="authgear|cascade-a")
        user_b = User(authgear_subject_id="authgear|cascade-b")
        session.add_all([tenant_a, tenant_b, user_a, user_b])
        await session.flush()
        tenant_a_id, tenant_b_id, user_a_id, user_b_id = (
            tenant_a.id,
            tenant_b.id,
            user_a.id,
            user_b.id,
        )

        session.add_all(
            [
                Membership(tenant_id=tenant_a_id, user_id=user_a_id, role=MembershipRole.OWNER),
                Membership(tenant_id=tenant_b_id, user_id=user_a_id, role=MembershipRole.ORGA),
            ]
        )
        await session.commit()

        # Deleting user_a cascades both of their memberships, leaves
        # tenant_a/tenant_b themselves untouched.
        await session.delete(await session.get_one(User, user_a_id))
        await session.commit()

        assert await session.get(Membership, (tenant_a_id, user_a_id)) is None
        assert await session.get(Membership, (tenant_b_id, user_a_id)) is None
        assert await session.get(Tenant, tenant_a_id) is not None
        assert await session.get(Tenant, tenant_b_id) is not None

        # Deleting a tenant cascades any remaining membership referencing it.
        session.add(Membership(tenant_id=tenant_a_id, user_id=user_b_id, role=MembershipRole.OWNER))
        await session.commit()
        await session.delete(await session.get_one(Tenant, tenant_a_id))
        await session.commit()

        assert await session.get(Membership, (tenant_a_id, user_b_id)) is None
        assert await session.get(User, user_b_id) is not None

        await session.delete(await session.get_one(Tenant, tenant_b_id))
        await session.delete(await session.get_one(User, user_b_id))
        await session.commit()


async def test_membership_rls_isolates_tenants_for_a_non_superuser_role() -> None:
    """Same ENABLE+FORCE+policy pattern as every tenant-scoped table so far.
    `engine` is the app's own real, restricted connection since ADR 0021.
    """
    async with admin_session_factory() as session:
        tenant_a = (
            await session.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()
        tenant_b = (
            await session.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()
        user = (
            await session.execute(
                text("INSERT INTO app_user (authgear_subject_id) VALUES (:s) RETURNING id"),
                {"s": f"authgear|rls-{uuid.uuid4()}"},
            )
        ).scalar_one()

        await session.execute(
            text("INSERT INTO membership (tenant_id, user_id, role) VALUES (:t, :u, 'owner')"),
            {"t": tenant_a, "u": user},
        )
        await session.execute(
            text("INSERT INTO membership (tenant_id, user_id, role) VALUES (:t, :u, 'orga')"),
            {"t": tenant_b, "u": user},
        )
        await session.commit()

    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_a)}
            )
            roles = (await conn.execute(text("SELECT role FROM membership"))).scalars().all()
            assert list(roles) == ["owner"]

        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_b)}
            )
            roles = (await conn.execute(text("SELECT role FROM membership"))).scalars().all()
            assert list(roles) == ["orga"]

        async with engine.begin() as conn:
            with pytest.raises(DBAPIError):
                await conn.execute(text("SELECT role FROM membership"))
    finally:
        async with admin_session_factory() as session:
            await session.execute(
                text("DELETE FROM membership WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(text("DELETE FROM app_user WHERE id = :u"), {"u": user})
            await session.execute(
                text("DELETE FROM tenant WHERE id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.commit()


async def test_app_user_has_no_rls_and_is_globally_readable() -> None:
    """app_user has no tenant_id at all (ADR 0022) - unlike every other
    table, the app's own restricted connection can read it with no
    app.tenant_id set whatsoever, proving it's genuinely not tenant-scoped
    rather than just coincidentally passing today.
    """
    async with admin_session_factory() as session:
        user = User(authgear_subject_id=f"authgear|global-{uuid.uuid4()}")
        session.add(user)
        await session.commit()
        user_id, subject_id = user.id, user.authgear_subject_id

    async with engine.begin() as conn:
        fetched_subject = (
            await conn.execute(
                text("SELECT authgear_subject_id FROM app_user WHERE id = :u"), {"u": user_id}
            )
        ).scalar_one()
        assert fetched_subject == subject_id

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, user_id))
        await session.commit()
