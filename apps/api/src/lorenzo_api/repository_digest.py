"""The digest of a release, the rows it released, and the breaking-change detector -
ADR 0208, RFC 0037 §2 and §3.

A publish hashes every row the update engine compares, with the snapshot functions the
diff itself uses, so a hash cannot disagree with what the engine would call a change. The
hashes are the repository's one set of released rows (`repository_released_row`), replaced
at each publish. A row is *released* while its hash now equals the stored one and *edited
since* otherwise; the same comparison, in the author's hands, says what a publish would
release before it is made, and finds the changes the engine cannot carry to a library that
already copied the repository.
"""

import hashlib
import json
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.entity_kinds import unpublishable_entries
from lorenzo_api.models import (
    Payload,
    PayloadDescription,
    RepositoryRelease,
    RepositoryReleasedRow,
)
from lorenzo_api.repository_content import (
    Content,
    attachments_of,
    entity_snapshot,
    index_entities,
    load_content,
    origin_namer,
    stat_definition_snapshot,
    stat_group_snapshot,
)
from lorenzo_api.repository_releases import ReleaseRef, latest_release, releases_as_refs

# A row's key: its kind, its origin id, and an attachment's parent (None for every other kind).
Key = tuple[str, uuid.UUID, uuid.UUID | None]
State = Literal["released", "edited"]

KINDS = ("stat_group", "stat_definition", "entity", "attachment")
_COUNT_KEY = {
    "entity": "entities",
    "stat_group": "stat_groups",
    "stat_definition": "stat_definitions",
    "attachment": "attachments",
}

# What the detector finds, by reason (RFC 0037 §3, ADR 0208): changes that break a library that
# copied the repository, and the one that only changes what an item is in it.
REASONS = (
    "entity_removed",
    "stat_definition_removed",
    "stat_definition_retyped",
    "stat_group_removed",
    "enum_value_removed",
    "kinds_changed",
    "slug_changed",
    "attachment_added",
)
# A warning is said and never refused: a parent added to an item libraries hold changes the item
# there, but it is a bridge's ordinary work, and every library names it before taking it.
WARNING_REASONS = frozenset({"attachment_added"})


@dataclass(frozen=True)
class Row:
    """One row as released, or as it is now: its hash, its name (an attachment's child's),
    and the few facts the detector reads. `facts` holds an entity's `kinds` and `slug`, a
    stat definition's `value_type` and `enum_values`, an attachment's `parent_name`."""

    kind: str
    row_id: uuid.UUID
    parent_id: uuid.UUID | None
    hash: str
    name: str
    facts: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> Key:
        return (self.kind, self.row_id, self.parent_id)


@dataclass(frozen=True)
class Breaking:
    """A change the detector found, as it is kept on a release: in `breaking_rows` when the
    engine cannot carry it, in `warning_rows` when it only changes what an item is."""

    kind: str
    row_id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    reason: str
    detail: str

    @property
    def key(self) -> Key:
        return (self.kind, self.row_id, self.parent_id)

    def as_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "row_id": str(self.row_id),
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "name": self.name,
            "reason": self.reason,
            "detail": self.detail,
        }

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> Breaking:
        return cls(
            kind=value["kind"],
            row_id=uuid.UUID(value["row_id"]),
            parent_id=uuid.UUID(value["parent_id"]) if value.get("parent_id") else None,
            name=value["name"],
            reason=value["reason"],
            detail=value["detail"],
        )


# --- Hashing -----------------------------------------------------------------------------


