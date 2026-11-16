# 0465 - An award by the holder's controller

Status: accepted, built (2026-11-16). Slice G1 of the follow-ups tracked in #1229. Takes up what
[RFC 0054](../rfcs/0054-features-grants-and-choices.md) section 2 says of an award ("the GM's, or the holder's controller where the
library allows") and [ADR 0454](0454-features-two-kinds-and-what-a-holder-has.md) left out ("a setting nobody has asked for").

## Context

An award is a feature a holder has with no rule behind it: a boon, a gift, a feat picked at the table. It is the holder's manager's
alone, so a player whose character is given something at the table waits for a GM to put it on the sheet. Some tables want the player
to do it; most do not, and a feature the GM did not mean to give is a surprise.

## Decision

- **A library setting, `controllers_award_features`**, a boolean of the tenant, **off by default**: no library's behaviour changes until
  an administrator turns it on. It is set as the other settings of a library are, `PATCH /tenants/{id}` (an administrator's), and read
  on `GET /tenants/{id}`; `PATCH` leaves it alone when the body does not carry it.
- **With it on, `POST /entities/{holder}/features` also takes the holder's controller**: anyone whose characters or groups reach the
  holder, the rule for editing what one holds (ADR 0124, as the switch of an instance has it). The holder's manager awards as before,
  on or off. Everything else an award does is unchanged: the same `409` for a feature that is not repeatable and is held, the same
  `422` for an entry that is no feature or a holder that holds nothing, the same instance, and the activity-log event names the caller.
- **Only the award.** Removing a feature stays a manager's (a controller may swap the pick of a changeable rule, ADR 0456), and
  applying grants was already the controller's. Awarding a feature to a holder one does not control is a `403` whatever the setting.
- **The answer.** `controllers_award_features` is in the tenant's answer, `false` until it is turned on: a response field
  that grew, which the typed clients that list a tenant's fields need in their fixtures (the account hub's has it).

## Design

`require_awarder` in `features.py` is `manages_holder`, then the tenant's column and `can_self_manage_entity`; the award route calls it
where it called `require_manager`. The column is `tenant.controllers_award_features boolean not null default false`. The schema field is a plain boolean.

## Validation and delivery

Tests: the setting off, set, kept by another change and cleared; a player refused with it off, awarding their own character with it
on (repeatable and not, a non-feature, a held feature that is not repeatable), refused for another being and for removing, refused again
with it off; an administrator awarding either way. The OpenAPI change is one optional request field and one optional response field,
neither breaking; the CLI models and `packages/api-client` are regenerated.

## Not in scope

Awarding by a controller of a group's members one by one, a per-feature setting (a library asks for all or none), a request a controller
makes and a manager approves.

## Consequences

- A table that wants players to take their own boons says so once; a table that does not changes nothing.
- RFC 0054's one setting that nobody had asked for is a column, and the award route has one rule for who may.
