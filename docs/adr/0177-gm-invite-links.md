# 0177 - A GM invite link: single use, short-lived

Status: accepted, decided with the maintainer on 2026-10-04, for account-hub's one-click setup ([ADR 0180](0180-account-hub-one-click-setup.md)).

Amends [ADR 0092](0092-campaign-invite-links.md)'s rule that an invite link "grants the **player** role in that one campaign only. Never GM", for one narrow kind of link.

## Context

A campaign's GM can be named in one way today: `PUT .../campaigns/{id}/gms/{user_id}`, which needs the GM's user id, so the person must already have an account and be found by email or nickname. A person setting up a table for a friend who has no account yet, or who is not in front of them, has no way to hand over the GM seat. The maintainer asked for it: a link that makes whoever redeems it a GM, redeemable by someone who already has an account or by someone who does not.

The second half needs nothing new. Redemption already requires a login, and a first authenticated call provisions the user ([ADR 0023](0023-authgear-token-verification.md)); account-hub's `/join/` page already carries a link through signup and back.

## Decision

An invite has a **role**, `player` or `gm`. Every existing link, and any created without saying, is `player`, unchanged.

### A GM link

- **Single use.** `max_uses` is omitted or `1`, and stored as `1`; anything else is a `422`. The atomic spend of [ADR 0092](0092-campaign-invite-links.md) is what makes it one person.
- **Short-lived.** `expires_at` is required and at most **7 days** out, against 30 for a player link (`MAX_GM_INVITE_LIFETIME`). A longer one is a `422`, with the same problem type as any other bad expiry.
- **Minted by whoever may grant GM directly**: `can_manage_campaign`, a GM of the campaign or a tenant `OWNER`/`ORGA`, the gate on `PUT .../gms/{user_id}`. A link is a new way to hand over a privilege the creator already has, never a new privilege.
- **Shown once, only its hash stored, listed without tokens, revocable**: all as for a player link.

### Redeeming it

- The redeemer gets a `CampaignGm` row, **not** a `Player` row, and **no tenant membership** ([ADR 0035](0035-campaign-scoped-gm-visibility.md): a table GM has none). The row's `created_by` is the link's creator, the granter, as on `PUT .../gms`.
- **Idempotent**: someone who already GMs the campaign gets `200`, `already_joined`, and no use is spent. A player of the campaign who redeems it becomes a GM *as well*; the two are independent rows.
- The same dead-link behaviour as ever: unknown, expired, revoked and spent links are indistinguishable.
- It is recorded in the activity log with its role, and the campaign's GMs are notified: "A new GM joined *name*".

### What the responses say

- `InviteOut` and `InviteCreatedOut` gain `role`.
- `InvitePreviewOut` gains `role`, so the landing page can say what is being offered ("join as a GM") before it asks anyone to log in. The role is not a secret: the holder is about to be asked to accept it.
- `InviteRedeemOut` gains `role`, and **`player_id` becomes nullable**, null for a GM redemption, which has no player row. It is the one change here that is not purely additive; account-hub is the only client of the route and does not read `player_id`, and it is regenerated in the same change.

## What a leaked GM link costs

More than a player link: a stranger who redeems an unspent one becomes a GM of that campaign, who reads its GM-only information, manages it, invites players and can grant GM. The containment is the point of every constraint above: **one use**, so a link redeemed by its intended person is dead; **seven days at most**; **instant revoke**; a token that is never stored or shown again; creation limited to people who could grant GM anyway; and a redemption that is logged and tells the other GMs. A link nobody has redeemed is the exposure, and it ends within a week.

[ADR 0171](0171-account-hub-campaign-invite-links.md)'s addendum, the edge rate rule deferred to go-live, is unchanged by this. That rule is about flooding; a 256-bit token cannot be guessed.

## Alternatives considered

- **A multi-use GM link.** Too much power for a link that gets pasted into a chat.
- **A player link, then promote.** Two steps, and the second needs the redeemer's user id found by hand, the very thing the link is meant to avoid.
- **Redeeming creates a tenant membership too.** ADR 0035's point is that a table GM has none, and an `ORGA` membership would hand over far more than the seat.
- **A separate `/gm-invites` route family.** The same storage, hash, lookup, redaction and tests would be written twice for one column.

## Not in scope

- **Tenant-role invite links** (a link into a library with a role), the v1.0 row of that name; a different, higher-privilege thing, as ADR 0092 said.
- **An approval step**, as for player links.

## Consequences

- **One migration** (`campaign_invite.role`, default `player`, existing rows unchanged), the create and redeem routes, the schemas above, tests (the single-use race, the 7-day limit, an existing GM, a player who becomes a GM too, the dead-link indistinguishability for a GM link, the token-redaction test unchanged), and regenerated clients.
- account-hub's invite panel offers "Invite a GM" next to the player link, its `/join/` page says which it is, and `/setup` offers it ([ADR 0180](0180-account-hub-one-click-setup.md)).
- The OpenAPI diff reports `player_id` becoming nullable; the pull request carries the `breaking-change` label if the job calls it one.