def canonical(value: Any) -> str:
    """The canonical JSON of a snapshot: sorted keys, no whitespace."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_of(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def live_rows(content: Content) -> dict[Key, Row]:
    """Every row of a repository's content the update engine compares and a library can
    receive: the repository's own stat groups, stat definitions and entities, and the
    attachments it added to its copies of others'. Hashed from `entity_snapshot`,
    `stat_group_snapshot` and `stat_definition_snapshot` and nothing else, named by origin."""
    namer = origin_namer(content)
    index = index_entities(content)
    rows: dict[Key, Row] = {}
    for group_id, group in content.groups.items():
        if content.own("stat_group", group_id):
            snapshot = stat_group_snapshot(content, group_id)
            rows[("stat_group", group_id, None)] = Row(
                "stat_group", group_id, None, hash_of(snapshot), group["name"]
            )
    for definition_id, definition in content.definitions.items():
        if content.own("stat_definition", definition_id):
            snapshot = stat_definition_snapshot(content, definition_id, namer)
            rows[("stat_definition", definition_id, None)] = Row(
                "stat_definition",
                definition_id,
                None,
                hash_of(snapshot),
                definition["name"],
                {"value_type": snapshot["value_type"], "enum_values": snapshot["enum_values"]},
            )
    for entity_id, name in content.entities.items():
        if content.own("entity", entity_id):
            snapshot = entity_snapshot(content, index, entity_id, namer)
            rows[("entity", entity_id, None)] = Row(
                "entity",
                entity_id,
                None,
                hash_of(snapshot),
                name,
                {"kinds": snapshot["kinds"], "slug": snapshot["slug"]},
            )
    for a in attachments_of(content):
        rows[("attachment", a.child_source_id, a.parent_source_id)] = Row(
            "attachment",
            a.child_source_id,
            a.parent_source_id,
            hash_of([str(a.child_source_id), str(a.parent_source_id)]),
            content.entities[a.child],
            {"parent_name": content.entities[a.parent]},
        )
    return rows


def digest_of(rows: Iterable[Row]) -> str:
    """One hash over a release's rows: each row's key and hash, in a fixed order."""
    lines = sorted(f"{r.kind}:{r.row_id}:{r.parent_id or ''}:{r.hash}" for r in rows)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


# --- The stored rows ---------------------------------------------------------------------


async def stored_rows(session: AsyncSession, repository_id: uuid.UUID) -> dict[Key, Row]:
    """The rows as they were at the repository's last publish."""
    rows: dict[Key, Row] = {}
    for stored in await session.scalars(
        select(RepositoryReleasedRow).where(RepositoryReleasedRow.tenant_id == repository_id)
    ):
        row = Row(
            stored.kind, stored.row_id, stored.parent_id, stored.hash, stored.name, stored.facts
        )
        rows[row.key] = row
    return rows


async def replace_stored_rows(
    session: AsyncSession, repository_id: uuid.UUID, rows: Iterable[Row]
) -> None:
    """The repository's released rows become `rows`: one set, not one for each release."""
    await session.execute(
        delete(RepositoryReleasedRow).where(RepositoryReleasedRow.tenant_id == repository_id)
    )
    values = [
        {
            "tenant_id": repository_id,
            "kind": r.kind,
            "row_id": r.row_id,
            "parent_id": r.parent_id,
            "hash": r.hash,
            "name": r.name,
            "facts": r.facts,
        }
        for r in rows
    ]
    if values:
        await session.execute(insert(RepositoryReleasedRow), values)


def state_of(stored: dict[Key, Row], live: dict[Key, Row], key: Key) -> State:
    """Whether a row is what was released: equal hashes, and absent on both sides counts as
    equal, so a removal that was published is released and one made since is edited."""
    before, now = stored.get(key), live.get(key)
    return (
        "released" if (before.hash if before else None) == (now.hash if now else None) else "edited"
    )


# --- Comparing ---------------------------------------------------------------------------


@dataclass
class Comparison:
    """The live rows against the stored ones: what a publish would add, change and remove.
    `changed` pairs each row as it was released with it as it is."""

    added: list[Row] = field(default_factory=list)
    changed: list[tuple[Row, Row]] = field(default_factory=list)
    removed: list[Row] = field(default_factory=list)

    @property
    def differing(self) -> int:
        return len(self.added) + len(self.changed) + len(self.removed)


def _order(row: Row) -> tuple[int, str, str, str]:
    return (KINDS.index(row.kind), row.name, str(row.row_id), str(row.parent_id))


def compare(stored: dict[Key, Row], live: dict[Key, Row]) -> Comparison:
    found = Comparison()
    for key, row in live.items():
        before = stored.get(key)
        if before is None:
            found.added.append(row)
        elif before.hash != row.hash:
            found.changed.append((before, row))
    found.removed = [row for key, row in stored.items() if key not in live]
    found.added.sort(key=_order)
    found.removed.sort(key=_order)
    found.changed.sort(key=lambda pair: _order(pair[1]))
    return found


