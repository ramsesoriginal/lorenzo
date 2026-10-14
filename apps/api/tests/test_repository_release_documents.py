"""ADR 0214: a release's document in the database - written and read back as the repository's
members and its libraries do, immutable, kept with its files once - and the point of it all:
the copy planner, the update engine and the digest cannot tell it from the rows.
"""

import hashlib
import random
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _content_compare import differences
from _fake_jwks import FakeJwksServer
from _release_world import release_world
from _repository_fixtures import seed_every_content_table
from _upstream_documents import deterministic_ids, in_tenant, read_as_public
from httpx import AsyncClient
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from test_api_release_digest import EDITS
from test_repository_attachments import _copy, _stack, _table

import lorenzo_api.repository_copying as copying
import lorenzo_api.repository_updates as updating
from lorenzo_api import release_document
from lorenzo_api.db import async_session_factory
from lorenzo_api.models import (
    Entity,
    EntityPrototype,
    Item,
    Payload,
    PayloadDocument,
    PayloadPicture,
    RepositoryRelease,
    RepositoryReleaseBlob,
    RepositoryReleaseDocument,
    RepositorySubscription,
    Tenant,
    TenantKind,
)
from lorenzo_api.release_document_store import (
    ReleaseDocumentExistsError,
    ReleaseDocumentNotFoundError,
    ReleaseNotFoundError,
    read_release_content,
    store_release_document,
)
from lorenzo_api.repository_access import reading_repository
from lorenzo_api.repository_content import Content, load_content
from lorenzo_api.repository_digest import digest_of, live_rows

PICTURE = random.Random(1).randbytes(30_000)
DOCUMENT = random.Random(2).randbytes(50_000)


# --- A repository with every kind of row, and files ----------------------------------------


async def _repository(*, files: bool = True, copy_records: bool = True) -> uuid.UUID:
    """A published repository with a row in every content table, and, if asked, a picture
    twice and a document on a note."""
    async with admin_session_factory() as session:
        tenant = Tenant(name="Handouts", kind=TenantKind.REPOSITORY, published_at=datetime.now(UTC))
        session.add(tenant)
        await session.flush()
        await seed_every_content_table(session, tenant.id, with_copy_records=copy_records)
        if files:
            sword = await session.scalar(
                select(Entity.id).where(Entity.tenant_id == tenant.id, Entity.name == "Sword")
            )
            from lorenzo_api.models import Information

            note = Information(
                tenant_id=tenant.id, entity_id=sword, title="Plates", type="note", is_public=True
            )
            session.add(note)
            await session.flush()
            payloads = [
                Payload(tenant_id=tenant.id, information_id=note.id, order=i) for i in range(3)
            ]
            session.add_all(payloads)
            await session.flush()
            session.add_all(
                [
                    PayloadPicture(
                        payload_id=payloads[0].id,
                        tenant_id=tenant.id,
                        data=PICTURE,
                        file_type="png",
                    ),
                    PayloadPicture(
                        payload_id=payloads[1].id,
                        tenant_id=tenant.id,
                        data=PICTURE,
                        file_type="png",
                    ),
                    PayloadDocument(
                        payload_id=payloads[2].id,
                        tenant_id=tenant.id,
                        data=DOCUMENT,
                        filename="maps.pdf",
                        file_type="pdf",
                    ),
                ]
            )
        await session.commit()
        return tenant.id


async def _release(tenant_id: uuid.UUID, number: int) -> uuid.UUID:
    async with admin_session_factory() as session:
        release = RepositoryRelease(tenant_id=tenant_id, number=number + 1, label=f"r{number}")
        session.add(release)
        await session.commit()
        return release.id


