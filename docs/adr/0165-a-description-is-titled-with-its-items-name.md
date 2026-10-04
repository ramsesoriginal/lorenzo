# 0165 - A description is titled with its item's name

Status: accepted

Fixes a defect in what [ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md) and [ADR 0144](0144-lorenzo-import-mapping-identity-plan-apply.md) built, found by the maintainer on 2026-10-04 on the first real import of the sheet's SRD into a repository. Follows the same fix to inventory-web in [ADR 0112](0112-inventory-web-the-whole-item.md).

## Context

An item's displayed title is the title of its description: `ItemOut.title` is read from the entity's `type = 'description'` information row, and falls back to the entity's own `name` only when there is no such row ([ADR 0019](0019-item-and-v-item.md), [ADR 0067](0067-item-title-falls-back-to-name.md)). [ADR 0112](0112-inventory-web-the-whole-item.md) met the same thing from the other side: inventory-web's editor titled every new description "Description", so writing a description renamed the item, and it now starts a new description with the item's name.

`lorenzo seed` and `lorenzo apply` had the old bug. Both wrote every description they made with the title "Description". So every taxonomy node and every imported item that has a description shows as "Description" wherever a client displays `title` (the board, the ancestry tree, the messages when an item is given), while the entity's own `name`, and any item without a description, still show the right name. The maintainer saw it on the Spellcasting focus node and on the heavy crossbow, with correct slugs and correct names in some views and "Description" in others. Nothing in the importer's design asked for it: it was the placeholder the first editor used.

## Decision

**A description the CLI writes is titled with its item's name**: the name the entity is given, for a node ([ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md)) and for an imported item or pack ([ADR 0144](0144-lorenzo-import-mapping-identity-plan-apply.md), [ADR 0145](0145-pack-contents-in-the-description.md)). Other information the importer writes (an alias list, anything the map's rules add) keeps the title its rule gives it: only the description is the item's title.

**Both commands also put right what they have already written.** A description titled exactly `Description`, on a node or item the command manages, is given the entity's own name as its title.

- It is **an action in the plan, not a surprise**. `seed` lists it as a `retitle` action, so `--dry-run` shows it and exits 2 while there is one. In `apply` the item is `complete`, like an item the CLI began and didn't finish, so `plan` reports it as pending and `apply` asks as it always does.
- It is written with the API's own update, `PATCH .../information/{id}` with `If-Match` taken from a read of the row, and only the title is sent. A row that changed in between is reported and fixed by running the command again, as re-parenting is ([ADR 0144](0144-lorenzo-import-mapping-identity-plan-apply.md)).
- **Only that one title.** A description titled anything else is somebody's choice, a display title different from the name, and is left alone, as is a description whose title already is the name.
- It is **idempotent**: once fixed there is nothing left to find, so a second run reports nothing to do.

This is the one change `seed` and `apply` make to something that exists without being asked with a flag. [ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md) has `seed` change nothing and [ADR 0144](0144-lorenzo-import-mapping-identity-plan-apply.md) has `apply` change a parent only with `--reconcile`. The exception is made because the title "Description" is the CLI's own defect rather than an edit anyone made, because it can be recognised exactly, and because it is shown in the plan first. A flag would have meant the broken data stayed broken until somebody found it.

## Not in scope

- **The API.** That a description's title is the item's name is the model's rule ([ADR 0019](0019-item-and-v-item.md)); this ADR doesn't change it, or how `title` falls back.
- **A command or flag of its own** for retitling, or for retitling anything other than the one exact title.
- **Tenants that copied a repository.** Their copies change the way any later change to a repository reaches them: the repository publishes again and they take it with `lorenzo repo updates` ([ADR 0121](0121-repository-updates-and-re-sync.md)).
- **A rename.** Only the description's title changes; the entity's name and slug are never touched.

## Consequences

- After upgrading, run each repository once through `seed` (every layer) and `apply` (the same files and map), publish it again, and let the tenants that copied it take the update.
- `plan`'s `complete` count includes the retitles, and `seed --dry-run`'s actions gain the kind `retitle`.
- `lorenzo_cli`'s operation table gains `GET` and `PATCH` for an information row, and is checked against the API's schema like the others.
