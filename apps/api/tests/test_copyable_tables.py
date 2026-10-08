"""The registry of copyable tables (ADR 0218): every tenant table is in it, and a copy has a place
and a step for every table it says it copies. A table added without them fails here, loudly,
instead of being left out of a copy without a word.
"""

import uuid
from datetime import UTC, datetime

from _admin_db import admin_session_factory
from _repository_fixtures import seed_every_content_table
from sqlalchemy import text

from lorenzo_api.copyable_tables import (
    COPIED_TABLES,
    COPY_LINKS,
    LINK_MODELS,
    PURGE_COUNTED,
    REGISTRY,
)
from lorenzo_api.models import RepositorySubscription, Tenant, TenantKind
from lorenzo_api.repository_copying import plan_copy

_BY_NAME = {t.name: t for t in REGISTRY}


async def _tenant_tables() -> set[str]:
    """Every table that stores tenant data: a tenant_id column and row-level security on."""
    async with admin_session_factory() as session:
        return set(
            (
                await session.execute(
                    text(
                        """
                        SELECT c.relname FROM pg_class c
                        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id'
                        WHERE c.relkind = 'r' AND c.relnamespace = 'public'::regnamespace
                          AND c.relrowsecurity
                        """
                    )
                )
            ).scalars()
        )


def test_the_registry_lists_each_table_once_and_its_own_model() -> None:
    names = [t.name for t in REGISTRY]
    assert len(names) == len(set(names)), sorted(n for n in names if names.count(n) > 1)
    for table in REGISTRY:
        assert table.model.__tablename__ == table.name


async def test_every_tenant_table_is_in_the_registry() -> None:
    """A new tenant table gets a model and a line in lorenzo_api.copyable_tables."""
    in_database = await _tenant_tables()
    registered = set(_BY_NAME)
    assert in_database - registered == set(), "tenant tables missing from the registry"
    assert registered - in_database == set(), "registry lines for tables that are not tenant tables"


async def test_content_tables_have_the_read_policy_and_the_rest_do_not() -> None:
    async with admin_session_factory() as session:
        with_policy = {
            name.strip('"')
            for name in (
                await session.execute(
                    text(
                        "SELECT polrelid::regclass::text FROM pg_policy "
                        "WHERE polname = 'repository_read'"
                    )
                )
            ).scalars()
        }
    assert with_policy == {t.name for t in REGISTRY if t.content}


def test_what_a_table_is_carried_by_is_a_copied_table() -> None:
    for table in REGISTRY:
        if table.carried_by is None:
            continue
        assert table.copy == "rows", table.name
        assert _BY_NAME[table.carried_by].copy == "rows", (table.name, table.carried_by)
        assert table.carried_by != table.name


def test_only_copied_and_link_tables_say_what_they_are() -> None:
    for table in REGISTRY:
        assert (table.link_of is not None) == (table.copy == "link"), table.name
        if table.copy != "rows":
            assert table.carried_by is None and not table.counted_on_purge, table.name


def test_the_derived_lists_are_the_registry_in_order() -> None:
    assert [name for name, _ in COPIED_TABLES] == [t.name for t in REGISTRY if t.copy == "rows"]
    assert [key for key, _, _ in COPY_LINKS] == [
        "link_entity",
        "link_stat_group",
        "link_stat_definition",
    ]
    assert [column for _, _, column in COPY_LINKS] == [
        "entity_id",
        "stat_group_id",
        "stat_definition_id",
    ]
    assert len(LINK_MODELS) == 4  # the three copy links and the attachment link
    assert "attachment" in PURGE_COUNTED
    assert PURGE_COUNTED - {"attachment"} <= {name for name, _ in COPIED_TABLES}


async def test_a_copy_inserts_a_row_after_the_rows_it_points_to() -> None:
    """The order of the registry is the order of the inserts: a foreign key between two copied
    tables must point backwards in it, or a copy fails on a repository that has such a row."""
    position = {name: i for i, (name, _) in enumerate(COPIED_TABLES)}
    async with admin_session_factory() as session:
        keys = (
            await session.execute(
                text(
                    """
                    SELECT c.conrelid::regclass::text AS child,
                           c.confrelid::regclass::text AS parent
                    FROM pg_constraint c
                    WHERE c.contype = 'f' AND c.conrelid <> c.confrelid
                    """
                )
            )
        ).all()
    wrong = sorted(
        (child, parent)
        for child, parent in ((k.child.strip('"'), k.parent.strip('"')) for k in keys)
        if child in position and parent in position and position[parent] > position[child]
    )
    assert wrong == [], "a copied table comes before a table it references"


async def test_a_copy_has_a_step_for_every_table_the_registry_says_it_copies() -> None:
    """Plans a copy of a repository with a row in every table, and holds what the planner writes to
    the registry in both directions: a copied table the planner writes nothing for has no step (or
    the seed lacks a row for it), and rows for a table the registry does not copy would be left
    out of the copy without an error."""
    async with admin_session_factory() as session:
        repository = Tenant(name="Faerûn", kind=TenantKind.REPOSITORY)
        library = Tenant(name="My Table")
        session.add_all([repository, library])
        await session.flush()
        await seed_every_content_table(session, repository.id)
        session.add(
            RepositorySubscription(
                repository_tenant_id=repository.id, subscriber_tenant_id=library.id
            )
        )
        repository.published_at = datetime.now(UTC)
        await session.commit()
        repository_id, library_id = repository.id, library.id
    try:
        async with admin_session_factory() as session:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(library_id)}
            )
            plan = await plan_copy(
                session,
                tenant_id=library_id,
                repository_id=repository_id,
                user_id=uuid.uuid4(),
                resolutions=[],
            )
        planned = {key for key, rows in plan.rows.items() if rows}
        expected: set[str] = {name for name, _ in COPIED_TABLES} | {key for key, _, _ in COPY_LINKS}
        assert planned - expected == set(), "the planner writes rows for tables a copy ignores"
        assert expected - planned == set(), "no planner step wrote rows for these copied tables"
    finally:
        async with admin_session_factory() as session:
            for tenant_id in (library_id, repository_id):
                await session.delete(await session.get_one(Tenant, tenant_id))
            await session.commit()
