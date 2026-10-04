# 0176 - A campaign's players and GMs come with their names

Status: accepted, decided with the maintainer on 2026-10-04, for account-hub's campaigns page ([ADR 0179](0179-account-hub-one-campaigns-page.md)) and for the GM invite links of [ADR 0177](0177-gm-invite-links.md). It also corrects a remark of [ADR 0173](0173-a-gm-lists-the-beings-they-can-see.md).

## Context

The maintainer asked for one page on which a GM sees their campaigns' players and characters, and asked for "the API fixed" so that they can. Looking at what a GM can read today, the characters are not the gap.

- `GET /tenants/{id}/characters` is gated by `require_tenant_participant`: a `Membership`, a `Player` row or a `CampaignGm` row anywhere in the tenant. A GM with only a grant passes. **ADR 0173's remark that it "keeps its membership gate" was mistaken**: it described the gate ADR 0078 gave the beings list, not this route's.
- `GET .../campaigns/{id}/players` returns each player with the characters they play, behind `can_access_campaign`, which a GM passes.
- `GET /me/managed` ([ADR 0086](0086-managed-scope-aggregate-and-notifications-since-filter.md)) lists every campaign the caller runs, across tenants, with no membership needed.

What a GM **cannot** read is *who the players are*. A player row carries a user id and nothing else. The names (`nickname`, `display_name`, `user_color`) come from the tenant roster, `GET /tenants/{id}/memberships`, which needs a tenant-wide membership; an ordinary table GM has none ([ADR 0035](0035-campaign-scoped-gm-visibility.md)). The same is true of a campaign's GM list (`GmOut` is a user id), so a tenant owner looking at a campaign's GMs sees ids for every GM who is not also a member. It gets worse as soon as GMs can join by link ([ADR 0177](0177-gm-invite-links.md)): such a GM never has a membership.

## Decision

The campaign-level people lists carry the names themselves.

- **`PlayerSummaryOut`** (the list, the detail and the create response) and **`GmOut`** gain `nickname`, `display_name` and `user_color`, all nullable, with the values and the meaning they already have on the roster ([ADR 0060](0060-user-profile-expansion.md)). Never the email.
- **The gate is unchanged**: `get_campaign_context`, so a player, a GM, or a tenant administrator who has not opted out of the campaign. Someone with no standing in the campaign still gets the same `404`.
- **The roster route is unchanged.**

### Why this discloses nothing new

Every member of a tenant already reads the name of every player in it from the roster. The people newly told are the ones who sit at that table: players and GMs of the campaign, who know each other. A `secret` campaign stays secret: its roster was already listed to the same audience, by user id.

## Alternatives considered

- **Open `GET /tenants/{id}/memberships` to GMs**, filtered to their campaigns. It is a tenant administrator's tool with two kinds of entry, and the filter would be a new rule on a route that mixes them. The names are needed *at the campaign*; a campaign route should carry them.
- **A new campaign roster route.** A third place for facts two routes already list.
- **Look names up by user id.** There is no such read, and it would be one request per person.

## Not in scope

- `GET .../characters`, its gate and its contents are unchanged. It already answers a GM with only a grant.
- The tenant roster keeps its membership gate.

## Consequences

- **Additive fields**, no migration. The two schemas' routes eager-load the user (`lazy="raise_on_sql"`, [ADR 0018](0018-sqlalchemy-modeling-conventions.md)) to avoid one query per row; tests cover a grant-only GM, a player, and a caller with no standing.
- Generated clients are regenerated. account-hub's roster panels name grant-only players and GMs, falling back to the roster for entries an older API does not name.
- **ADR 0173 gets an erratum** pointing here.
