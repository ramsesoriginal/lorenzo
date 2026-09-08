from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from lorenzo_api.db import async_session_factory, engine
from lorenzo_api.models import (
    Entity,
    Information,
    Payload,
    PayloadDescription,
    PayloadDocument,
    PayloadNumber,
    PayloadPicture,
    Tenant,
)


async def test_information_and_payload_bundle_end_to_end() -> None:
    """No resolution/visibility/knowledge system here (ADR 0017) - just
    proving one Information row can bundle all four payload kinds and read
    back correctly.
    """
    async with async_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        entity = Entity(tenant_id=tenant.id, name="Rusty Shovel")
        session.add(entity)
        await session.flush()

        info = Information(
            tenant_id=tenant.id, entity_id=entity.id, title="Shovel lore", type="gm-note"
        )
        session.add(info)
        await session.flush()

        description_payload = Payload(tenant_id=tenant.id, information_id=info.id)
        number_payload = Payload(tenant_id=tenant.id, information_id=info.id)
        picture_payload = Payload(tenant_id=tenant.id, information_id=info.id)
        document_payload = Payload(tenant_id=tenant.id, information_id=info.id)
        session.add_all([description_payload, number_payload, picture_payload, document_payload])
        await session.flush()

        session.add(
            PayloadDescription(
                payload_id=description_payload.id,
                tenant_id=tenant.id,
                locale="en-US",
                content="A shovel, slightly rusty, oddly warm to the touch.",
            )
        )
        session.add(
            PayloadNumber(payload_id=number_payload.id, tenant_id=tenant.id, value=Decimal("2.5"))
        )
        session.add(
            PayloadPicture(
                payload_id=picture_payload.id,
                tenant_id=tenant.id,
                data=b"\x89PNG\r\n\x1a\n",
                file_type="image/png",
            )
        )
        session.add(
            PayloadDocument(
                payload_id=document_payload.id,
                tenant_id=tenant.id,
                data=b"%PDF-1.4",
                filename="shovel-appraisal.pdf",
            )
        )
        await session.commit()

        fetched_info = await session.get(Information, info.id)
        assert fetched_info is not None
        assert fetched_info.title == "Shovel lore"
        assert fetched_info.type == "gm-note"

        description = await session.get(PayloadDescription, description_payload.id)
        assert description is not None
        assert description.locale == "en-US"
        assert description.content == "A shovel, slightly rusty, oddly warm to the touch."

        number = await session.get(PayloadNumber, number_payload.id)
        assert number is not None
        assert number.value == Decimal("2.5")

        picture = await session.get(PayloadPicture, picture_payload.id)
        assert picture is not None
        assert picture.data == b"\x89PNG\r\n\x1a\n"
        assert picture.file_type == "image/png"

        document = await session.get(PayloadDocument, document_payload.id)
        assert document is not None
        assert document.data == b"%PDF-1.4"
        assert document.filename == "shovel-appraisal.pdf"

        # Deleting the tenant cascades through entity/information/payload/
        # payload_* automatically - relationship()+ondelete=CASCADE
        # (ADR 0018) gives the unit of work real dependency ordering.
        await session.delete(tenant)
        await session.commit()


async def test_information_type_is_unique_per_entity() -> None:
    async with async_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        entity = Entity(tenant_id=tenant.id, name="Test Item")
        session.add(entity)
        await session.flush()

        session.add_all(
            [
                Information(
                    tenant_id=tenant.id, entity_id=entity.id, title="First", type="gm-note"
                ),
                Information(
                    tenant_id=tenant.id, entity_id=entity.id, title="Second", type="gm-note"
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            await session.commit()

        # Nothing was actually persisted - the failed commit rolls back the
        # whole transaction, including the tenant/entity flushed earlier.
        await session.rollback()


_DROP_TEST_ROLE_IF_EXISTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rls_test_role') THEN
        EXECUTE 'DROP OWNED BY rls_test_role';
        EXECUTE 'DROP ROLE rls_test_role';
    END IF;
END $$;
"""


async def test_information_rls_isolates_tenants_for_a_non_superuser_role() -> None:
    """information/payload/payload_description/payload_number/
    payload_picture/payload_document all use the byte-for-byte same
    ENABLE+FORCE+policy pattern (confirmed via psql inspection when this
    migration was written) - this proves it works for the new tables at
    least once more, testing information specifically, rather than
    purely extrapolating from every prior table's equivalent proof.
    """
    async with engine.begin() as conn:
        tenant_a = (
            await conn.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()
        tenant_b = (
            await conn.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()

        entity_a = (
            await conn.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'a') RETURNING id"),
                {"t": tenant_a},
            )
        ).scalar_one()
        entity_b = (
            await conn.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'b') RETURNING id"),
                {"t": tenant_b},
            )
        ).scalar_one()

        await conn.execute(text(_DROP_TEST_ROLE_IF_EXISTS))
        await conn.execute(text("CREATE ROLE rls_test_role NOSUPERUSER NOBYPASSRLS NOLOGIN"))
        await conn.execute(text("GRANT SELECT, INSERT ON information TO rls_test_role"))
        await conn.execute(
            text(
                "INSERT INTO information (tenant_id, entity_id, title, type) "
                "VALUES (:t, :e, 'tenant-A-info', 'gm-note')"
            ),
            {"t": tenant_a, "e": entity_a},
        )
        await conn.execute(
            text(
                "INSERT INTO information (tenant_id, entity_id, title, type) "
                "VALUES (:t, :e, 'tenant-B-info', 'gm-note')"
            ),
            {"t": tenant_b, "e": entity_b},
        )

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SET ROLE rls_test_role"))
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_a)}
            )
            titles = (await conn.execute(text("SELECT title FROM information"))).scalars().all()
            assert list(titles) == ["tenant-A-info"]
            await conn.execute(text("RESET ROLE"))

        async with engine.begin() as conn:
            await conn.execute(text("SET ROLE rls_test_role"))
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_b)}
            )
            titles = (await conn.execute(text("SELECT title FROM information"))).scalars().all()
            assert list(titles) == ["tenant-B-info"]
            await conn.execute(text("RESET ROLE"))
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM information WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await conn.execute(
                text("DELETE FROM entity WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await conn.execute(
                text("DELETE FROM tenant WHERE id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await conn.execute(text(_DROP_TEST_ROLE_IF_EXISTS))
