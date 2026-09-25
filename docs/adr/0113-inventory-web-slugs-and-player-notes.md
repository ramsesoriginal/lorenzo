# 0113 - inventory-web: setting slugs, and players' notes on items

Status: accepted

## Context

Any entity can have a slug since [ADR 0107](0107-entity-slugs-and-batch-resolve.md), and LorenzoScript links name entities by slug: `[[Belt Pouch]]` needs something to hold `belt-pouch`. inventory-web can set one in only one place, the optional field when a GM creates an instance. A catalog item, the usual target of such a link, can't get one at all. The item page's `?slug=` address also still assumes that only instances have slugs.

Players can't write anything in inventory-web. The API already lets them add a note to an item they hold:

- `POST .../entities/{id}/information` uses the self-or-managed tier ([ADR 0038](0038-information-payload-knowledge-crud-api.md)): an item reachable from the caller's own characters is theirs to write about.
- `note` is a free-form type ([ADR 0101](0101-editable-information-and-description-payloads.md)), so an item can have any number of notes.
- ADR 0101's edit gate lets the author edit or delete what they wrote. A knower row (ADR 0038) lets them make a restricted note readable to their own character, as loot-bot's `/note` does.

## Decision

### Slugs

GMs get a **Slug** field in three places:

- Manage items' create form.
- Each catalog item's edit panel.
- The item page, for catalog items and instances alike, next to the tag and information editors.

The field is prefilled:

- with the entity's current slug when it has one (read from `EntityDetailOut.slug`, since `ItemOut` has none);
- otherwise with a suggestion. In the create form, the suggestion follows the name and the display title as they're typed, until the GM edits the slug.

The suggestion comes from the title the item is shown by: its display title, else its name ([ADR 0067](0067-item-title-falls-back-to-name.md)). That's what an author reads, and so what they write in `[[…]]`. It's the first free candidate from [`slugify`](../../packages/lorenzoscript/src/inline.ts) of that title, shortened to fit 100 characters:

- **A catalog item** gets `slugify(title)`, then `-2`, `-3` and so on. That is the slug `[[Title]]` looks for, so a wikilink to the item works at once.
- **An instance** gets `slugify(title)-1`, `-2` and so on. The bare title stays free for the catalog item, so `[[Iron Sword]]` keeps meaning the item even when only its instances have slugs.

One `GET .../entities/resolve` request checks up to 20 candidates. A title `slugify` reduces to nothing gets no suggestion.

Saving follows the field:

- an unchanged field sends nothing;
- a cleared field sends `DELETE .../slug`;
- anything else sends `PUT .../slug`.

The field checks ADR 0107's grammar before sending. A `409` becomes "Another entity already uses …".

The instance-creation field stays optional and empty. It now uses the real suggestion as its placeholder. Filling it by default would give every instance a slug, and the tenant's one slug namespace would fill up with loot.

The item page's `?slug=` now reads `GET .../entities/resolve?slug=…`, not `.../by-slug/{slug}`: only the resolve endpoint says an entity's `kinds`, and `EntityDetailOut` doesn't. The kinds decide whether the item or the instance endpoint shows it, so a catalog item's slug addresses its page too. Only tenant members can read the catalog ([ADR 0032](0032-item-and-item-instance-crud-api.md)), so for anyone else a catalog item's slug leads nowhere, like an unknown one. The item page shows the slug for catalog items as well as instances.

### Notes

A note is an information row of type `note`. Its title is prefilled "Note" and its text is LorenzoScript.

The item page and the board's detail panel both get a **Notes** section:

- **Reading.** It lists the notes the viewer can see, from `GET .../entities/{id}/information?type=note`.
- **Writing.** "Add a note" shows on item instances when the viewer is a GM (`isCampaignGm()`) or one of their characters owns the item. The API remains the real gate. Catalog items have none: they're the GM's, and the GM has the information manager.

Notes are **private by default**, the maintainer's choice:

- A checkbox, **Everyone can read this**, starts unchecked, with a note naming who can read it otherwise: "Otherwise only Ashfang's players and the campaign's GMs can."
- A private note is created with `is_public: false`. The character that owns the item, when the author plays it, is then added as its reader with `PUT .../information/{id}/knowers/{character_entity_id}`.
- If adding the reader fails, the new note is deleted again and the error shown. Otherwise the author would have written something they can't read.
- A GM writing about an item none of their characters owns has no character to add. Their private notes are read through GM sight, as a GM-only information row is. The checkbox's note then says "Otherwise only the campaign's GMs can."

The reader is the character, not the author's `Player` row (ADR 0109's player knowers), for one reason: loot-bot's `/note` already makes a private note readable by the author's character. "Private" then means the same in both apps, and a note written in one reads the same in the other. For a character with one player, the two are the same people. The difference shows only when a character has several players, or changes hands: then the note follows the character.

The privacy promise is only as strong as the API's visibility rule. A campaign's GMs and tenant administrators can read every note on an item they can reach ([ADR 0035](0035-campaign-scoped-gm-visibility.md), [ADR 0096](0096-owner-joins-orga-in-the-information-visibility-bypass.md)). The checkbox's note says so. Hiding notes from GMs would need an API change, and the maintainer didn't choose it.

Each note has **Edit** and **Delete** wherever "Add a note" shows. Both use ADR 0101's writes and `If-Match`. The API decides whose note may change: its author, or anyone who can both see it and write about the item. Making a public note private adds the owning character as a reader in the same way.

## Not in scope

- Showing who wrote a note. `InformationOut` has no author field, so that needs a small API change first.
- Notes on the change feed ([ADR 0099](0099-player-facing-change-feed.md)), as ADR 0109 deferred them.
- Sharing a note with chosen players or characters. That's ADR 0109's knower surface, still deferred in inventory-web ([ADR 0112](0112-inventory-web-the-whole-item.md)).
- Slugs for beings, and slug history or redirects (ADR 0107).

## Consequences

- A GM can give any item or instance a slug where they already edit it, and a new item gets the slug its wikilinks expect.
- Players write in inventory-web for the first time, within what the API already allowed them.
- A private note's reader row is written after the note itself. The two-step write is undone on failure, but a crash between the steps leaves a note only GMs can read.
