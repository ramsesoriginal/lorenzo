# 0173 - A GM lists the beings they can see

Status: accepted, decided with the maintainer on 2026-10-04, after account-hub's `/beings` page turned out to fail outright for a GM with no library membership ([issue #418](https://github.com/ramsesoriginal/lorenzo/issues/418)).

Amends [ADR 0078](0078-being-listing-and-search-endpoint.md)'s gate on `GET /tenants/{id}/beings`, and builds on the reach [ADR 0152](0152-a-gm-sees-every-being-in-no-campaign.md) completed.

## Context

[ADR 0078](0078-being-listing-and-search-endpoint.md) gave the "pick a being" list a membership gate (`get_tenant_context`), and said why: it is a superset of `GET .../characters`, since it also reveals bare-being stubs that never appear there, so it "stays at least as strict, not looser".

Since then the GM side has grown. A GM's reach ([ADR 0035](0035-campaign-scoped-gm-visibility.md), [0046](0046-gm-reachability-widens-to-surroundings.md), [0124](0124-groups-own-things-and-moving-is-not-giving.md)) covers the characters of the campaigns they GM, the scenes those characters stand in, and what is in them. [ADR 0151](0151-a-being-in-no-campaign-and-who-stands-in-for-its-gm.md) and [0152](0152-a-gm-sees-every-being-in-no-campaign.md) added the beings in no campaign: a GM may give an NPC a pack, read its GM-only information, and open its board, with a tenant setting (`npcs_shared_with_gms`) deciding whether that is every such being or only those they and their co-GMs authored.

A **membership** is administrative, and only that: `MembershipRole` is `OWNER` or `ORGA` ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md)). An ordinary table GM has none ([ADR 0035](0035-campaign-scoped-gm-visibility.md)). So the list that is meant to let them pick a being answers such a GM with a `404`, and nothing built on it works for them:

- they may act on an NPC they have no way to look up;
- account-hub's `/beings` shows "No tenant with id …" for the whole page, before its hand-off panel can open (found while fixing the panel, [PR #424](https://github.com/ramsesoriginal/lorenzo/pull/424); the GM sees the error whatever the other libraries they administer hold).

ADR 0152 settled who may read and act on a being in no campaign. It said nothing about the listing, which stayed on the old tier.

## Decision

`GET /tenants/{tenant_id}/beings` has three outcomes, by who asks:

| Caller | Answer |
| --- | --- |
| **A tenant administrator** (a `Membership`, `OWNER` or `ORGA`) | **Every being**, exactly as today. |
| **A GM**: holds a `CampaignGm` row in the tenant, and no membership | **The beings in their reach**: those whose entity is in `gm_reachable_entity_ids` ([ADR 0035](0035-campaign-scoped-gm-visibility.md)). |
| **Anyone else**: a player, a participant with no GM role | `404`, the tenant-not-found problem, as today. |

A GM who is also an administrator is an administrator: they list everything. The listing never read an administrator's per-campaign opt-out ([ADR 0026](0026-campaign-gm-orga-and-access-rule.md)), and still doesn't.

### What a GM's reach holds

One existing set, not a new rule, so the list is exactly the beings whose GM-only information the GM could already read:

- the characters on the roster of any campaign they GM ([ADR 0035](0035-campaign-scoped-gm-visibility.md));
- every entity that contains one of those characters, and everything in it: the NPC standing in the same room ([ADR 0046](0046-gm-reachability-widens-to-surroundings.md));
- the groups those characters belong to, and what they own ([ADR 0124](0124-groups-own-things-and-moving-is-not-giving.md));
- the beings in no campaign they have standing over ([ADR 0152](0152-a-gm-sees-every-being-in-no-campaign.md)): every one with the setting on, else the ones they or a co-GM authored.

The set is filtered to beings. **A player character of a campaign they do not GM is not in it**, and neither is an NPC the setting hides from them. That is the point of reach over "every being": it keeps a table's characters private within a tenant, which is what a `secret` campaign and the opt-out exist for, and what ADR 0152 declined to give up.

### Shape

Unchanged: `BeingSummaryOut` (`entity_id`, `name`, `is_pc`), `?q=` over `Entity.name`, the same paging. A name is not secret in this schema beyond reach already ([ADR 0078](0078-being-listing-and-search-endpoint.md)'s own argument), and everything listed is something the GM can already read about.

## Alternatives considered

- **Every being, for any GM.** Simple, and fail-open: a GM who plays elsewhere would read the names of the characters at tables they are not at, and a `secret` campaign would stop being private. The reasoning that led to ADR 0152's setting applies unchanged.
- **List only for administrators, and have the client say so** (the stopgap considered in #418). Honest, and it leaves the GM unable to pick the NPC they may give to. It stays available to a client that wants it.
- **Any tenant participant**, players included. A different audience with a different question (what a player may know about, [ADR 0028](0028-knowledge-and-group-membership.md)); not decided here.
- **Link a being to a campaign**, so that "its campaign's GMs" is a plain rule. The clean long-term model ([ADR 0046](0046-gm-reachability-widens-to-surroundings.md), [0152](0152-a-gm-sees-every-being-in-no-campaign.md)); this does not preclude it, since a linked being leaves the campaign-less set on its own.

## Not in scope

- **Players listing beings.** inventory-web's give search for a player has the same gap and is a separate decision.
- **`GET .../characters`.** It keeps its membership gate, so a GM with no membership now finds a character at `/beings` but not at `/characters`. Whether it should follow is a separate question.
- **Anything in account-hub.** Its hand-off panel already falls back to user ids when the roster is unreadable ([PR #424](https://github.com/ramsesoriginal/lorenzo/pull/424)), so it needs no change once this answers; a real-browser spec proves that.

## Consequences

- **No migration, no schema change.** The response model is the same; the route's description changes, so the generated clients are regenerated.
- **ADR 0078's "at least as strict" is amended, not dropped:** the list is exactly as open as reach, no more, and an ordinary participant is told what they were told before.
- **A GM pays what any GM read pays.** The reach is rebuilt on each call by a GM, with `Being.entity_id` in a SQL `IN`: fine at a campaign's expected size, and the same cost ADR 0152 named for `visible_information_clause`. An administrator pays nothing new.
- **Built in one slice:** the route's gate and filter in `routers/beings.py`, tests for each caller and for the setting on and off, regenerated clients, and a real-browser check of account-hub's `/beings` for a GM with no membership.

## Erratum (2026-10-04): `GET .../characters` already admits a GM

The "Not in scope" note above says `GET .../characters` "keeps its membership gate", so that a GM with no membership "finds a character at `/beings` but not at `/characters`". That is mistaken. The route is gated by `require_tenant_participant` (a membership, a `Player` row or a `CampaignGm` row), which admits a GM who holds only a campaign grant. What such a GM cannot read is the players' names; [ADR 0176](0176-a-campaigns-people-come-with-their-names.md) adds them to the campaign-level lists.
