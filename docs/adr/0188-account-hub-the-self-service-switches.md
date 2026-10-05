# 0188 - account-hub: a GM's self-service switches

Status: accepted, decided with the maintainer on 2026-10-05.

The last client slice of [RFC 0034](../rfcs/0034-player-self-service.md): the screens for the two switches [ADR 0185](0185-player-self-service-the-switches.md) added and [ADR 0186](0186-player-self-service-enforcement.md) made real, so a GM no longer needs the API to turn making your own items off.

## Decision

The smallest edit that puts each switch where its neighbours already are, and nothing new around them.

- **The campaign's setting** is a checkbox, "Players can make their own items", in the campaign's existing **Edit** form on `/tenants`, beside **Secret**. It is saved through the form's `PATCH` with the other fields, and only when it changed.
- **A player's override** is a select on that player's row of the campaign roster, next to **Remove**: "Follows the campaign" (no override), "Can make their own items", "Can't make their own items". A change saves at once through `PATCH .../players/{id}` and says "Saved." or the API's error, putting the select back on a failure. It shows for whoever the roster already offers **Remove** to (whoever manages the campaign), and the API enforces the same.

The values come from `GET .../campaigns/{id}` (`player_self_service`) and the roster's `GET .../players` (`self_service`), which both already carry them.

## Not in scope

- Showing a player whether it is on for them: inventory-web's card already says so ([ADR 0187](0187-inventory-web-adding-an-item-to-a-board.md)).
- Setting it when a campaign is created (it starts on, as ever), or in the one-click setup.
- Any restyling: account-hub's own redesign is its own v1.0 row.

## Consequences

- A GM can say "loot comes from me" for a campaign, or "except Alice", without the API.
- RFC 0034 is built end to end, with the deploy step of ADR 0186 (which the maintainer has done) the last thing it needed.
