# 0456 - The grants read, apply with picks, and revocation

Status: accepted, built (2026-11-12). Slice F3 of [RFC 0054](../rfcs/0054-features-grants-and-choices.md). Builds on
[ADR 0454](0454-features-two-kinds-and-what-a-holder-has.md) (features and what a holder has),
[ADR 0455](0455-grant-rules-and-the-prerequisites-of-a-feature.md) (rules and prerequisites),
[ADR 0447](0447-contents-options-and-the-active-switch.md) (`active`), [ADR 0099](0099-player-facing-change-feed.md) (the change feed)
and [ADR 0285](0285-api-reads-that-cost-what-they-read.md) (what a request may cost). Resolution does not change.

## Context

Rules and prerequisites say what a holder may have; nothing yet makes it so. A level-up is a client changing the holder's stats and then
asking for what is now due, and what a source or a stat stops justifying has to go, in the request that stops it, not at some later time.

## Decision

- **A grant record says how a holder came to have a feature.** `grant_record` has the holder, the rule and the source the grant was
  made from (an ancestor entry of the holder, or an instance it holds; both empty for an award), the feature and, while it is `active`,
  its instance. A `revoked` record keeps its feature and loses its instance, which is deleted, with a reason: `source` (the source is
  gone, inactive or moved out), `conditions` (they no longer hold) or `removed` (taken by hand). An award now has a record too, with no
  rule; earlier awards have none and read as awards. A (holder, rule, source, feature) has one active record, so a second apply grants
  nothing new, and an instance has one record. A deleted rule leaves its records (read as awards); a deleted source entry leaves its
  record with no source, and a record that lasts while its source does and has none is revoked at the next check.
- **The read** `GET /entities/{holder}/grants` computes and writes nothing: `held` (what rules and awards gave, with the source and its
  kind), `due` (automatic grants whose conditions hold and that have no record), `open_choices` (a choose rule that holds and has room:
  its minimum, maximum, what is picked, and the options that pass their prerequisites, a hidden entry as `a hidden entry`) and `orphaned`
  (active records whose source or conditions no longer hold). `GET /entities/{holder}/features` says `granted_by` for each instance.
  Readable as the holder's features are.
- **Sources.** A holder's sources are the entries on its prototype walk, with the rules of the whole walk (a Champion archetype brings its
  parent Fighter's), and the active instances it holds directly, feature instances and item instances (the two with an `active` switch),
  each of whose own walk brings its rules with the instance as the reference, so an item held twice or a feature taken twice counts
  twice. A rule on the holder's own entry is not one of its sources. A group's sources are its entry's walk and what it holds.
- **A condition reads numbers** as a `comparison` formula does (ADR 0444): the effective value with formulas evaluated, a bool as 1 or 0
  and an enum as its `sort_order`; a stat with no number makes the comparison false. A count stat is read the same way and rounded down
  (none or a negative one is 0).
- **Apply** `POST /entities/{holder}/grants/apply` `{picks, dry_run, override}`: in one transaction it revokes what is orphaned, makes the
  automatic grants that are due, records the picks, and repeats until nothing changes, because a granted feature is itself a source; a
  depth of eight stops a cycle of rules and says `truncated`. A pick `{rule_id, source_id, options}` is refused (422) outside the rule's
  options, for a rule and source with no open choice by the end, for a feature already picked for it, below the minimum where the apply
  carries picks for it, above the maximum, and past a prerequisite; and refused (409) for a feature the holder has that is not
  `repeatable`. A GM's `override` lifts the minimum, the maximum and the prerequisite, never the last. A feature removed by hand is not
  made again by a later apply. `dry_run` reports what would be created and revoked and writes nothing.
- **Who may.** The holder's controller applies (whoever reaches it, ADR 0124), and any GM of it (403 otherwise); `override` is a GM's alone
  (403). A pick of a rule that is `changeable` can be swapped by the holder (removing it, then picking again); any other grant is removed
  by the holder's GM only.
- **Revocation happens in the request that causes it.** A holder with active records that last while their source does is checked (one
  statement for all of them; a holder with none costs just that) by: a change of the holder's parents (and of an instance's, for what it
  gives its holder), a flip of `active` on a feature instance or an item instance, an item instance moved out of its holder or set
  down, the deletion of a source (an entry, an item instance, the items a deleted being held), and a stat written or cleared on the
  holder or the source that a condition of one of those records reads (the check first looks up whether any does). Records whose source
  or conditions no longer hold are revoked; what an instance gave goes before it, down a chain (an item that gives a feature that
  gives a choice takes all three). Granting is never done there: a feature that becomes due waits for the next apply. A `permanent`
  grant is checked for its conditions only when it is made and stays when its source goes. Each revocation is an activity entry and a
  change-feed row for whoever held it; a revocation in a request made by someone the session cannot name is logged with no actor.
  A stat inherited from a prototype that is written changes what its holders read, and is not followed.
- **A repository carries the records.** Release documents move to **format 45** (`grant_records`, the active ones; version 44 is read
  with none). A copy writes a record for each instance it makes, with the library's own copy of the rule and the source, for an
  instance the repository owns; a record whose rule or source was not copied is left out and the instance reads as awarded. Copied once
  and never changed by an update, as an instance is.

## Design

`grant_record` (`holder_id`, `rule_id`, `source_ref_id`, `feature_id`, `feature_instance_id`, `state`, `revoked_reason`, `created_at`,
`created_by`), every key composite with `tenant_id`, the two policies of a content table and `FORCE ROW LEVEL SECURITY`; the keys
cascade for the holder, the feature and the instance and set the rule and the source to null; checks say an active record has its
instance and a revoked one has a reason; partial unique indexes hold one active record for a (holder, rule, source, feature) and one for
an instance. `grants.py` holds the reading (`compute`: sources and standings, numbers, options, due, open, orphaned), the writing
(`grant`, `revoke`, `apply_grants`) and the checks the requests call (`revoke_orphans`, `revoke_by_sources`,
`revoke_after_stat_write`); `routers/grants.py` has the two routes.

## Validation and delivery

A test for each: what is due read without writing and granted once; a condition that does not hold and then does; a condition on the
source; a choice with its minimum, maximum, picks and refusals; a count from a stat; a prerequisite leaving an option out and a GM's
override; a feature already held; a chain of grants granted in one apply and revoked together; a cycle ending; a dry run; a change of
parents, a stat write, an item switched off, moved and deleted, and a source entry deleted, each revoking in its request; a stat write
costing one statement more when no condition reads the stat; a grant removed by hand not made again; a player applying, swapping a
changeable pick, and refused an override and another's holder; the document round trip and the version 44 reader; and a copy bringing a
record. The OpenAPI change is the two routes, `granted_by` and the new schemas; the CLI models and `packages/api-client` are
regenerated.

## Not in scope

The `features` template slot (F4); revoking when a prototype's stat is written; a record's history beyond the last revocation; an apply
that runs on a stat write; an undo of an apply beyond removal and revocation.

## Consequences

- A character complete after one apply, a level-up that is a stat write and an apply, and a magic item that gives features while it is
  worn.
- A request that changes a holder's parents, an item's place or switch, or a stat a rule reads, may delete features; one that touches no
  holder with such records pays one statement.
- Choices are enforced: a library that needs a looser rule has the GM override or leaves the rule out.
