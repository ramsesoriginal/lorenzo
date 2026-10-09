# 0226 - LorenzoLedger: a name for the inventory file, and descriptions in it

Status: accepted, decided with the maintainer on 2026-10-09.

Amends [ADR 0191](0191-inventory-file-format-v1.md) and [ADR 0193](0193-lorenzo-inventory-import-and-export.md). Slice 6 of [RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md) is a converter outside this repository; the first one, from D&D Beyond, showed what the format lacked.

## Context

The format has been called "the inventory file" and identifies itself as `lorenzo-inventory/1`. Two things came up before any converter was written.

- **The name is a poor fit.** It says "inventory", which is one use of it, and a file that records what a character owns, where it is and what is known about it is closer to a ledger. [Identity §14.3](../brand/identity.md#143-terminology) wants one word per idea, and the format is about to be mentioned by tools that are not ours.
- **It cannot carry a description.** `note` is one line. A converter reading a character sheet has the item's full text (a magic item's rules, a weapon's properties) and nowhere to put it. [RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md) already keeps weight, value and kind as notes for a GM to read; the text is the same sort of thing and longer.

Nothing but this repository's own importer reads the format yet, and no file is known to exist outside the maintainer's two inventories, so changing the identifier now costs almost nothing and later costs files.

## Decision

### The name

The format is **LorenzoLedger**, and a file is a **ledger** (“the Ledger” in prose). The guide keeps its address, [inventory-file-format.md](../guides/inventory-file-format.md), so no link breaks. The commands keep their names: `lorenzo inventory import` and `export` read and write a ledger of a character's inventory, and a ledger of something else, later, is not ruled out.

- **The identifier** is `format: lorenzo-ledger/1`, and `"format": "lorenzo-ledger/1"` in JSON. Writers emit it.
- **The old identifier is still read.** `lorenzo-inventory/1` is accepted and means exactly what it did, so files already written keep working. Nothing is said about it: it is not a warning, since the file is right.
- **File names** are suggested, not required: `name.ledger.md` and `name.ledger.json`.

This is still version 1. The rename and the addition below happen before any v1 file exists elsewhere; a later version still adds and does not redefine ([ADR 0191](0191-inventory-file-format-v1.md)).

### Descriptions

A line quoted with `>` belongs to the item line above it.

```markdown
## Equipped
- Quarterstaff | weight: 4 | value: 2 sp | kind: weapon
  > A simple melee weapon, **1d6** bludgeoning, versatile (1d8).
  >
  > Proficiency lets you add your bonus to the attack roll.
- Backpack
  > A leather pack.
  - 7 x Rations
```

- **Where.** Any `>` line (leading spaces allowed, one optional space after the `>` dropped) belongs to the nearest item line above it in the same section, at any indentation. A writer indents it two spaces past its item, so the text stays inside the item when the file is rendered as Markdown. A `>` line before the first item of a section, or under an ignored heading, is ignored with a warning.
- **What.** The text is LorenzoScript ([RFC 0027](../rfcs/0027-lorenzoscript.md)), the Markdown dialect descriptions are written in. A bare `>` is a blank line. Several quoted lines are one description, joined with line breaks, with blank lines at either end dropped.
- **At most 20,000 characters** to an item. More is a problem, as a loose stack is: nothing is cut to fit.
- **In JSON** it is a `description` string on the item, the same text.
- **A v1 reader that does not know about it** already ignores a line that is not a list item, so a ledger with descriptions still reads there, minus the text. That is why it is a quoted line and not a field.
- **There is no `description:` field** in the one-line form: two ways to write one thing is one too many.

### What an import and an export do with it

- **Import** writes a description as a private note titled “Description”, then tells the owner's character, as it does for “Note” and “Details” ([ADR 0193](0193-lorenzo-inventory-import-and-export.md)). Order on an item: Note, Description, Details. A line that only moves an item (`--add`) writes none.
- **Export** reads a “Description” note back into the ledger, so an export and an import round-trip it.
- It is a note and not the item's `description` information on purpose: that one is what a client shows as the instance's title ([ADR 0067](0067-item-title-falls-back-to-name.md), [ADR 0112](0112-inventory-web-the-whole-item.md)), and an import must not rename what it makes.

### Everything else in the guide

Matching, sections, containers, stacks, limits and the placeholder are unchanged.

## Not in scope

- **A new field for what a converter knows beyond the six** (rarity, attunement, damage, armour class, source). A converter puts it at the top of the description, where a person reads it. Promoting any of it to a field is a later version's job, once something computes with it.
- **HTML, images and links to other entries** in a description. LorenzoScript's own entity links are accepted as text and not resolved by an import.
- **A converter** from any source. They live outside this repository ([RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md) slice 6); the first, `lorenzo-beyond` for D&D Beyond, is its own package.
- **A schema file** for the JSON form, still.

## Consequences

- A converter can keep the whole text of an item, and a GM sorting an unsorted item has it in front of them.
- A file written with descriptions is a little larger and no less readable; most of the text is a quote under a line.
- Existing `lorenzo-inventory/1` files and readers keep working, and a reader of this version reads both names forever. The cost is one more accepted string in `format.py`.
- Three places say the old name and change with this: the guide, the CLI's help and README, and the tests' sample files. The records ([ADR 0191](0191-inventory-file-format-v1.md), [0193](0193-lorenzo-inventory-import-and-export.md), [RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md)) keep what they decided and say it was amended.
