# 0060 - User profile expansion

Status: accepted

## Context

`User` (ADR 0054) has an identity (`email`, `nickname`) but nothing that makes a profile feel like a *person* in this app: no friendly display label distinct from the unique lookup handle, no way to say how to address someone, no picture URL handed back on the caller's own profile response, and nothing at all for a shared UI (rosters, notification styling) to key off per-user.

## Decision

`models/user.py` gains six new columns, all nullable/defaulted, all optional:

- `display_name: str | None` - a friendly label, deliberately **not unique**. `nickname` stays the unique lookup handle ADR 0054/0055 already built; conflating "the thing you're found by" with "the thing shown in UI" was the wrong trade-off once both exist. Two users can both be "Alex."
- `pronouns: str | None`, `bio: str | None` - free text, unvalidated, private (see visibility below).
- `locales: list[str]` - a Postgres `ARRAY(Text)`, default `{}`. This codebase's first native array column: a short, homogeneous, order-not-load-bearing list of locale tags doesn't earn a join table the way `GroupMember`/`CharacterPlayer` do for genuine many-to-many domain relationships.
- `user_color: str | None` - validated as `#RRGGBB` at the schema boundary (`Field(pattern=r"^#[0-9A-Fa-f]{6}$")`, matching `_SLUG_PATTERN`'s existing validate-at-the-edge style), for shared UI to color-code a person by (notification styling, roster highlighting) - not enforced as meaningful beyond that shape.

`PATCH /me`'s body schema is broadened from `NicknameUpdate` to a new `ProfileUpdate` covering all six self-editable fields; `NicknameUpdate` is retired rather than kept alongside it.

`MeOut` gains all six fields, plus `picture_url: str` - always a constructed URL (`request.url_for("get_user_picture", ...)`), not conditional on a picture actually existing, the same "hand back the URL, let the resource itself 404/redirect" precedent `PayloadPictureOut.url` already established (ADR 0020).

**Visibility, decided per field, not blanket:**
- `display_name`/`user_color` join `nickname` on the tenant-roster schemas (`MembershipRosterEntryOut`/`PlayerRosterEntryOut`/`GmRosterEntryOut`) - `user_color`'s whole point is other people's clients rendering it, so it has to actually reach them.
- `UserRefOut` (the by-email/by-nickname lookup, ADR 0055) gains `display_name` only - a friendlier label while resolving who you're about to invite, not a rendering context, so no `user_color`.
- `pronouns`/`bio`/`locales` stay private to `MeOut`/`AdminUserOut` - more personal, no stated need for anyone else to see them yet.
- `AdminUserOut` (ADR 0057) gains all six, for a complete admin view.

## Not in scope

- Validating `locales` values against a real BCP-47 list - free-form, same as every other locale-shaped field in this codebase (`PayloadDescription.locale`, ADR 0017).
- Any notion of a "verified" pronoun/bio moderation pass.

## Consequences

- New migration; `models/user.py`; `schemas/users.py` (`ProfileUpdate` replacing `NicknameUpdate`, `MeOut`, `UserRefOut`); `schemas/tenants.py` (three roster schemas); `schemas/admin.py` (`AdminUserOut`); `routers/users.py` (`get_me`/`update_me`/`_me_out` now thread `Request`); `routers/tenants.py` (`list_tenant_roster`'s batch query widened).