async def _delete(*tenant_ids: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        await session.execute(delete(Tenant).where(Tenant.id.in_(tenant_ids)))
        await session.commit()


@asynccontextmanager
async def _as_member(tenant_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """A session as the restricted app role, as a member of the tenant (RLS applies)."""
    async with async_session_factory() as session:
        await in_tenant(session, tenant_id)
        yield session


# --- Writing and reading --------------------------------------------------------------------


async def test_a_stored_document_reads_back_as_the_rows_were_loaded() -> None:
    repository = await _repository()
    release = await _release(repository, 1)
    try:
        async with admin_session_factory() as session:
            loaded = await load_content(session, repository)
        async with _as_member(repository) as session:
            stored = await store_release_document(
                session, tenant_id=repository, release_id=release, content=loaded
            )
            await session.commit()
        async with _as_member(repository) as session:
            back = await read_release_content(session, tenant_id=repository, release_id=release)

        assert differences(loaded, back) == []
        assert stored.format == release_document.FORMAT and stored.size > 0
        # The fixture's picture and document, and ours: four files, the picture once, and one
        # of them (the fixture's picture) was stored with its seed release already.
        assert (stored.files, stored.new_files) == (4, 3)
    finally:
        await _delete(repository)


async def test_the_files_of_two_releases_are_stored_once() -> None:
    repository = await _repository()
    first, second = await _release(repository, 1), await _release(repository, 2)
    try:
        async with admin_session_factory() as session:
            loaded = await load_content(session, repository)
            one = await store_release_document(
                session, tenant_id=repository, release_id=first, content=loaded
            )
            two = await store_release_document(
                session, tenant_id=repository, release_id=second, content=loaded
            )
            await session.commit()

            assert (one.new_files, two.new_files) == (3, 0)
            assert two.files == 4
            kept = (
                await session.execute(
                    select(func.count(), func.sum(func.length(RepositoryReleaseBlob.data))).where(
                        RepositoryReleaseBlob.tenant_id == repository
                    )
                )
            ).one()
            # The picture's bytes are there once, though two payloads and two documents use them.
            assert kept == (4, len(PICTURE) + len(DOCUMENT) + len(b"\x89PNG") + len(b"%PDF"))
            lists = set(
                await session.scalars(
                    select(func.array_to_string(RepositoryReleaseDocument.blobs, ",")).where(
                        RepositoryReleaseDocument.release_id.in_([first, second])
                    )
                )
            )
            names = ",".join(
                sorted(
                    hashlib.sha256(b).hexdigest() for b in (PICTURE, DOCUMENT, b"\x89PNG", b"%PDF")
                )
            )
            assert lists == {names}
    finally:
        await _delete(repository)


async def test_the_same_files_in_two_repositories_are_two_rows() -> None:
    one, two = await _repository(), await _repository()
    release_one, release_two = await _release(one, 1), await _release(two, 1)
    try:
        async with admin_session_factory() as session:
            for repository, release in ((one, release_one), (two, release_two)):
                await store_release_document(
                    session,
                    tenant_id=repository,
                    release_id=release,
                    content=await load_content(session, repository),
                )
            await session.commit()
            count = await session.scalar(
                select(func.count()).where(RepositoryReleaseBlob.tenant_id.in_([one, two]))
            )
            assert count == 8
    finally:
        await _delete(one, two)


async def test_a_release_has_one_document_and_it_is_never_replaced() -> None:
    repository = await _repository(files=False)
    release = await _release(repository, 1)
    try:
        async with admin_session_factory() as session:
            loaded = await load_content(session, repository)
            await store_release_document(
                session, tenant_id=repository, release_id=release, content=loaded
            )
            await session.commit()
            with pytest.raises(ReleaseDocumentExistsError):
                await store_release_document(
                    session, tenant_id=repository, release_id=release, content=loaded
                )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(RepositoryReleaseDocument)
                    .where(RepositoryReleaseDocument.release_id == release)
                )
                == 1
            )
    finally:
        await _delete(repository)


