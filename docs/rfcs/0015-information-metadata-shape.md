# RFC: `information`/`payload` — a generic metadata container: types, ordering, and the rest of the CRUD surface

Status: proposed; sub-slices 1 and 3 (and description edits from sub-slice 4) accepted by [ADR 0101](../adr/0101-editable-information-and-description-payloads.md); sub-slice 2 accepted by [ADR 0107](../adr/0107-entity-slugs-and-batch-resolve.md), as RFC 0027 stage 5

*Originally numbered 0014 on this branch; renumbered to 0015 on merge into `main`, which had independently claimed 0014 for [RFC 0014](0014-account-hub-tenant-admin-and-roster-management.md) (account-hub's own tenant/campaign-admin RFC) in the meantime — the same renumbering precedent already established for ADR 0050/0054/0068/0069.*

## Context

[ADR 0017](../adr/0017-information-and-payloads.md) deliberately narrowed `information`/`payload` to a proof-of-concept slice: `entity_id`+`title`+free-text `type`, four fixed payload kinds, no ordering, no `is_public`. [ADR 0028](../adr/0028-knowledge-and-group-membership.md) added `knowledge`/`is_public`. [ADR 0038](../adr/0038-information-payload-knowledge-crud-api.md) built exactly enough write surface for GitHub milestone #1's three-observer scenario: create a description, grant/revoke an entity-knower. Both ADRs named what they left out in their own "Not in scope" sections as deliberate narrowings, not oversights — this RFC is the point several of those named gaps get picked back up, because real usage (and a broader brainstorm of what the container is actually meant to hold) has now outgrown the original slice.

The container was always meant to be generic — RFC 0001's own words are "a description, an image, a claim, a note, a document, each individually typed." In practice, that ambition turned out to include things not obviously "descriptive" at all: mechanical data (a spell's effect text), business data (an item's price, a specific vendor's offer, current stock), binary handouts, and even internal per-client metadata a frontend needs to stash somewhere. Working through concrete examples surfaced that today's schema and API assume a narrower shape than the container actually needs to serve:

- `UNIQUE(entity_id, type)` makes *every* type singleton — right for `description`, wrong for `note`, `handout`, or anything else meant to repeat.
- Nothing can be edited or deleted once created.
- An `Information` row can hold exactly one `Payload`, created atomically with it — there's no way to add a second, or to author anything beyond a `description` payload at all (binary upload mechanics were explicitly left undecided by ADR 0038).
- There's no list/filter endpoint — the only way to read `information` is bundled inside `GET /entities/{id}`, fine for two or three rows per entity, wasteful once an entity can carry a dozen notes and several handouts.
- `Knowledge`'s write side only reaches entity-knowers (character/group), even though `information_visibility.py`'s read side already resolves a caller's own player-knowledge.

Separately, but landing in the same slice because it came up in the same conversation: `item_instance.slug` ([ADR 0043](../adr/0043-item-instance-slug.md)) is a `tenant_id`+`slug` uniqueness pattern that generalizes cleanly to any entity, not just item instances — worth extracting into its own table now, before a second entity subtype wants the same column repeated.

This RFC is [RFC 0011](0011-information-payload-knowledge-crud-api.md)'s sequel: 0011 shipped the smallest slice that proved the three-tier-visibility concept end to end; this one is the larger slice reflecting what the container actually needs to be to serve as genuine, general-purpose metadata storage.

## Decision

1. **`information_type(name, is_singleton, category)`** — a small, global (not tenant-scoped) catalog, covering only the fixed, code-dependent subset of `type` values the application itself behaves differently for. `category` is `technical` or `gm_authored`, so a client can filter a notes/lore editor down to the types a human actually authors, hiding system-managed ones. Seeded with exactly two rows for this slice: `description` and `main_picture`, both `is_singleton=true`, `technical`. GM-authored types (`note`, `handout`, anything a GM invents on the fly) get **no** catalog row — free text stays free text; registering them here would defeat the point of them being free-form.
2. **A partial unique index replaces the current blanket `UNIQUE(entity_id, type)`**:

   ```sql
   CREATE UNIQUE INDEX information_singleton_type ON information (entity_id, type)
     WHERE type IN ('description', 'main_picture');
   ```

   Every other `type` value can now repeat on the same entity — `note`, `handout`, `vendor_price`, and anything not yet invented. This list and `information_type.is_singleton` are **two independently-maintained facts, not one derived from the other** — a Postgres partial index predicate can't reference another table via subquery, so the catalog documents the singleton set for clients, it doesn't drive the constraint. Any future migration that adds or removes a technical/singleton type has to touch both by hand.
