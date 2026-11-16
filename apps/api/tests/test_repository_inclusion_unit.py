"""ADR 0431: the pure parts of including a source in a release, with a `Content` in memory - which
rows are a copy of an included repository's and what becomes of the links that said so, what a
change of the choice is, and what A's terms say when nobody has said anything. The database and the
routes are in test_repository_include.py.
"""

import uuid

from _content_compare import differences
from _content_fixtures import full_content

from lorenzo_api import release_document as rd
from lorenzo_api.models import RepositoryProfile
from lorenzo_api.repository_content import Content
from lorenzo_api.repository_inclusion import (
    default_may_be_included,
    flatten,
    included_by,
    inclusion_changes,
    recorded_inclusions,
    release_sources_of,
    terms_of,
)


def _id(n: int) -> uuid.UUID:
    return uuid.UUID(int=n)


UPSTREAM = _id(60)  # the repository `full_content` copied rows from
OTHER = _id(80)  # another one it copied


def _two_sources() -> Content:
    """Rows copied from A (UPSTREAM) and from Z, a group A merged into one of its own, a stat
    deleted from A and one from Z, attachments from both."""
    c = Content(tenant_id=_id(1))
    from_a, from_z, from_a2, merged_group, z_group = (_id(n) for n in (100, 101, 102, 103, 104))
    a_row, z_row, a_row2, a_group, z_origin_group, a_gone, z_gone = (
        _id(n) for n in (200, 201, 202, 203, 204, 205, 206)
    )
    c.entities = {from_a: "Longsword", from_z: "Chest", from_a2: "Dagger", _id(105): "Own"}
    c.links.entity = {from_a: a_row, from_z: z_row, from_a2: a_row2}
    c.links.stat_group = {merged_group: a_group, z_group: z_origin_group}
    c.links.origin_tenant = {
        a_row: UPSTREAM,
        a_row2: UPSTREAM,
        a_group: UPSTREAM,
        a_gone: UPSTREAM,
        z_row: OTHER,
        z_origin_group: OTHER,
        z_gone: OTHER,
    }
    c.links.merged = {a_group, z_origin_group}
    c.links.deleted["entity"] = {a_gone, z_gone}
    c.links.snapshots = {s: {"name": str(s)} for s in c.links.origin_tenant}
    c.links.copies = {UPSTREAM, OTHER}
    c.links.attachments[UPSTREAM] = {(a_row, z_row)}
    c.links.attachments[OTHER] = {(z_row, z_row)}
    return c


def test_the_copies_of_an_included_source_become_the_contents_own() -> None:
    c = _two_sources()

    flatten(c, {UPSTREAM})

    own = {e for e in c.entities if c.own("entity", e)}
    assert {c.entities[e] for e in own} == {"Longsword", "Dagger", "Own"}
    # What it copied from the other source is still a copy.
    assert {c.entities[e] for e in c.entities if not c.own("entity", e)} == {"Chest"}
    # A merged group of A's is the content's own now: it is carried, not offered for update.
    assert _id(103) not in c.links.stat_group and _id(104) in c.links.stat_group
    # Everything that only a copy link kept of A is gone: what was deleted of it, its snapshots,
    # who its rows came from, the attachments taken from it, and A itself as a repository built on.
    assert c.links.deleted == {"entity": {_id(206)}}
    assert set(c.links.origin_tenant.values()) == {OTHER}
    assert set(c.links.snapshots) == {_id(201), _id(204), _id(206)}
    assert c.links.merged == {_id(204)}
    assert UPSTREAM not in c.links.attachments and OTHER in c.links.attachments
    assert c.links.copies == {OTHER}
    # The rows themselves are untouched: flattening changes who they are said to be copies of.
    assert len(c.entities) == 4


def test_flattening_every_source_leaves_no_link() -> None:
    c = _two_sources()

    flatten(c, {UPSTREAM, OTHER})

    assert c.links.entity == {} and c.links.stat_group == {} and c.links.stat_definition == {}
    assert c.links.origin_tenant == {} and c.links.snapshots == {} and c.links.merged == set()
    assert c.links.deleted == {} and c.links.copies == set() and dict(c.links.attachments) == {}
    assert all(c.own("entity", e) for e in c.entities)


