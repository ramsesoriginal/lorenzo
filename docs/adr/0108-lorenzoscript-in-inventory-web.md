# 0108 - LorenzoScript in inventory-web: rendered descriptions and a description editor

Status: accepted

## Context

[RFC 0027](../rfcs/0027-lorenzoscript.md) stage 6 brings LorenzoScript into `apps/inventory-web`: the editor on the item description, and a Lorenzo resolver on the typed API client, with entity images fetched using the viewer's token and dates in the locale from `/me`. Everything it needs now exists:

- the parser and renderer ([ADR 0100](0100-lorenzoscript-core-parser-and-renderer.md), [0102](0102-lorenzoscript-standard-extensions.md), [0105](0105-lorenzoscript-entity-references-and-resolver.md))
- the editor ([ADR 0106](0106-lorenzoscript-editor-and-demo.md))
- the description write routes ([ADR 0101](0101-editable-information-and-description-payloads.md))
- slugs and batch resolve ([ADR 0107](0107-entity-slugs-and-batch-resolve.md))

Today the item page and the board's item panel both show description text with `textContent`, so Markdown appears raw.

Building on ADR 0101 turned up one gap. It says a client builds `If-Match` for a payload from that payload's `updated_at`, since no response carries a payload's own `ETag` header. But the two texts differ: `etag_for` writes `isoformat()`, `…+00:00`, while the JSON `updated_at` is pydantic's `…Z`. A client that follows the rule gets `412` every time.

## Decision

### Packages

`apps/inventory-web` depends on `@lorenzo/lorenzoscript` and `@lorenzo/lorenzoscript-editor` as `workspace:*`. They ship TypeScript source, and Astro's Vite bundles them like the app's own modules. The editor's styles already come from `@lorenzo/brand`'s `components.css` (`.ls-editor`, `.ls-content`), which the app links.

### Rendering, shared by both views

One module renders descriptions for the item page and the board's item panel alike. For a set of texts, it:

1. parses each text and collects its `references()`
2. resolves every entity and image slug not yet known through `GET .../entities/resolve`, 100 per request (the API's cap)
3. fetches the main picture for each image reference
4. renders synchronously with that resolver, in the viewer's locale

Results are cached for the page's lifetime, including the slugs that didn't resolve, so re-rendering a live preview only asks about new slugs. The output goes into `.ls-content` containers with `innerHTML`, which ADR 0100's safe-by-construction renderer allows.

- **Locale.** `/me`'s `locales` if the user has set any, otherwise the browser's languages. `/me` is fetched once per page and shared with the existing `isCampaignGm` check.
- **Pictures.** `![alt](slug)` shows the entity's `main_picture`. The app reads it from `GET .../entities/{id}` and fetches its bytes from `GET .../payloads/{id}/content` with the viewer's token, then shows them through a `blob:` URL. An entity without a picture, or one the viewer can't see, renders as its alt text. External `https` images stay allowed, the renderer's default; turning them off is a later option.
- **Calendar.** `{{cal …}}` has no resolver yet, so it renders as its expression.

### Where a link leads

The app has two views an entity can open in: the item page (`/item/?tenant=…&id=…`) for `item` and `item_instance`, and the board filtered to a character (`/board/?tenant=…&character=…`) for `character`. A plain `being` has no view here.

- A hint that names one of the entity's kinds, and has a view, picks that view: `character/ashfang` opens the board.
- Otherwise the link follows the entity's own kinds, in the order `item_instance`, `item`, `character`. The hint says where to go; it doesn't make the link fail.
- An entity with no view in this app renders as plain text, like one that doesn't resolve.

A small pure function makes this choice, so it's unit-tested without a browser.

### Editing, on the item page

- **Who sees it.** GMs, by the app's existing `isCampaignGm()` convention. The API's self-or-managed check stays the real gate; a refused save shows the API's own message.
- **Opening the editor.** "Edit description", or "Write a description" when there's none, fetches `GET .../entities/{id}`. It edits the first description payload, by `order`, of the entity's `description` information. The API only ever creates one; any others, from seeding, are left alone.
- **Saving an existing description.** `PATCH .../payloads/{id}` with `{content}` and `If-Match` built from the payload's `updated_at` at the moment the editor opened.
  - `412` means someone saved in between. The editor stays open with the author's text, and says so.
  - The page then reloads the item and re-renders.
- **Writing a new description.** `POST .../entities/{id}/information` with type `description`, title `Description`, the text, and the viewer's first locale.
  - A "Players can read this" checkbox, checked by default, sets `is_public`. inventory-web has no way to name knowers, so a private description written here would stay hidden from every player.
- **While editing,** a short list below the editor names every link that won't work for readers: slugs nobody holds yet, hints the entity doesn't match, and entities with no page here. Readers never see these notes; for them, a broken link is simply plain text.

The board's panel renders but doesn't edit.

### `etag_for` writes the JSON timestamp

`apps/api`'s `etag_for` now writes `updated_at` exactly as the JSON body does: it uses pydantic's own serializer, so the two can't drift apart. That makes ADR 0101's rule true for every resource:

- clients that echo an `ETag` header back, like loot-bot, notice nothing
- a token issued before the deploy fails once with `412`, the same as any concurrent edit, and a fresh read fixes it

## Not in scope

- Editing on the board, or on catalog list rows.
- Several description payloads per entity, one per locale. There's no route to add a second.
- Naming knowers, or changing a description's visibility after it's written.
- Backlinks and stored references: stage 7.
- In-game calendar rendering, pending its own RFC.

## Consequences

- Descriptions written as plain text render the same as before, since a paragraph is a paragraph. One exception: Markdown syntax in existing text, such as `*`, `_`, or a leading `#`, now takes effect.
- Every page showing descriptions makes one more request when a text has entity links, and two more per distinct entity picture.
- ADR 0101's `If-Match` rule now works as written. Anyone else building `If-Match` from `updated_at` needs no workaround.
