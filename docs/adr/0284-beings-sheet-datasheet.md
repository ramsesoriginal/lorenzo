# 0284 - The being sheet as a datasheet, with its weapons, abilities and authors

Status: accepted, decided with the maintainer on 2026-10-12. Slice U3 of [RFC 0043](../rfcs/0043-the-being-sheet.md); builds on [ADR 0277](0277-information-shows-who-wrote-it.md), [0281](0281-sheet-settings-and-the-sheet-read.md), [0282](0282-beings-sheet-shell-modes-and-sections.md) and [0283](0283-beings-sheet-play-stats-and-undo.md). The design is [docs/design/beings](../design/beings/README.md); where this and the prototype disagree, the prototype wins.

## Context

A skirmish player wants an operative as a datasheet: a stat line, a weapons table, abilities. Nothing about the being differs; the density does.

## Decision

- **A layout switch, apart from the mode.** Sheet and Datasheet are a quieter control beside the mode switch: the mode says what you are doing, the layout how densely the being is drawn, and the two are independent. Play works in the datasheet as on the sheet: the same cells, steppers, adjuster and undo. The datasheet shares the header's frame, has no section links in the sticky bar, and is not remembered.
- **One cell per stat, one line per group.** The stat band draws a being's stats as tiles on the sheet and as the cells of a line in the datasheet, from the same code, so what changing a number means is defined once ([ADR 0283](0283-beings-sheet-play-stats-and-undo.md)).
- **Weapons are the library's setting, read once.** The datasheet reads `GET .../beings/{id}/sheet` ([ADR 0281](0281-sheet-settings-and-the-sheet-read.md)) when it is first shown: what the being holds directly, as a table with a column for each stat of the weapon group any of them has, in the library's order, with units and signs, and a dash where one has no value. Another player's being has no weapons ([ADR 0040](0040-item-instance-read-visibility.md)), and the section is then absent, not empty.
- **A library that has not said where weapons are** gets "Carried": what the being owns, as names and counts. The datasheet never shows a table of nothing, and the sheet's own inventory section is unchanged.
- **Abilities and notes** are one block: the abilities (information of the library's ability type, from the sheet read) and then the notes, each with its text. A note that is not for everyone says so with a neutral badge and nothing more; the datasheet does not list who was told (the sheet's notes still do). Abilities are a subset of notes, not a new kind.
- **Who wrote it.** A note, on the sheet and in the datasheet, shows its author's name when the API gives one ([ADR 0277](0277-information-shows-who-wrote-it.md)): exactly as visible as the note.
- **About** is a collapsed description at the foot of the datasheet.

## Not in scope

A being's card in the list as a datasheet (design brief, open question 3); a campaign's own weapon group (the read accepts `campaign_id` and ignores it); entity templates; printing.

## Consequences

The sheet read is one request for the part of the datasheet the other reads do not give, and it is made only when the datasheet is looked at. A being opened by a link that asks for the datasheet shows it as soon as it has loaded.
