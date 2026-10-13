# RFC 0043: The being sheet: a page to read, play and edit a being, and the API it needs

- **Status:** accepted and built (2026-10-12): the API slices A1 to A6 and the Beings slices U1 to U3, each in its ADR. §7 says where the build differs from what is written here.
- **Builds on:** [ADR 0270](../adr/0270-beings-app.md) to [0272](../adr/0272-beings-editing-stats-and-handing-over.md) (the Beings app), [ADR 0111](../adr/0111-inherited-descriptions-and-stat-value-sources.md) (what a value inherits), [ADR 0103](../adr/0103-stat-tags-enum-values-and-mandatory-groups.md) and [0104](../adr/0104-computed-stats.md) (tags and computed stats), [ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md) to [0121](../adr/0121-repository-updates-and-re-sync.md) (repositories), [ADR 0040](../adr/0040-item-instance-read-visibility.md) (what an owned item shows).
- **Picture:** [docs/design/beings](../design/beings/README.md) and its clickable prototype.

## Summary

The Beings app is functionally complete, but its page is a column of separate sections and its editing is a stack of forms. This RFC records the page worked out on a prototype: one sheet with a **Read, Play and Edit** switch, a **Sheet** and a **Datasheet** layout, stats drawn generically from a library's own vocabulary, and numbers that can be changed in place at the table. It then names what the API has to say for the sheet to be built exactly as drawn, and splits the work into slices.

No game system is assumed. A GM running an NPC, a player at the table, a skirmish player reading a datasheet, an author who wants prose and a heist crew preparing a plan are equally served by the same page, because the page is built from stat groups, stat definitions, notes and what a being carries, not from a ruleset.

## 1. Decisions

1. **Three modes, two layouts.** Read, Play and Edit say what you are doing; Sheet and Datasheet say how dense the being is drawn. The mode switch stays in reach in a sticky bar, on a phone too.
2. **In-place changes outside Edit.** In Play, a number can be taken away from, added to or set to an amount, and a tag toggled; every change can be undone. A note can be added in Read and Play. Edit builds the being.
3. **Stats are drawn by type and group** from the library's vocabulary. A value that is inherited or calculated is drawn dashed and says where it comes from; a calculated value can say how it was made up.
4. **The vocabulary says how a stat is shown**: a unit, whether a number is signed, whether it can be changed in play (also for tags), whether it is pinned to the sticky bar, and an order for stats and groups. Three optional hints link a stat to another: a maximum ("of 9"), a minimum (the floor of a stepper) and a resolved value (the "+3" beside a score). Hints are clues, never limits.
5. **Authors are visible** on information that is visible.
6. **A datasheet** is a layout of the same being: each stat group a line of cells, what is equipped as a table of the stats of a weapon group, and abilities. Which stat group is the weapon group, and which type of information is an ability, are settings of the library.
7. **Brand.** The sheet is built on `apps/brand` and `packages/brand` as they are; what the sheet adds stays in `apps/beings` until a second app needs it ([ADR 0098](../adr/0098-branding-css-app-and-package.md)).

## 2. What the API has to say

Read against the code, not assumed. Most of the sheet works on the API as it is (modes, the sticky bar, stepping and undo, notes and their audiences, who plays a being, hand over, pictures, inventory). These seven things did not:

| Need | Today | Slice |
| --- | --- | --- |
| "From Dwarf", and which values are calculated | A stat value is `{name, value, own}`; the view names the holder only of a formula | A1 |
| Why armour class is 15 | The only explanation is a tenant-admin preview with no coefficients, and none for a contents formula | A1 |
| Who wrote a note | The model stores `created_by`; the read does not show it | A2 |
| Unit, signed, adjustable, pinned, an order | None exists; stat definitions and groups cannot be edited at all | A3 |
| "of 9", "+3", a floor | Nothing relates one stat to another | A4 |
| All of the above through repository copy, updates, digest and the seed | Snapshots hold name, type, group and enum values only | A5 |
| Equipped items with the stats of a weapon group, and abilities | An item read carries four fixed stat lists | A6 |

## 3. Slices

