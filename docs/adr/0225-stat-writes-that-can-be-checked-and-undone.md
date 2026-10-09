# 0225 - Stat writes that can be checked and undone

Status: accepted, decided with the maintainer on 2026-10-09. Slice W1 of [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) (section 6). Builds on [ADR 0037](0037-effective-stat-resolution.md) (stat values and the stat PUT), [ADR 0103](0103-stat-tags-enum-values-and-mandatory-groups.md) (the tag routes), [ADR 0216](0216-parents-for-any-entry.md) (a write that touches the entry) and [ADR 0042](0042-concurrency-token-on-reads.md) (`ETag` and `If-Match`).

## Context

Bench writes a change as a command and compares it with the server before sending (RFC 0039 section 5). For a stat there was nothing to compare with: a stat write moved only the stat row's own version, so an entry's `ETag` did not change when one of its stats did, and the response did not say what the write replaced. Two things followed: an edit made against an entry's old version was accepted over a changed stat, and a stat edit could not be undone exactly, since the value it overwrote was not known to the caller. And an own value could not be removed again, so "revert to inherited" and the undo of a first write were not writable (a bool had `DELETE .../tags/{id}`, nothing else did).

## Decision

- **A stat write moves the entry's version.** `PUT .../stats/{id}` and the tag routes (`PUT`, `PATCH` and `DELETE .../tags/{id}`) set the entry's `updated_by` and `updated_at`, as every other write to an entry does (ADR 0216), so its `ETag` moves. **Only a real change moves it**: the same value again, or clearing what is not there, writes nothing and changes nothing, as the same parents again do not. A write that only adds the stat's group to the entry (`acquire_group`) is a change.
- **The new version comes back as the `ETag` header** of each of these responses, so a caller can chain a second write without a second read.
- **`previous`: what the write replaced.** These routes return the entry exactly as before, with one field added, `previous: { had_own_value, value }`. `had_own_value` false means the entry had no value of its own and inherited, so `value` is null and the undo is clearing it; true means `value` is what to put back. The schema is `EntityStatWriteOut`, which extends `EntityDetailOut`: nothing a caller of these routes read before is gone, and `GET /entities/{id}` is unchanged.
- **`DELETE /tenants/{t}/entities/{id}/stats/{stat_definition_id}`** removes the entry's own direct value for a stat that is not a bool, so it inherits again. It returns the entry and `previous` like the others, takes `If-Match` against the stat's own version as the tag `DELETE` does, and is idempotent: nothing to remove is `200` with `had_own_value` false and moves nothing. Its group is left alone, as the tag route leaves it.
  - A **bool** is `422`, and the message names the tag route.
  - A **formula** is not a direct value: the entry holding one for the stat is `409`, whose message points at `DELETE .../computed-stats/{id}`. The two stay separate ([ADR 0104](0104-computed-stats.md): one or the other).
- **Authorization and the order of checks are the stat PUT's**: the entry and the stat definition (404), who may write the entry's stats (403), the stat's type (422), `If-Match` (412).

### The audit RFC 0039 asked for

Which other writes to an entry leave its version where it was, found by reading the routes (nothing here changes any of them):

- **The entry's link name** (`PUT` and `DELETE .../entities/{id}/slug`): no version.
- **A formula** (`PUT` and `DELETE .../computed-stats/{id}`): moves the formula row's own version, not the entry's.
- **A description or a note** (information routes): their own version, on the payload, by design ([ADR 0224](0224-bench-description-and-notes.md)).
- Attaching a stat group is only done by the stat writes above and is covered.

The first two are left as they are: Bench writes neither yet. Each is a one-line change in its route when Bench does (the formula editor, B7), and is then a small ADR of its own, not a change to this one.

## Consequences

- An edit made against an entry's old version is refused with `412` after a stat write, which is what makes the compare in RFC 0039 section 5 possible for stats.
- Bench can undo a stat write exactly: put `previous.value` back, or `DELETE` the value if there was none.
- A caller that never sent `If-Match` to an entry is unaffected. One that did, and edited stats in between, now sees a `412` it did not see before; that is the point.
- The generated clients carry `previous` and the new route.
