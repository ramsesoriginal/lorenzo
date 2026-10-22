# 0328 - Manuscript bundles and saved revisions

Status: accepted. Implements the persistence portion of [RFC 0047](../rfcs/0047-lorenzo-writing.md)
W1 under [ADR 0327](0327-lorenzo-writing.md).

## Context

Writing needs its own manuscript text alongside descriptions and notes. Authors must recover
saved prose and pictures even after an edit through another Lorenzo client. Repository copies
carry the current manuscript, not the source author's recovery history.

## Decision

`manuscript` is a singleton authored Information type. Its ordered text and picture payloads are
ordinary LorenzoScript and picture payloads, using their existing identities and audience.
Existing entries can designate a text bundle explicitly by changing its type; no implicit
conversion of descriptions or notes occurs. The first writing slice can use existing Scenes as
standalone drafts without inventing a temporary entry kind.

A tenant-scoped `manuscript_revision` records the bundle before its first payload mutation in a
database transaction. Database triggers cover text, pictures and payload ordering, including
writes from other clients and bulk code paths. Snapshot content contains ordered stable payload
identities, text locales and picture bytes; it contains no audience grants. No-op updates do not
create revisions. Revisions remain while their Information exists; deleting the Information or
entry explicitly deletes its history too. The interface must explain that destructive action.
Keep saved revisions without automatic expiry in this slice; no background retention policy is
introduced. History is operational data, excluded from repository copies and releases.

History reads require the current Information editing permission, not merely a past grant or
current read permission. Recovery copies selected saved content into an editor and then uses
conditional ordinary writes; it does not rewind sharing, identity, other notes or world state.
An unavailable or revoked manuscript cannot be recovered through a history endpoint. History
responses are private and no-store. Images in a revision remain subject to that same gate.

## Consequences

The snapshot is once per transaction, before the first mutation, so a multi-step operation has
one recoverable starting point rather than intermediate half-written bundles. Tenant RLS and
same-tenant keys protect history. Saved history can grow with manuscript size; future retention
or deduplicated storage needs a separate decision and must preserve promised recovery.
The existing generic Information and payload APIs remain the write surface.
