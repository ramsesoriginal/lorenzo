# 0264 - Link previews: a preview endpoint with per-kind templates held in code

Status: accepted. The "Link registry plus hover preview templates" row of [v1.0](../../v1.0.md) and the hover half of inventory-web's "Notifications, hover previews" row. Builds on [RFC 0027](../rfcs/0027-lorenzoscript.md) (LorenzoScript links), [ADR 0107](0107-entity-slugs-and-batch-resolve.md) and [ADR 0240](0240-my-links-resolve-in-the-context-of-the-text.md) (resolving a link name, `my/` links), [ADR 0108](0108-lorenzoscript-in-inventory-web.md) (inventory-web renders links), [ADR 0111](0111-inherited-descriptions-and-stat-value-sources.md) (an entry shows its ancestors' descriptions and pictures), [ADR 0217](0217-entity-kinds-the-routes-the-updates-and-the-publish-check.md) (what an entry is), [ADR 0237](0237-api-pictures-and-information-order.md) (the main picture) and [ADR 0028](0028-knowledge-and-group-membership.md)/[ADR 0109](0109-player-knowers-knower-listing-and-information-list.md) (what a caller may read). Bench's own card ([ADR 0233](0233-bench-links-to-entries-in-text.md)) is unchanged.

## Context

A link in LorenzoScript text names an entry. A reader pointing at it wants to know what it is before following it: its name, what kind of thing, a few numbers, the start of its description, a picture. Bench draws such a card from data it already mirrors (ADR 0233). inventory-web holds no mirror: to draw one it would read the full entry (`GET .../entities/{id}`, every stat, every information row, containment) for each link a person happens to point at, and then choose from it on the client. Which numbers matter differs by kind: a sword's damage and weight, a character's hit points, nothing for a group.

The kinds a link can lead to are the ones an entry can be (ADR 0217): `item`, `item_instance`, `being`, `character`, and a bare entry. Links by `my/` ([ADR 0240](0240-my-links-resolve-in-the-context-of-the-text.md)) and pictures resolve to the same entries, so an entry id is the one thing every kind of link ends in.

## Decision

### The endpoint

`GET /tenants/{t}/entities/{entity_id}/preview`, open to a tenant participant like `GET .../entities/{entity_id}`. It answers `LinkPreviewOut`:

- `entity_id`, `name`, `slug` (the link name, or null), `kinds` (as `EntityListOut` gives them);
- `template`, the name of the registry template that built the card (`character`, `being`, `item_instance`, `item`, or `entry` for the fallback), so a client can style by it;
- `picture_url`, the main picture's content URL (ADR 0237), the entry's own or the nearest ancestor's, or null; a protected file, fetched with the viewer's token as every picture is;
- `stats`, `[{ name, value }]`, the effective values (inherited and computed ones included, as `GET .../entities/{id}` gives them) of the stats the template names;
- `excerpt`, the start of the description as **plain words**, the markup read out (LorenzoScript parsed with the server's port, `lorenzoscript.py`; links keep their words, pictures give none), cut at a word with an ellipsis; empty when there is none.

**Visibility is the single read's, exactly.** The description and the picture are `Information` rows and go through `InformationVisibility.can_see` (ADR 0028/0109), the rule `GET .../entities/{id}` applies: a GM-only description or picture is not in the card of a caller who may not read it. Where the entry's own description is hidden from the caller, the card falls through to the nearest ancestor description the caller can read (the same walk an item's page makes, ADR 0111), never to the hidden one. An entry that is missing, or another library's, answers `404` as the single read does; nothing in the card is readable by that caller anywhere else. A test reads the same entry as the owner and as a plain participant and checks no hidden text is in the second body.

The card is built from a lighter read than the single entry's: no number or document payloads, and for pictures only that one exists (the file's bytes are never loaded), so a hover costs a few small queries.

### The registry

`apps/api/src/lorenzo_api/link_previews.py`, one module, a small declarative table `TEMPLATES: kind -> PreviewTemplate` plus `FALLBACK` for a bare entry:

| Template | Stats shown (in this order, at most) | Description | Inherits description and picture |
| --- | --- | --- | --- |
| `character` | hp, armor, height (3) | 200 chars | no: a character is its own person, not a copy of its prototype |
| `being` | hp, armor, height, rarity (3) | 200 | yes |
| `item_instance` | damage, armor, weight, price, rarity, hp (4) | 200 | yes |
| `item` | damage, armor, weight, price, rarity (4) | 200 | yes |
| `entry` (fallback) | none | 200 | yes |

`template_for(kinds)` picks the most specific kind (`character` before `being`, `item_instance` before `item`). Stats are matched by the name the library gave them, without regard to case (a stat definition belongs to the library, not to the code); one the entry has no value for is skipped; tags (booleans) are never shown. Pure functions, no database: `template_for`, `pick_stats`, `excerpt_of`, unit-tested on their own.

Templates are **code, not data**. A new kind is one row. The registry is the only place that knows which numbers matter for which kind.

### inventory-web

- Every `a.ls-entity` inside a `.ls-content` (descriptions and notes) opens the card: a pointer resting on it for 300 ms, keyboard focus at once, a tap at once. The link already leads to an id (`/item/?...&id=` or `/board/?...&character=`, from the resolver, `my/` links included), so the card is asked for by id; a link without one (a slug address) shows no card.
- The card is `role="tooltip"`, the link gets `aria-describedby` while it is open, Escape closes it with focus left on the link, and leaving the link or blurring closes it. Leaving takes 150 ms and coming back, to the link or onto the card, cancels it, so a pointer crossing the gap does not make it flicker, and the card can be hovered (WCAG 1.4.13). It is put away on scroll. It takes no focus and has no controls.
- **Touch:** the first tap on a link opens its card and does not follow; a second tap on the same link follows it; a tap elsewhere closes it. Touch pointer events do not trigger the hover path.
- Cards are cached for the page, per entity (`createCardCache`): one request however often it is pointed at; a `404` is remembered as "no card", any other failure is forgotten so the next hover asks again.
- The timing is a small pure state machine (`previewState.ts`, injected timers) with unit tests; the DOM is one listener set on the document, so texts drawn again need nothing.

## Alternatives considered

- **Templates a library author edits (data, not code).** Rejected with the maintainer: it is a settings surface and a migration for something no one has asked to tune, and a stat chosen by name in a template written by a person is a thing that breaks silently when the stat is renamed. The registry can become data later without changing the endpoint.
- **Client-only: build the card in each client from `GET .../entities/{id}`.** Rejected with the maintainer: every client (inventory-web, the loot bot, account-hub, Bench for an entry it has not mirrored) would repeat the per-kind choice and the visibility-sensitive excerpt, and a hover would read far more than a card shows.
- **A batch or by-slug variant** (`GET .../entities/previews?slug=`, parallel to `resolve`). Not built: every link inventory-web renders has been resolved to an id already, so the by-id route is the one used, and a hover asks about one entry at a time. It would be one more route over the same function if a client needs the card without a resolve.
- **Rendering the excerpt as HTML on the server.** Rejected: plain words need no escaping on the client and cannot carry a link that would be followed inside a tooltip.

## Consequences

- One new route, `LinkPreviewOut` and `LinkPreviewStatOut`, in the OpenAPI schema; `packages/api-client`'s generated schema and the CLI's generated models are regenerated (the CLI's enum names renumber as they do whenever a schema with a new enum use is added).
- inventory-web gains `lib/linkPreview.ts`, `lib/previewState.ts` and `components/LinkPreview`, mounted once from the layout.
- A description with a picture inherits from an ancestor even when the entry's own picture is hidden from the caller; the card does not say which entry a description came from (the item page does).
- The stat names in the templates are the ones the importer and the standard stat groups use. A library with other names gets cards without stats, not an error.
- Other clients (loot-bot embeds, account-hub) can use the same route; none does yet.