def counts_of(found: Comparison, descriptions_edited: int) -> dict[str, Any]:
    """What a release records of what it did, by kind: rows added, changed and removed, the
    attachments added and removed, and the hint of descriptions edited since the release
    before it (RFC 0037 §2)."""
    counts: dict[str, Any] = {
        _COUNT_KEY[kind]: {"added": 0, "changed": 0, "removed": 0}
        for kind in KINDS
        if kind != "attachment"
    }
    counts["attachments"] = {"added": 0, "removed": 0}
    for row in found.added:
        counts[_COUNT_KEY[row.kind]]["added"] += 1
    for _, row in found.changed:
        counts[_COUNT_KEY[row.kind]]["changed"] += 1
    for row in found.removed:
        counts[_COUNT_KEY[row.kind]]["removed"] += 1
    counts["descriptions_edited"] = descriptions_edited
    return counts


# --- The detector (RFC 0037 §3) ----------------------------------------------------------


def _quoted(name: str) -> str:
    return f"“{name}”"


def detect(found: Comparison) -> list[Breaking]:
    """The changes in `found` the update engine cannot carry to a library that already copied
    the repository, or carries so that the library differs from a fresh copy: a removed entry,
    stat or stat group, a stat whose type changed, an enum value taken away, an entry whose
    kind or link name changed, and (as a warning, `WARNING_REASONS`) an attachment added. Added
    rows, changed values, formulas and parents are what updates are for, and are not listed."""
    hits: list[Breaking] = []

    def hit(row: Row, reason: str, detail: str) -> None:
        hits.append(Breaking(row.kind, row.row_id, row.parent_id, row.name, reason, detail))

    for row in found.removed:
        if row.kind == "entity":
            hit(
                row,
                "entity_removed",
                f"{_quoted(row.name)} was removed. Libraries that copied it can only keep "
                "their copy, detached.",
            )
        elif row.kind == "stat_definition":
            hit(
                row,
                "stat_definition_removed",
                f"{_quoted(row.name)} was removed. Libraries that copied it keep it, and "
                "formulas and values there may still use it.",
            )
        elif row.kind == "stat_group":
            hit(
                row,
                "stat_group_removed",
                f"{_quoted(row.name)} was removed. Libraries that copied it keep it.",
            )
    for before, now in found.changed:
        if now.kind == "stat_definition":
            if before.facts.get("value_type") != now.facts.get("value_type"):
                hit(
                    now,
                    "stat_definition_retyped",
                    f"The type of {_quoted(now.name)} changed from {before.facts.get('value_type')}"
                    f" to {now.facts.get('value_type')}. Libraries that copied it keep the old "
                    "type, and new copies get the new one.",
                )
            gone = sorted(
                set(before.facts.get("enum_values", [])) - set(now.facts.get("enum_values", []))
            )
            if gone:
                hit(
                    now,
                    "enum_value_removed",
                    f"{_quoted(now.name)} took away {', '.join(gone)}. Entries in libraries may "
                    "still hold it.",
                )
        elif now.kind == "entity":
            if before.facts.get("kinds") != now.facts.get("kinds"):
                old, new = before.facts.get("kinds") or [], now.facts.get("kinds") or []
                hit(
                    now,
                    "kinds_changed",
                    f"The kind of {_quoted(now.name)} changed from {', '.join(old) or 'none'} to "
                    f"{', '.join(new) or 'none'}. Libraries that copied it keep the old kind, and "
                    "new copies get the new one.",
                )
            old_slug = before.facts.get("slug")
            if old_slug is not None and old_slug != now.facts.get("slug"):
                hit(
                    now,
                    "slug_changed",
                    f"The link name of {_quoted(now.name)} changed from {old_slug} to "
                    f"{now.facts.get('slug') or 'none'}. Links to it in text libraries already "
                    "copied still use the old one.",
                )
    for row in found.added:
        if row.kind == "attachment":
            parent = row.facts.get("parent_name", "")
            hit(
                row,
                "attachment_added",
                f"{_quoted(parent)} was added as a parent of {_quoted(row.name)}. It changes what "
                f"{_quoted(row.name)} is in every library that holds it.",
            )
    return hits


def split(found: Iterable[Breaking]) -> tuple[list[Breaking], list[Breaking]]:
    """What breaks, and what only warns, each in order."""
    sorted_ = ordered(found)
    return (
        [b for b in sorted_ if b.reason not in WARNING_REASONS],
        [b for b in sorted_ if b.reason in WARNING_REASONS],
    )


def ordered(hits: Iterable[Breaking]) -> list[Breaking]:
    return sorted(hits, key=lambda b: (KINDS.index(b.kind), b.name, b.reason, str(b.row_id)))


# --- Description edits (RFC 0037 §2) -----------------------------------------------------