| Id | What | ADR | Issue | Depends on |
| --- | --- | --- | --- | --- |
| D | This RFC, the ADRs, and the design brief | | #662 | |
| A1 | Where a stat value comes from, and an explanation read | [0276](../adr/0276-where-a-stat-value-comes-from.md) | #663 | |
| A2 | Information shows who wrote it | [0277](../adr/0277-information-shows-who-wrote-it.md) | #664 | |
| A3 | Stat definition display fields, order, and `PATCH` | [0278](../adr/0278-stat-definition-display-fields-order-and-patch.md) | #665 | |
| A4 | Stat hints | [0279](../adr/0279-stat-hints.md) | #666 | A3 |
| A5 | Display fields in repository copy, updates, digest and the seed | [0280](../adr/0280-display-fields-in-repository-copy-updates-and-seed.md) | #667 | A3, A4 |
| A6 | Sheet settings and the sheet read | [0281](../adr/0281-sheet-settings-and-the-sheet-read.md) | #668 | A3 |
| U1 | Beings: the shell (modes, sticky bar, sections) | [0282](../adr/0282-beings-sheet-shell-modes-and-sections.md) | #669 | |
| U2 | Beings: stats on the sheet, and playing them | [0283](../adr/0283-beings-sheet-play-stats-and-undo.md) | #670 | A1, A3, A4 |
| U3 | Beings: the datasheet | [0284](../adr/0284-beings-sheet-datasheet.md) | #671 | A2, A6, U1 |

The migrations of A1, A3, A4 and A6 form one chain, so the API slices are built and merged in the order A1, A2, A3, A4, A5, A6. U1 to U3 follow once the API is in.

## 4. Settled with the maintainer

- **Position, as proposed:** order is copied when a library copies a repository and is not part of the snapshot that updates compare, so reordering a repository does not fill every library's updates with changes. A library can order its own vocabulary. If the maintainer meant that position should be synced by updates like the other fields, that is one field added to the snapshot in A5.
- **A hint's floor** is the value of the stat it links to on that being, and applies only when a minimum hint is set and that stat has a value there. Without one, nothing is clamped.
- **Another player's datasheet is empty of weapons**, for now: item reads keep [ADR 0040](../adr/0040-item-instance-read-visibility.md).
- **Settings are the library's**, with an optional `campaign_id` on the sheet read that is accepted and validated and does nothing yet, so per-campaign overrides can come without changing the route.
- **Adjustable governs tags** in Play as well as numbers.
- **Abilities are a subset of notes**: information of a configured type.
- **Authoring the new fields in Bench and account-hub is deferred.** Until then they are set through the API, `lorenzo api` and the seed.

## 5. Not in scope

Entity templates and visual templates (dots, tracks, clocks, a stat paired with its maximum as one tile); the authoring UI named above; per-campaign overrides; a different rule for who sees an opponent's weapons; the phone header being more compact than the prototype's.

## 6. Open questions

- **Templates.** When they come, they can choose which stats are vitals, which are shown as a pair, and the weapon group, instead of the settings and flags this RFC adds. Do the flags stay as defaults?
- **Reading a being's sheet as another player.** A skirmish opponent reads your datasheet. Item visibility says no today; a rule that equipped weapons are readable with the being is the likely answer.
- **Undo beyond Play.** Play changes only, for now.

## 7. As built

What changed on the way, each in its ADR:

- **The stat vocabulary is readable by every participant** ([ADR 0281](../adr/0281-sheet-settings-and-the-sheet-read.md), amended). It was for library members only, and a player has no membership; without it a player's sheet could not know which numbers a table may change. Writing is unchanged.
- **The mode and the layout are not remembered** ([ADR 0282](../adr/0282-beings-sheet-shell-modes-and-sections.md)); a page opens in Read and as a sheet. This answers the design brief's question 5.
- **The datasheet's note badges** say only "Not for everyone" where a note is not public; the sheet's notes still show the audience in full ([ADR 0284](../adr/0284-beings-sheet-datasheet.md)). A library with no weapon group gets a "Carried" table.
- **Edits in Edit are not undoable**, as in §6; Play's are, up to thirty steps ([ADR 0283](../adr/0283-beings-sheet-play-stats-and-undo.md)).
- **The numbers of the ADRs are 0276 to 0284.** Another ADR took 0275 while this was being written, so the series moved up by one from what the milestone's title says.