async def test_a_document_is_written_for_a_release_of_that_repository_and_its_own_content() -> None:
    mine, other = await _repository(files=False), await _repository(files=False)
    their_release = await _release(other, 1)
    my_release = await _release(mine, 1)
    try:
        async with admin_session_factory() as session:
            loaded = await load_content(session, mine)
            with pytest.raises(ReleaseNotFoundError):
                await store_release_document(
                    session, tenant_id=mine, release_id=their_release, content=loaded
                )
            with pytest.raises(release_document.ReleaseDocumentError, match="not of"):
                await store_release_document(
                    session,
                    tenant_id=mine,
                    release_id=my_release,
                    content=await load_content(session, other),
                )
            # And the database says the same without the code's help: the key has the tenant.
            session.add(
                RepositoryReleaseDocument(
                    release_id=their_release,
                    tenant_id=mine,
                    format=1,
                    content=b"x",
                    blobs=[],
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()
    finally:
        await _delete(mine, other)


async def test_a_release_nobody_wrote_a_document_for_has_none_to_read() -> None:
    repository = await _repository(files=False)
    release = await _release(repository, 1)
    try:
        async with admin_session_factory() as session:
            with pytest.raises(ReleaseDocumentNotFoundError):
                await read_release_content(session, tenant_id=repository, release_id=release)
    finally:
        await _delete(repository)


async def test_a_file_that_has_gone_makes_the_document_corrupt() -> None:
    repository = await _repository()
    release = await _release(repository, 1)
    try:
        async with admin_session_factory() as session:
            await store_release_document(
                session,
                tenant_id=repository,
                release_id=release,
                content=await load_content(session, repository),
            )
            await session.execute(
                delete(RepositoryReleaseBlob).where(
                    RepositoryReleaseBlob.sha256 == hashlib.sha256(PICTURE).hexdigest()
                )
            )
            await session.commit()
            with pytest.raises(release_document.ReleaseDocumentCorruptError, match="file"):
                await read_release_content(session, tenant_id=repository, release_id=release)
    finally:
        await _delete(repository)


async def test_a_document_in_a_format_nobody_reads_is_refused() -> None:
    repository = await _repository(files=False)
    release = await _release(repository, 1)
    try:
        async with admin_session_factory() as session:
            await store_release_document(
                session,
                tenant_id=repository,
                release_id=release,
                content=await load_content(session, repository),
            )
            await session.commit()
        async with admin_session_factory() as session:
            # Immutable, so the way to get one is to write it so.
            await session.execute(
                text("ALTER TABLE repository_release_document DISABLE TRIGGER USER")
            )
            await session.execute(
                update(RepositoryReleaseDocument)
                .where(RepositoryReleaseDocument.release_id == release)
                .values(format=2)
            )
            await session.execute(
                text("ALTER TABLE repository_release_document ENABLE TRIGGER USER")
            )
            await session.commit()
            with pytest.raises(release_document.UnknownDocumentFormatError):
                await read_release_content(session, tenant_id=repository, release_id=release)
    finally:
        await _delete(repository)


# --- Immutable -------------------------------------------------------------------------------


async def test_neither_a_document_nor_a_file_can_be_changed_but_both_can_go() -> None:
    repository = await _repository()
    release = await _release(repository, 1)
    try:
        async with admin_session_factory() as session:
            await store_release_document(
                session,
                tenant_id=repository,
                release_id=release,
                content=await load_content(session, repository),
            )
            await session.commit()

        # Not even the role that owns the tables.
        for statement in (
            "UPDATE repository_release_document SET content = '\\x00' WHERE release_id = :r",
            "UPDATE repository_release_document SET format = 9 WHERE release_id = :r",
            "UPDATE repository_release_blob SET data = '\\x00' WHERE tenant_id = :t",
        ):
            async with admin_session_factory() as session:
                with pytest.raises(DBAPIError, match="can't change"):
                    await session.execute(text(statement), {"r": release, "t": repository})

        # And not the app role, as the repository's own member.
        async with _as_member(repository) as session:
            with pytest.raises(DBAPIError, match="can't change"):
                await session.execute(
                    text("UPDATE repository_release_document SET format = 9 WHERE release_id = :r"),
                    {"r": release},
                )

        async with _as_member(repository) as session:
            await session.execute(delete(RepositoryReleaseDocument))
            await session.execute(delete(RepositoryReleaseBlob))
            await session.commit()
        async with admin_session_factory() as session:
            for model in (RepositoryReleaseDocument, RepositoryReleaseBlob):
                assert not await session.scalar(
                    select(func.count()).where(model.tenant_id == repository)
                )
    finally:
        await _delete(repository)


async def test_a_document_goes_with_its_release_and_a_release_with_its_repository() -> None:
    repository = await _repository()
    release = await _release(repository, 1)
    async with admin_session_factory() as session:
        await store_release_document(
            session,
            tenant_id=repository,
            release_id=release,
            content=await load_content(session, repository),
        )
        await session.commit()
        await session.execute(delete(RepositoryRelease).where(RepositoryRelease.id == release))
        await session.commit()
        assert not await session.scalar(
            select(func.count()).where(RepositoryReleaseDocument.release_id == release)
        )
        # The document of the release that was seeded with the repository is still there.
        assert await session.scalar(
            select(func.count()).where(RepositoryReleaseDocument.tenant_id == repository)
        )
    await _delete(repository)
    async with admin_session_factory() as session:
        for model in (RepositoryReleaseDocument, RepositoryReleaseBlob):
            assert not await session.scalar(
                select(func.count()).where(model.tenant_id == repository)
            )


# --- Who reads it -----------------------------------------------------------------------------


async def test_a_library_reads_a_granted_published_repositorys_document_and_nobody_else_does() -> (
    None
):
    repository = await _repository()
    release = await _release(repository, 1)
    async with admin_session_factory() as session:
        library = Tenant(name="A table")
        stranger = Tenant(name="Somebody else")
        session.add_all([library, stranger])
        await session.flush()
        loaded = await load_content(session, repository)
        await store_release_document(
            session, tenant_id=repository, release_id=release, content=loaded
        )
        await session.commit()
        library_id, stranger_id = library.id, stranger.id

    async def read_as(tenant: uuid.UUID) -> Content:
        async with _as_member(tenant) as session, reading_repository(session, repository):
            return await read_release_content(session, tenant_id=repository, release_id=release)

    try:
        # Not granted: the rows are not there for it.
        with pytest.raises(ReleaseDocumentNotFoundError):
            await read_as(library_id)

        async with admin_session_factory() as session:
            session.add(
                RepositorySubscription(
                    repository_tenant_id=repository, subscriber_tenant_id=library_id
                )
            )
            await session.commit()
        assert differences(loaded, await read_as(library_id)) == []
        # Granted to somebody else is not granted to this one.
        with pytest.raises(ReleaseDocumentNotFoundError):
            await read_as(stranger_id)
        # Outside the gated read, even the granted library sees nothing.
        async with _as_member(library_id) as session:
            with pytest.raises(ReleaseDocumentNotFoundError):
                await read_release_content(session, tenant_id=repository, release_id=release)

        # Unpublished again: closed.
        async with admin_session_factory() as session:
            (await session.get_one(Tenant, repository)).published_at = None
            await session.commit()
        with pytest.raises(ReleaseDocumentNotFoundError):
            await read_as(library_id)
    finally:
        await _delete(repository, library_id, stranger_id)


async def test_a_library_cannot_write_a_document() -> None:
    repository = await _repository(files=False)
    release = await _release(repository, 1)
    async with admin_session_factory() as session:
        library = Tenant(name="A table")
        session.add(library)
        await session.flush()
        session.add(
            RepositorySubscription(repository_tenant_id=repository, subscriber_tenant_id=library.id)
        )
        loaded = await load_content(session, repository)
        await session.commit()
        library_id = library.id
    try:
        async with _as_member(library_id) as session, reading_repository(session, repository):
            # The library can read the release, so it is the write that is refused.
            with pytest.raises(DBAPIError, match="row-level security"):
                async with session.begin_nested():
                    await store_release_document(
                        session, tenant_id=repository, release_id=release, content=loaded
                    )
    finally:
        await _delete(repository, library_id)


# --- The point: the engines cannot tell it from the rows -------------------------------------


async def _documents(*repositories: uuid.UUID) -> dict[uuid.UUID, Content]:
    """Each repository's content written to a new release and read back, as the engines will
    read it."""
    documents: dict[uuid.UUID, Content] = {}
    for repository in repositories:
        async with admin_session_factory() as session:
            number = (
                await session.scalar(
                    select(func.coalesce(func.max(RepositoryRelease.number), 0)).where(
                        RepositoryRelease.tenant_id == repository
                    )
                )
                or 0
            ) + 1
        release = await _release(repository, number)
        async with admin_session_factory() as session:
            await store_release_document(
                session,
                tenant_id=repository,
                release_id=release,
                content=await load_content(session, repository),
            )
            await session.commit()
        async with admin_session_factory() as session:
            documents[repository] = await read_release_content(
                session, tenant_id=repository, release_id=release
            )
    return documents


async def _plan(
    library: uuid.UUID, repository: uuid.UUID, documents: dict[uuid.UUID, Content]
) -> copying.Plan:
    async with admin_session_factory() as session:
        await in_tenant(session, library)
        async with read_as_public(documents):
            with deterministic_ids():
                plan = await copying.plan_copy(
                    session,
                    tenant_id=library,
                    repository_id=repository,
                    user_id=uuid.UUID(int=7),
                    resolutions=[],
                )
        # What differs by design: a step of a public repository says it can be read without a
        # grant, and the library here holds one, which is the same plan.
        for step in plan.steps:
            step.public = False
        return plan


async def _updates(
    library: uuid.UUID, repository: uuid.UUID, documents: dict[uuid.UUID, Content]
) -> updating.Updates:
    async with admin_session_factory() as session:
        await in_tenant(session, library)
        async with read_as_public(documents):
            return await updating.compute_updates(
                session, tenant_id=library, repository_id=repository
            )


async def test_a_first_copy_of_a_bridge_is_planned_the_same_from_the_documents(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    _, table = await _table(raw_client, fake_jwks_server, stack, "gm")
    try:
        documents = await _documents(stack.equipment, stack.rules, stack.bridge)

        from_rows = await _plan(table, stack.bridge, {})
        from_documents = await _plan(table, stack.bridge, documents)

        assert [(s.name, s.attachments) for s in from_rows.steps] == [
            ("Common Equipment", 0),
            ("D&D 5e", 0),
            ("D&D Equipment", 3),
        ]
        assert differences(from_rows, from_documents) == []
        # And each of the repositories alone.
        for repository in (stack.equipment, stack.rules):
            assert (
                differences(
                    await _plan(table, repository, {}), await _plan(table, repository, documents)
                )
                == []
            )
    finally:
        await cleanup_stack(stack)


async def cleanup_stack(stack: Any) -> None:
    from _repository_actors import cleanup

    await cleanup(stack.tenants, stack.actors)


async def test_the_updates_of_a_bridge_are_the_same_from_the_documents(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    gm, table = await _table(raw_client, fake_jwks_server, stack, "gm")
    try:
        await _copy(gm, table, stack.bridge)
        async with admin_session_factory() as session:
            # Nothing changed since the copy: no updates, from the rows or from a document.
            quiet = await _documents(stack.equipment, stack.rules, stack.bridge)
            for repository in (stack.equipment, stack.rules, stack.bridge):
                assert (
                    differences(
                        await _updates(table, repository, {}),
                        await _updates(table, repository, quiet),
                    )
                    == []
                )

            # The repositories change: a rename and a new item in the equipment, an attachment
            # more in the bridge, the rules' root renamed.
            equipment = {
                e.name: e
                for e in (
                    await session.scalars(select(Entity).where(Entity.tenant_id == stack.equipment))
                ).all()
            }
            equipment["Dagger"].name = "Dirk"
            spear = Entity(tenant_id=stack.equipment, name="Spear")
            session.add(spear)
            await session.flush()
            session.add(Item(entity_id=spear.id, tenant_id=stack.equipment))
            session.add(
                EntityPrototype(
                    entity_id=spear.id,
                    prototype_id=equipment["Weapon"].id,
                    tenant_id=stack.equipment,
                )
            )
            (
                await session.scalar(
                    select(Entity).where(Entity.tenant_id == stack.rules, Entity.name == "D&D 5e")
                )
            ).name = "D&D Fifth"  # type: ignore[union-attr]
            bridge = {
                e.name: e
                for e in (
                    await session.scalars(select(Entity).where(Entity.tenant_id == stack.bridge))
                ).all()
            }
            session.add(
                EntityPrototype(
                    entity_id=bridge["Dagger"].id,
                    prototype_id=bridge["Economic Object"].id,
                    tenant_id=stack.bridge,
                )
            )
            await session.commit()

        documents = await _documents(stack.equipment, stack.rules, stack.bridge)
        for repository in (stack.equipment, stack.rules, stack.bridge):
            from_rows = await _updates(table, repository, {})
            from_documents = await _updates(table, repository, documents)
            assert differences(from_rows, from_documents) == []
        # It was not an empty comparison.
        equipment_updates = await _updates(table, stack.equipment, documents)
        assert {c.name for c in equipment_updates.changed} == {"Dagger"}
        assert [a.name for a in equipment_updates.added] == ["Spear"]
        assert [len((await _updates(table, stack.bridge, documents)).attachments_added)] == [1]
    finally:
        await cleanup_stack(stack)


async def test_the_digest_of_a_document_is_the_digest_the_publish_recorded(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    try:
        documents = await _documents(stack.equipment, stack.rules, stack.bridge)
        async with admin_session_factory() as session:
            for repository in (stack.equipment, stack.rules, stack.bridge):
                published = await session.scalar(
                    select(RepositoryRelease.digest).where(
                        RepositoryRelease.tenant_id == repository, RepositoryRelease.number == 1
                    )
                )
                loaded = await load_content(session, repository)
                assert published
                assert digest_of(live_rows(documents[repository]).values()) == published
                assert live_rows(documents[repository]) == live_rows(loaded)
        # And the bridge's attachments are in what was hashed.
        assert any(k[0] == "attachment" for k in live_rows(documents[stack.bridge]))
    finally:
        await cleanup_stack(stack)


@pytest.mark.parametrize("scenario", ["every change but a removal", "a removal"])
async def test_the_updates_after_a_change_in_every_compared_field_are_the_same(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, scenario: str
) -> None:
    world = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        edits = ["removal"] if scenario == "a removal" else sorted(set(EDITS) - {"removal"})
        for edit in edits:
            await EDITS[edit][0](world)
        documents = await _documents(world.repository)

        from_rows = await _updates(world.table, world.repository, {})
        from_documents = await _updates(world.table, world.repository, documents)

        assert differences(from_rows, from_documents) == []
        if scenario == "a removal":
            assert len(from_rows.removed) == 1
        else:
            fields = {f.field.split(":")[0] for c in from_rows.changed for f in c.fields}
            assert {
                "name",
                "slug",
                "prototypes",
                "stat_groups",
                "stats",
                "formulas",
                "enum_values",
                "value_type",
                "priority",
            } <= fields
            assert len(from_rows.added) == 1
    finally:
        await world.done()


async def test_a_first_copy_of_the_armoury_is_planned_the_same_from_a_document(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server)
    try:
        documents = await _documents(world.repository)
        assert (
            differences(
                await _plan(world.table, world.repository, {}),
                await _plan(world.table, world.repository, documents),
            )
            == []
        )
    finally:
        await world.done()


async def test_a_first_copy_with_pictures_and_documents_carries_their_bytes_from_the_document() -> (
    None
):
    repository = await _repository(copy_records=False)
    async with admin_session_factory() as session:
        library = Tenant(name="A table")
        session.add(library)
        await session.flush()
        session.add(
            RepositorySubscription(repository_tenant_id=repository, subscriber_tenant_id=library.id)
        )
        await session.commit()
        library_id = library.id
    try:
        documents = await _documents(repository)
        from_rows = await _plan(library_id, repository, {})
        from_documents = await _plan(library_id, repository, documents)

        assert differences(from_rows, from_documents) == []
        pictures = from_documents.rows["payload_picture"]
        assert [p["data"] for p in pictures].count(PICTURE) == 2
        assert [p["data"] for p in from_documents.rows["payload_document"]].count(DOCUMENT) == 1
    finally:
        await _delete(repository, library_id)


async def test_the_comparison_notices_when_a_document_is_not_the_rows(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The tests above are only as good as their means of telling: rows edited after the
    document was made give other updates from the rows than from the document."""
    world = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        documents = await _documents(world.repository)
        assert (
            differences(
                await _updates(world.table, world.repository, {}),
                await _updates(world.table, world.repository, documents),
            )
            == []
        )

        async with admin_session_factory() as session:
            (await session.get_one(Entity, world.ids["Longsword"])).name = "Tampered with"
            await session.commit()
        from_rows = await _updates(world.table, world.repository, {})
        from_documents = await _updates(world.table, world.repository, documents)

        assert [c.fields[0].field for c in from_rows.changed] == ["name"]
        assert from_documents.changed == []
        assert differences(from_rows, from_documents)
    finally:
        await world.done()
