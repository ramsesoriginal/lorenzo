"""ADR 0285 addendum (R2, RFC 0037): the update engine finds the local row of each end of an
attachment through one inversion of the copy links, made once, and not one for each end of each
attachment, which was the square of the content: `updates` of a bridge of 20,000 entries took
12 to 16 s against 4 to 5 s for a repository of the same size.
"""

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient
from sqlalchemy import select
from test_repository_attachments import _by_name, _copy, _stack, _table

from lorenzo_api.models import EntityPrototype
from lorenzo_api.repository_content import Links


async def test_the_entity_links_are_inverted_a_fixed_number_of_times_however_many_attachments(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: object
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    gm, table = await _table(raw_client, fake_jwks_server, stack, "gm")
    try:
        await _copy(gm, table, stack.bridge)
        # The bridge attaches three more parents to the entries it copied: three attachments the
        # library has not taken, each with two ends to find.
        async with admin_session_factory() as session:
            copies = await _by_name(stack.bridge)
            existing = set(
                (
                    await session.execute(
                        select(EntityPrototype.entity_id, EntityPrototype.prototype_id).where(
                            EntityPrototype.tenant_id == stack.bridge
                        )
                    )
                ).all()
            )
            added = 0
            for child, parent in (
                ("Dagger", "Economic Object"),
                ("Longsword", "Economic Object"),
                ("Dagger", "D&D 5e"),
            ):
                if (copies[child], copies[parent]) not in existing:
                    session.add(
                        EntityPrototype(
                            entity_id=copies[child],
                            prototype_id=copies[parent],
                            tenant_id=stack.bridge,
                        )
                    )
                    added += 1
            await session.commit()
        assert added >= 2

        calls: list[str] = []
        real = Links.local_of

        def counting(self: Links, kind: str):  # type: ignore[no-untyped-def]
            calls.append(kind)
            return real(self, kind)

        monkeypatch.setattr(Links, "local_of", counting)  # type: ignore[attr-defined]
        response = await gm.get(f"/tenants/{table}/repositories/{stack.bridge}/updates")

        assert response.status_code == 200, response.text
        assert len(response.json()["attachments_added"]) >= 2
        # One inversion for the engine's own maps and one for the attachments, whatever their
        # number: before, two more for each end of each one.
        assert calls.count("entity") <= 3, calls
    finally:
        from _repository_actors import cleanup

        await cleanup(stack.tenants, stack.actors)