3. **`order` (integer) on `information`** (`UNIQUE(entity_id, order)`) **and `payload`** (`UNIQUE(information_id, order)`) — picks up ADR 0017's own explicitly-deferred "payload ordering within a bundle." Both stay strictly unique per parent, as asked; exact assignment-on-create and renumbering-on-reorder mechanics are deferred (see below).
4. **`payload_entity(payload_id, tenant_id, target_entity_id)`** — a fifth concrete payload kind, `target_entity_id` FK to `entity.id`. **Documented as narrative/informational references only** — "this NPC's spouse is [link]," not a mechanical relation. It is never a substitute for `containment`/`entity_prototype`/`ownership`/`group_member`, which stay the only *structurally* enforced entity-to-entity relations in this schema; this is a convention note in the ADR that implements this, not something the schema itself can enforce, the same class of accepted, unenforced invariant ADR 0017 already carries for "exactly one concrete payload row per `payload_id`."
5. **`entity_slug(entity_id, slug, tenant_id)`**, `UNIQUE(tenant_id, slug)`, generalizing `item_instance.slug`'s exact precedent to any entity. A genuine small win from generalizing: `item_instance.slug` needed a *partial* unique index specifically to allow `NULL` (no slug) alongside real ones; `entity_slug` doesn't have that problem at all, since "no slug" is simply "no row" — a plain table-level `UNIQUE` constraint suffices. Migration backfills existing `item_instance.slug` data into the new table and drops the column.

   Comes with a real endpoint surface, not just a schema table — the whole point of a slug is resolving it back to the thing it names:
   - **`GET /tenants/{tenant_id}/entities/by-slug/{slug}`** — resolves a slug straight to the same `EntityDetailOut` shape `GET /entities/{entity_id}` already returns, not just a bare `{entity_id}`. A slug is an alternate lookup key for the same resource, not a separate, thinner one — a client resolving a slug almost always wants the entity itself next, and a bare-id response would just force a second round trip.
   - **`PUT`/`DELETE /tenants/{tenant_id}/entities/{entity_id}/slug`** — set or clear the (singular) slug, mirroring this API's existing singular-sub-resource shape (e.g. instance ownership). Stays one slug per entity, matching `item_instance.slug`'s own precedent exactly — this isn't growing into a multi-alias system.
   - **`v_item_instance`/`ItemInstanceOut.slug`** and any of their existing consumers switch from reading `item_instance`'s own column to joining `entity_slug` on `entity_id` — the implementing ADR confirms the exact current call sites (`v_item_instance`'s view definition, `ItemInstanceOut`, and whatever item-instance-specific slug lookup exists today) rather than this RFC assuming its own memory of them is current.
6. **`GET /tenants/{tenant_id}/entities/{entity_id}/information`** — `Page[InformationOut]`, matching `list_items`'s existing pagination convention, filterable by `type` and by `information_type.category`. The real collection endpoint this container has never had.
7. **`create_information`'s duplicate check becomes type-aware.** Today's `409` fires for *any* repeated `type`, matching the blanket constraint decision 2 replaces. It needs to check `information_type.is_singleton` instead — otherwise the DB now happily allows a second `note`, while the app's own pre-check still blocks it.
8. **`PATCH`/`DELETE /tenants/{tenant_id}/information/{information_id}`** — real editing (title/type/`is_public`/`order`) and real removal, with `If-Match` concurrency per [ADR 0042](../adr/0042-concurrency-token-on-reads.md). Today, nothing created through this API can ever be changed or removed.
9. **`Payload` becomes its own addressable sub-resource**: `POST /tenants/{tenant_id}/information/{information_id}/payloads` (a `kind`-discriminated body: `description`/`number`/`picture`/`document`/`entity`), `PATCH`/`DELETE /tenants/{tenant_id}/payloads/{payload_id}`. This is what actually resolves ADR 0038's parked "binary payload upload mechanics... not resolved here" gap, and what lets one `Information` row hold more than one ordered `Payload`.
10. **Player-knowers, write side**: `PUT`/`DELETE /tenants/{tenant_id}/information/{information_id}/player-knowers/{player_id}`, mirroring the existing entity-knower sub-resource shape but against `Player`. Closes the gap where the read side already unions a caller's own player-knowledge but nothing can ever grant it.
11. **Listing current knowers** — some way to answer "who has already been told this," covering both knower kinds. Exact shape (a dedicated `GET .../knowers` collection vs. embedding the list in `InformationOut`) is left open, see below.
12. **A dedicated reorder endpoint**, for `information` (siblings under one entity) and `payload` (siblings under one `Information`) — plain per-row `PATCH` makes any real reorder an unatomic scramble of N requests each renumbering around the unique constraint. Exact shape deferred, see below.