async def descriptions_edited_since(
    session: AsyncSession, repository_id: uuid.UUID, since: datetime | None
) -> int:
    """How many description texts were written or edited after `since`: a hint, as
    the digest does not see text. A description deleted outright leaves no trace."""
    if since is None:
        return 0
    return int(
        await session.scalar(
            select(func.count())
            .select_from(Payload)
            .join(
                PayloadDescription,
                (PayloadDescription.payload_id == Payload.id)
                & (PayloadDescription.tenant_id == Payload.tenant_id),
            )
            .where(Payload.tenant_id == repository_id, Payload.updated_at > since)
        )
        or 0
    )


# --- What a library reads ----------------------------------------------------------------


@dataclass(frozen=True)
class BreakingNote:
    """Why a row was called breaking, and by which release."""

    reason: str
    detail: str
    release: ReleaseRef


async def notes_since(
    session: AsyncSession, repository_id: uuid.UUID, synced_release_id: uuid.UUID | None
) -> tuple[dict[Key, list[BreakingNote]], dict[Key, list[BreakingNote]]]:
    """The rows any release after the one a library last took listed as breaking, and as a
    warning: the union of what the library skipped, oldest release first. A library with no
    release on record (a copy from before releases) is owed all of them. Read inside the gated
    read of the repository."""
    stmt = select(RepositoryRelease).where(
        RepositoryRelease.tenant_id == repository_id,
        (func.jsonb_array_length(RepositoryRelease.breaking_rows) > 0)
        | (func.jsonb_array_length(RepositoryRelease.warning_rows) > 0),
    )
    if synced_release_id is not None:
        synced = await session.scalar(
            select(RepositoryRelease.number).where(
                RepositoryRelease.tenant_id == repository_id,
                RepositoryRelease.id == synced_release_id,
            )
        )
        if synced is not None:
            stmt = stmt.where(RepositoryRelease.number > synced)
    breaking: dict[Key, list[BreakingNote]] = {}
    warnings: dict[Key, list[BreakingNote]] = {}
    releases = (await session.scalars(stmt.order_by(RepositoryRelease.number))).all()
    for ref, release in zip(releases_as_refs(releases), releases, strict=True):
        for into, found in ((breaking, release.breaking_rows), (warnings, release.warning_rows)):
            for value in found:
                row = Breaking.from_json(value)
                into.setdefault(row.key, []).append(BreakingNote(row.reason, row.detail, ref))
    return breaking, warnings


# --- Assessing a repository --------------------------------------------------------------


@dataclass
class Assessment:
    """A repository's live content against what its latest release saw: everything a publish
    records of itself, and everything the author's preview says before it is made."""

    release: ReleaseRef | None
    baseline: bool
    live: dict[Key, Row]
    digest: str
    matches: bool | None
    comparison: Comparison
    hits: list[Breaking]
    warnings: list[Breaking]
    descriptions_edited: int | None
    counts: dict[str, Any]
    # The entries whose combination of kinds no round-trip matrix covers (ADR 0217): a publish is
    # refused while there are any.
    unproven_kinds: list[dict[str, Any]]


async def assess(session: AsyncSession, repository_id: uuid.UUID) -> Assessment:
    """Loads the repository once and compares it with the rows of its latest release, if that
    release has a digest: without one (no release yet, or one made before digests) everything
    counts as added, nothing is breaking and nothing matches. Reads only the repository's own
    rows, as one of its members."""
    content = await load_content(session, repository_id)
    live = live_rows(content)
    release = await latest_release(session, repository_id)
    baseline = release is not None and release.digest is not None
    stored = await stored_rows(session, repository_id) if baseline else {}
    comparison = compare(stored, live)
    hits, warnings = split(detect(comparison)) if baseline else ([], [])
    digest = digest_of(live.values())
    edited = (
        await descriptions_edited_since(session, repository_id, release.created_at)
        if release
        else None
    )
    return Assessment(
        release=release,
        baseline=baseline,
        live=live,
        digest=digest,
        matches=(release is not None and release.digest == digest) if baseline else None,
        comparison=comparison,
        hits=hits,
        warnings=warnings,
        descriptions_edited=edited,
        counts=counts_of(comparison, edited or 0),
        unproven_kinds=unpublishable_entries(
            (row.row_id, row.name, row.facts.get("kinds") or [])
            for row in live.values()
            if row.kind == "entity"
        ),
    )
