# 0197 - Names in update diffs

Status: accepted, decided with the maintainer on 2026-10-07. Slice A1 of [RFC 0036](../rfcs/0036-repository-tooling.md), tracked in #507. Extends [ADR 0121](0121-repository-updates-and-re-sync.md) and [ADR 0172](0172-attachments-a-parent-a-bridge-adds-to-a-copy-travels-with-it.md); additive, nothing existing changes meaning.

## Context

`GET /tenants/{tenant_id}/repositories/{repository_id}/updates` compares three versions of every copied row (ADR 0121), and a field's `base`, `upstream`, `local`, `added` and `removed` are written in origin ids, so that the three can be compared at all. An id appears in:

- the name of a keyed field, `stats:<id>` and `formulas:<id>`, where `label` names the stat, but only for a stat the repository still has: a stat dropped upstream has `label: null`;
- the values of a set, `prototypes` (entries) and `stat_groups`;
- the `stat_group` of a stat definition;
- a formula's inputs (`source`, `left`, `right`, a sum's `terms[].source`);
- a value that belongs to the library alone, a prototype or stat the repository never had: written `local:<id>`, since no origin exists.

A client has to look each one up, from the library's own copies and the repository's browse reads, and a row that was deleted upstream or deleted in the library can't be looked up there at all, so "Was / Now / Yours" ([RFC 0036](../rfcs/0036-repository-tooling.md) §4) would show an id exactly where a person most needs a word. `RowRefOut` and `AttachmentRefOut` already carry names; the field values do not.

The `not_applied` entries of `POST .../updates` have the same problem. `field` is `stats:<id>` for a stat's value, and one reason reads "`<id>` wasn't copied here", an id in a sentence a person is meant to read ([ADR 0194](0194-user-facing-terminology.md): API messages are product copy).

## Decision

### A side map of names on the updates response

`UpdatesOut` gains `names`, an object from id to name, for **every id the changed fields mention**, as the key is written in the values: an origin id, or `local:<id>` for one of the library's own rows. Values stay as they are, so a client that doesn't read `names` works as before; one that does needs one lookup per id, in one place, and nothing is repeated beside every value.

A name beside each value was rejected: values are untyped (a number, a string, a list, a formula object), and wrapping them would break every existing client; a parallel field per value would repeat a name once per mention, and a formula's inputs sit inside an object.

An id is named, in this order, by:

1. the repository's row as it is now;
2. the library's own row for it: its copy, or its own row the repository copied from it, or, for `local:<id>`, that row;
3. the snapshot kept in the library's copy link, taken when the row was copied or last updated, which still has the name of a row the repository dropped and, since the link outlives the row, of one the library deleted.

The first name found wins, so a renamed row shows what it is called upstream now. An id the library's links no longer know (the link was detached, and the library's row, if any, is no longer tied to it) has no name anywhere. It is **left out of `names`**, never mapped to itself or to a placeholder: the API doesn't invent words. A client says what it knows, "an entry that is gone" or "a stat that is gone", and never shows the id as if it were a name. Where a field about a stat has no name, `label` is `null` as before.

`label` itself is filled from the same map, so a stat dropped upstream now has its label too.

### `not_applied`

Its entries gain `name`, the row the entry is about, and `label`, what its `field` names: the stat of a `stats:<id>`/`formulas:<id>` field, and for an attachment (kind `attachment`) the parent, `name` being the child. Both are `null` where there is no name. The one reason that quoted an id, "`<id>` wasn't copied here", now says the entry's name, or "what it points at" where it has none. Other reasons already name things by words and are unchanged, as is the rest of the apply response.

### Not changed

- No route, parameter, request body or status code. Nothing is added to the database.
- Existing fields keep their values. `names`, `name` and `label` are new response properties, which the committed OpenAPI snapshot and the generated clients ([ADR 0122](0122-api-client-package.md), [ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md)) take; no accepted break is needed.
- Who may read: the same members, through the same gated read of the repository. Names come from the repository's content that read already returns, the library's own rows and the library's own copy links, so no other library's row can appear.

## Not in scope

- Names beside the apply request's ids, or in the activity log.
- A change to what is compared or when a field counts as changed (ADR 0121).
- Reading names in the command line, which still prints an id for an attachment it couldn't apply; it can use `name` once someone scopes it.

## Consequences

- Shelf's update diff ([RFC 0036](../rfcs/0036-repository-tooling.md) S4) stops resolving names in the browser: it reads `names`, and needs the browse reads of the repository only for what it shows beyond the diff. A row about something deleted upstream or deleted in the library reads correctly, which the browser could not do.
- The response grows by one entry per distinct id a diff mentions. Resolving them reads nothing the update computation hadn't already loaded.
- A client must treat a missing key as "no name", and show a word of its own, not the key.