### Sub-slices, smallest first

1. `information_type` + the partial unique index + the type-aware `create_information` fix (decisions 1, 2, 7 — these three only make sense together).
2. `entity_slug` + its lookup/set/clear endpoints + migrate `item_instance.slug`'s consumers onto it (decision 5 — independent of everything else here, can land any time).
3. `order` columns + `PATCH`/`DELETE /information/{id}` (decisions 3, 8 — `PATCH` is what actually lets `order` be set).
4. `Payload` as a sub-resource + `payload_entity` (decisions 4, 9 — resolves the binary-upload-mechanics fork as part of this slice).
5. The collection endpoint (decision 6).
6. Knowledge gaps: player-knowers + listing knowers (decisions 10, 11).
7. The reorder endpoint (decision 12 — deliberately last; it needs `order` (slice 3) to already exist).

### What this RFC deliberately does not decide

- **Binary payload wire format.** Every other endpoint in this API is uniform JSON in/out ([ADR 0020](../adr/0020-rest-api-tenant-scoping-and-schemas.md)). Base64-in-JSON keeps that uniformity at a real size cost on top of an already-BYTEA-in-Postgres design ([ADR 0017](../adr/0017-information-and-payloads.md)'s own named tradeoff); `multipart/form-data` is the efficient choice but would be this API's first departure from JSON-only. A real fork, left for the ADR that builds slice 4.
- **The reorder endpoint's exact shape** — swap-two-positions vs. move-to-position, and how a reorder touching several sibling rows at once gets a concurrency check (`If-Match` against what, exactly, when the request isn't about one row).
- **`order` assignment on creation** — whether the API always requires an explicit value from the caller, or the server auto-appends (and if so, how concurrent inserts computing "next available" avoid racing each other).
- **Whether authorization ever needs tiering by visibility** (GM-only vs. public) rather than today's flat self-or-managed-or-catalog-fallback check. ADR 0038 already named this as a deliberate narrowing; this RFC doesn't reopen it, and doesn't foreclose revisiting it either.
- **Whether `information_type` ever grows tenant-scoped rows** for GM-authored types (e.g. so a tenant can register their own vocabulary for a nicer dropdown). Deliberately "no" for this slice — revisit only if a real client asks for it, not speculatively.
- **Listing knowers' exact response shape** (decision 11) — a dedicated endpoint vs. an embedded field on `InformationOut`.
- **Whether a `Payload`'s `kind` can ever change after creation** — almost certainly not, matching `payload`'s own conceptual invariant of being exactly one kind for its lifetime (ADR 0017), but left for the implementing ADR to state explicitly rather than assumed here.

## Consequences

- The blanket `UNIQUE(entity_id, type)` becoming a partial index is a real behavior change for **every existing `information` row**, not just newly-created ones: multiple rows of the same non-singleton type become possible everywhere the moment the migration lands.
- `information_type` and the partial index's literal list are two independently-maintained sources of truth for "which types are singleton" — named explicitly in decision 2, repeated here because it's the one piece of this RFC most likely to silently drift if a future change touches only one of them.
- `payload` gains a fifth concrete kind whose distinction from every dedicated relation table (`containment`/`entity_prototype`/`ownership`/`group_member`) is convention-only, not schema-enforced — extending, not introducing, the same class of accepted gap ADR 0017 already carries.
- `entity_slug`'s migration is the one piece of this RFC that isn't purely additive — it touches `item_instance` directly (backfill, then drop the column).
- Once `Payload` is independently addressable and ordered, `InformationOut`'s response shape likely needs to expose a payload *list* rather than today's single flattened payload — a real, if modest, break from every existing consumer of the current flat shape.
- `GET /tenants/{tenant_id}/entities/{entity_id}/information`'s pagination means large information sets no longer have to travel with every `GET /entities/{id}` call — the main practical payoff of treating `information` as genuinely general-purpose metadata storage rather than "the two or three facts an item happens to have."
