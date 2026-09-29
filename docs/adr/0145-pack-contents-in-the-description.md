# 0145 - Pack contents in the pack's description, and handing a pack out

Status: accepted

Slice 6 of [RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md) (R7). Builds on [ADR 0144](0144-lorenzo-import-mapping-identity-plan-apply.md) (the importer) and [ADR 0140](0140-a-stack-when-an-item-instance-is-created.md) (a stack in one create).

## Context

An MPMB pack lists its contents by display name: `["Rations, days of", 5, 2]`. An entry ending in `, with:` is a container, and the entries after it go inside. R7 decided where that lives in Lorenzo: not in a table only the CLI has (a copy of a repository carries tenant data, so a subscriber would get a pack with nothing in it), and not as real child items (containment is written only through instance routes, its primary key is the child so the same Rations can't sit in two packs, and nothing would instantiate them). It goes in the pack item's **public description**, as a strict list.

R7 left two things to be checked while building: that the server leaves a description's text untouched, and how names in a pack are resolved to items.

## Decision

### The list

```text
This pack contains:

- 1 x [Backpack](basic-gear-backpack)
  - 5 x [Rations (1 day)](basic-gear-rations-1-day)
  - 2 x [Torch](basic-gear-torch)
- 1 x Alms box
```

- **A line with a link is an item of the catalog.** `[Label](slug)` is LorenzoScript's own entity link ([ADR 0105](0105-lorenzoscript-entity-references-and-resolver.md)), so the description renders as a list with links, and its links are references: `GET …/entities/{id}/backlinks` on Rations answers "which packs contain this" with no table of its own.
- **A line without one is plain text,** for something the sheet has no gear entry for.
- **Everything listed after a `, with:` entry goes inside it** (two-space indent), as the sheet's own comment says. Entries before any container are at the top.
- **The parser is strict and reads nothing else.** A line is `- N x [Label](slug)` or `- N x text`, indented by whole levels, at most three deep. Prose, a mis-indented line or a link with a bad slug is ignored, so a person who adds a sentence to the description cannot break handing the pack out. It is Python, since `packages/lorenzoscript` is TypeScript; the format was chosen to be valid LorenzoScript, and to be read by anything with a regular expression.

### Resolving names

Each entry is resolved against the items of the same run, in this order, and never guessed at:

1. **A row in `[pack_items]`** (built in, and your map's on top): `"candles" = "gear:candle"` links to that entry, and `"alms box" = "text"` says it is not a catalog item.
2. **An exact, case-insensitive name** among the names the items go by (`name`, `invName`, and the name shown once the price is taken off). A name two items answer to is reported, not picked.
3. **Otherwise** it stays plain text and is reported.

The built-in map answers the SRD's own gaps: five plurals and wordings of real gear (`Candles`, `Pitons`, `Torches`, `Costumes`, `Perfume, vial of`), and seven things the sheet lists only inside packs and has no entry for (an alms box, a censer, vestments, a book of lore…). Of the SRD's 66 pack entries, 50 matched exactly and none were ambiguous.

**Quantities are converted to the item's own unit.** A pack counts in units of its name (`["Hempen rope, feet of", 50, …]` is 50 feet); the item is a coil of 50 feet. Taken literally that is 50 coils. The count is divided by the item's bundle size (50 feet → 1 coil), rounded up and noted when it doesn't divide, and the line is labelled with the item's own name so the number reads correctly.

An entry nothing could be linked to does **not** hold the pack back. It is listed in the plan (`pack.unresolved`), in `review-queue.json` (kind `pack`, with the row to add), and in `proposed.map.toml`, and under `--strict` it makes the exit code `1`.

### When it is written

- **After every item it names exists.** `apply` writes packs last.
- **At first import,** because information is copy-once and not re-synced ([ADR 0121](0121-repository-updates-and-re-sync.md)): a first release that left it out would never reach a copy made from it. A pack that exists without its description counts as unfinished, so a run that was interrupted, or an earlier import without this slice, is completed by the next.

### Handing a pack out

`lorenzo pack give <pack> --tenant T [--owner CHARACTER] [--into CONTAINER] [--dry-run]` reads the description, creates the container's instance, then each thing inside it with `container_entity_id` and its `quantity` (ADR 0140), and prints what it made. It is client-side orchestration over routes that exist; it needs no `apps/api` capability, and any client can do the same from the same text.

- Plain-text lines are skipped, and said so.
- Loose entries are each their own instance, or one stack in `--into` if given (at most 50 loose, as a guard against a typo).
- The owner, if given, is set on everything created.
- It refuses, before creating anything, if the pack has no list or names an item this tenant doesn't have (for instance a copy that lacks part of the import).

## What was verified

Against the real API rather than assumed: the server stores and returns the description text exactly as written, including the indentation and the links; the backlinks of Rations list the pack; the seven SRD packs come out link-clean under `--strict`; and Explorer's pack, handed out, is a container holding stacks whose weight is what the recipe says (a camper's pack of 5 + 10 + 2 + 10 comes to 27.0).

## Consequences

- A pack is prose plus a list in a tenant, so it copies with the repository and can be edited by a person. The cost is that its meaning is a convention: change the description carelessly and the list can stop parsing (a line that doesn't parse is simply not handed out).
- The long-term home is real child items (RFC 0025 R7 names it: "instantiate with contents" as a first-class capability). Moving there is mechanical: parse the list into containment rows.
- Slugs in the list are the machine keys. A renamed slug doesn't rewrite `[…](old-slug)` text, so the namespace a pack's items were imported under is part of what it depends on (ADR 0144).
- The rounding of a quantity that doesn't divide a bundle is a judgment the importer makes and reports; it is not silent.
