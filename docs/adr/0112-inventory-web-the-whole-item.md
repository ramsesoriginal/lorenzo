# 0112 - inventory-web shows the whole item, and edits its descriptions, tags, and information

Status: accepted

## Context

inventory-web shows an item in two places: the board's detail panel and the standalone item page. Each has its own copy of the same six hard-coded stats (weight, height, price, rarity, HP, armour) plus a magical/cursed line. The API sends more: `ItemOut` has four stat groups (physical, economic, destroyable, damaging), every tag, and pictures, and all of it inherits through prototypes since [ADR 0111](0111-inherited-descriptions-and-stat-value-sources.md).

Writing was narrower still:

- A description can only be written on the item page, and it had a bug. [ADR 0108](0108-lorenzoscript-in-inventory-web.md)'s editor titled every new description "Description". A description's title is also the item's displayed name ([ADR 0019](0019-item-and-v-item.md)), so writing one renamed the item.
- Manage items creates and edits items without a description.
- The API's information and payload writes ([ADR 0101](0101-editable-information-and-description-payloads.md)) and tag writes ([ADR 0103](0103-stat-tags-enum-values-and-mandatory-groups.md)) have no UI.

## Decision

### One item view

`src/lib/itemView.ts` renders an `ItemOut` or `ItemInstanceOut` for both the board's panel and the item page. They show the same thing, and the hard-coded stats go:

- **Stats.** The four groups are Physical, Economic, Destroyable, and Damaging. Each shows the stats that have a value, and a group without any is left out. Weight, price, HP and the rest are among them.
- **Tags.** Tags that are on show as chips, magical and cursed among them. An explicit off, or no value, shows nothing to readers; the tag editor below is where a GM sees those.
- **Pictures.** Fetched with the viewer's token and shown through `blob:` URLs, as LorenzoScript pictures are (ADR 0108).
- **Descriptions.** The item's own first, rendered as LorenzoScript, then inherited ones. Each inherited description or picture is labelled "From Longsword", linking to that item's page.

### Writing a description, with its display title

The description editor gains a **Display title** field: the description's title, and so the item's displayed name.

- It's prefilled with the current title, which is the item's name when it has none. Clearing it shows the name again ([ADR 0067](0067-item-title-falls-back-to-name.md)). This was the maintainer's choice, over leaving the title empty or copying the name silently.
- A changed title is saved with `PATCH .../information/{id}`, using `If-Match`. Text and title are two writes. If one fails, the editor stays open and says which one.
- Items renamed "Description" by the old editor get their name back through this field.
- The edit panel's Name field now reads the entity's own name. It used to show the display title, so saving the panel could copy that title onto the name.

The same editor appears in three places:

- on the item page, as now
- in Manage items' create form, optional, written right after the item is created
- in each catalog item's edit panel

### Editing tags

GMs get a tag editor on the item page. It lists every `bool` stat definition in the tenant's `tags` group, each with three states:

- **Inherited** uses `DELETE`.
- **On** uses `PUT`.
- **Off** uses `PATCH`.

The current state comes from `EntityDetailOut.stats`: the effective value, and ADR 0111's `own` flag. The editor also shows the effective value an inherited tag resolves to.

Listing stat definitions needs tenant membership (`get_tenant_context`), but writing a tag only needs standing over the entity. A GM who isn't a tenant member therefore sees a note instead of the editor. Opening the list to every participant would be a small API change for later.

### Managing information

GMs get an **Information** section on the item page. It lists every piece of the entity's information from `GET .../entities/{id}/information` ([ADR 0109](0109-player-knowers-knower-listing-and-information-list.md)): title, type, whether players can read it, and its rendered text.

- **Add** with a title, a type, "Players can read this", and LorenzoScript text (`POST .../entities/{id}/information`).
- **Edit** the title, type, and visibility with `PATCH .../information/{id}`, and the text with `PATCH .../payloads/{id}`, each using `If-Match`.
- **Delete** after a confirmation, with `DELETE .../information/{id}` using `If-Match`.

The description is one of these pieces, the one of type `description`. Adding a second singleton type returns the API's `409`, which is shown as a message.

Every write here is GM-only by the app's `isCampaignGm()` convention. The API's own checks remain the real gate.

## Not in scope

- Who knows a piece of information: ADR 0109's knowers and player knowers. The maintainer deferred them.
- Editing stat values other than tags, and uploading pictures.
- Editing on the board, which stays read-only.

## Consequences

- The board and the item page can't drift apart again: one module draws both.
- Every item shows its prototypes' descriptions and pictures, labelled, as ADR 0111 decides.
- Writing a description never renames an item by accident; the display title is always visible where it's edited.