def test_flattening_nothing_changes_nothing() -> None:
    c = full_content()

    flatten(c, set())
    flatten(c, {uuid.uuid4()})

    assert differences(c, full_content()) == []


def test_a_flattened_content_is_a_document_a_library_reads_as_the_same_content() -> None:
    c = full_content()
    flatten(c, {UPSTREAM})
    c.sources = {
        UPSTREAM: {
            "inclusion": "include",
            "name": "Upstream",
            "licence": {"label": "CC BY 4.0", "url": None},
        },
        OTHER: {"inclusion": "show", "name": "Other", "licence": None},
    }

    document, files = rd.encode(c)
    back = rd.decode(rd.loads(rd.dumps(document)), files)

    assert differences(c, back) == []
    assert back.links.copies == {OTHER}
    assert back.sources[UPSTREAM]["licence"] == {"label": "CC BY 4.0", "url": None}
    assert back.sources[OTHER]["licence"] is None


def test_what_a_release_records_of_its_sources_is_by_name_and_says_the_licence() -> None:
    c = Content(tenant_id=_id(1))
    c.sources = {
        _id(3): {"inclusion": "show", "name": "Zeta", "licence": None},
        _id(2): {
            "inclusion": "include",
            "name": "Alpha",
            "licence": {"label": "OGL", "url": "https://example.com/ogl"},
        },
    }

    records = release_sources_of(c)

    assert records == [
        {
            "id": str(_id(2)),
            "name": "Alpha",
            "inclusion": "include",
            "licence_label": "OGL",
            "licence_url": "https://example.com/ogl",
        },
        {
            "id": str(_id(3)),
            "name": "Zeta",
            "inclusion": "show",
            "licence_label": None,
            "licence_url": None,
        },
    ]
    assert [r["name"] for r in included_by(records)] == ["Alpha"]
    assert included_by(None) == []
    profile = RepositoryProfile(release_sources=records)
    assert recorded_inclusions(profile) == {str(_id(2)): "include", str(_id(3)): "show"}
    assert recorded_inclusions(None) == {} == recorded_inclusions(RepositoryProfile())


def _now(**choices: str) -> dict[uuid.UUID, dict[str, object]]:
    return {
        _id(int(n)): {"inclusion": c, "name": f"Source {n}", "licence": None}
        for n, c in choices.items()
    }


def test_a_changed_choice_is_a_change_and_an_unchanged_one_is_not() -> None:
    recorded = [
        {"id": str(_id(1)), "inclusion": "show"},
        {"id": str(_id(2)), "inclusion": "include"},
        {"id": str(_id(3)), "inclusion": "include"},
    ]
    after = {
        _id(1): {"inclusion": "include", "name": "One"},
        _id(2): {"inclusion": "show", "name": "Two"},
        _id(3): {"inclusion": "include", "name": "Three"},
    }

    changes = inclusion_changes(recorded, after)

    assert [(c.name, c.before, c.after) for c in changes] == [
        ("One", "show", "include"),
        ("Two", "include", "show"),
    ]
    assert changes[0].as_json() == {
        "repository_id": str(_id(1)),
        "name": "One",
        "before": "show",
        "after": "include",
    }


def test_nothing_is_a_change_before_a_public_release_or_for_a_repository_built_on_since() -> None:
    after = {_id(1): {"inclusion": "include", "name": "One"}}

    # No public release yet: the choice is free.
    assert inclusion_changes(None, after) == []
    # A public release that did not record this source: it is new, and its rows are added.
    assert inclusion_changes([], after) == []
    assert inclusion_changes([{"id": str(_id(9)), "inclusion": "show"}], after) == []
    # A source that is gone from the content is not a change of choice.
    assert inclusion_changes([{"id": str(_id(1)), "inclusion": "show"}], {}) == []


def test_the_terms_say_what_the_visibility_says_until_an_owner_says_otherwise() -> None:
    assert default_may_be_included("private") is False
    assert default_may_be_included("public") is True
    assert terms_of(None).may_be_included is False
    assert terms_of(RepositoryProfile(visibility="private")).may_be_included is False
    assert terms_of(RepositoryProfile(visibility="public")).may_be_included is True
    # An Owner's value wins either way.
    assert terms_of(RepositoryProfile(visibility="private", may_be_included=True)).may_be_included
    assert not terms_of(
        RepositoryProfile(visibility="public", may_be_included=False)
    ).may_be_included
