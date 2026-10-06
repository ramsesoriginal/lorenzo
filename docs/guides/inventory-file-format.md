# The inventory file (format v1)

A plain text file that lists what one character carries and owns: what it is, how many, and what it is in. Lorenzo reads it to fill in a character's inventory, and writes the same file back out when you ask it to. You can write one by hand, or have anything (a spreadsheet export, a script, an assistant) produce it from this page.

> **Status: proposed** in [RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md) and recorded in [ADR 0191](../adr/0191-inventory-file-format-v1.md). The format is stable enough to write files against; the commands that read and write it (`lorenzo inventory import` and `export`) are not built yet. Converters from spreadsheets (CSV) and LaTeX lists are planned and will come, but may take a while. Until then, write the file by hand or make a small script of your own.

## The shortest useful file

```markdown
format: lorenzo-inventory/1
owner: Mira

## Equipped
- Dagger
- Backpack
  - 9 x Rations
  - Waterskin | note: filled with water

## Not carried
- Chest | place: the inn at Pal Vaz
  - Spare cloak
```

That is all of it: a header, two sections, and a list where **indenting means "in"**.

## The parts

### The header

Two lines before the first `##` section, as `key: value`:

| Key | Meaning |
| --- | --- |
| `format` | Always `lorenzo-inventory/1`. Required, so a reader knows what it is looking at. |
| `owner` | The character's name (or its id) whose inventory this is. **One owner per file.** Required. |
| `library` | Optional hint: the library (tenant) the file was written for, as its slug or name. If it does not match the one you import into, you are told before anything is made. |

Any other text outside the sections (a title, a paragraph, a `#` heading) is ignored, so you can write notes to yourself in the file.

### The two sections

- **`## Equipped`**: what the character has in hand or on them, at the top level. Also accepted: `Holding`, `Hands`, `In hand`, `Worn`.
- **`## Not carried`**: what the character owns but is not carrying. Also accepted: `Stored`, `Elsewhere`, `At home`, `Owned`.

The match is not case-sensitive. Any other `##` heading is **ignored, together with the lines under it**, and you get a warning saying so: headings are kept free for later versions of the format, and nothing is guessed into the wrong section. Everything else in a file is a container, and a container is written as a line (below), not a heading.

### The lines

```text
- [N x ]NAME[ | field: value][ | field: value]…
```

- **`N x`** is how many, a whole number. Left out, it is 1. `x` and `×` both work.
- **`NAME`** is what you call it, as you would write it on a sheet, in any language. It becomes the item's own name. If you know exactly which catalog item it is, give a reference as well (below), or write it as a link, `[Label](reference)`, which is the same pack-list shape [ADR 0145](../adr/0145-pack-contents-in-the-description.md) uses.
- **Fields** come after the name, each after a `|`. All are optional. Unknown fields are ignored with a warning, so a newer file still reads in an older reader.

| Field | Meaning |
| --- | --- |
| `ref` | The one thing in the library this is: an **instance id**, an **item id**, or a **slug**. Tried in that order. |
| `item` | Written by an export: the item's id or slug, so a file can move between libraries. You will not need to write it. |
| `weight` | Weight of **one** piece, in pounds: `0.04` or `0.04 lb`. A decimal comma is fine (`0,04`). Optional. |
| `value` | Value of one piece, free text: `5 Cp`, `2 Sb`, `1000 G (material)`, `?`. Optional. |
| `kind` | A hint about what sort of thing it is (`weapon`, `ammo`, `book`, `consumable`, …). Free text. Only used to help match or sort, never required. |
| `note` | A description or anything worth keeping. Becomes the item's note. |
| `place` | Where a container is kept, when it is not on the character (`place: the inn at Pal Vaz`). Only used for containers under `## Not carried`. |

A `|` inside a name or a note is written `\|`.

### Containers

**A line with indented lines under it is a container**, and what is indented is in it. Indent with two spaces per level, up to six levels:

```markdown
## Equipped
- Backpack
  - Bag of Holding
    - Goodiebag
      - Mini ship model
```

Rules that follow from how Lorenzo keeps things:

- A container line has no count (it is one). To have two backpacks, write two lines.
- **A stack needs a container.** `98 x Crossbow bolts` has to be inside something: a quiver, a pouch, a backpack. A count above 1 at the top of a section is reported as a problem, and nothing is guessed. (The same rule is why a pack's list nests its stacks.)
- A section lists top-level things: what is in the hand or on the body under `Equipped`, and what is owned but elsewhere under `Not carried`. A container itself can be listed in either.
- A container that is somewhere else, such as a chest at an inn, is simply a container under `## Not carried` with a `place:`.

### Creatures and anything else

Everything in Lorenzo is an entity, so a skeleton, a pet, a trophy skull or a spell scroll is a line like any other. In v1 it is made as an item instance; making it a being instead is something to do afterwards.

## What happens when it is imported

Each line is matched to the library's items, in this order, and the first hit wins. Everything is compared without case and without surrounding spaces:

1. `ref` as an **instance id** of this character's own item
2. `ref` as an **item id**
3. `ref` as a **slug**
4. the name as an **exact title**
5. the name after a **preprocessing step** (a table of known translations and spellings the importer keeps, so `Seil` can find `Rope`)
6. nothing found: it becomes an **unsorted item**

An unsorted item is a placeholder: it keeps your name, note, weight, value and kind, and shows a badge on the board. Your GM sees all of them in one list and either points each at a real catalog item or makes one for it. You are told when that happens: each item appears in your list of changes, and you get one notification saying that items were sorted. Nothing is lost by importing something the catalog does not know.

A file holds at most **1024 item lines** (the list lines, each starting with a dash).

Two things to know:

- **What you may use is what you may see.** A player matches against the public catalog; a GM matches against everything. A line that finds nothing visible to you becomes an unsorted item, not an error.
- **Import only creates.** It refuses a character that already has things, unless you pass `--add`. With `--add`, a line whose `ref` is the id of one of the character's own existing items does not make a copy: it moves that item to where the file puts it. This is how an export, edited and read back in, works.

Weight, value, kind and place are kept as a note on the item, so a GM sorting it later has them in front of them.

## The JSON form

The same file as JSON, for scripts. `lorenzo inventory export --json` writes it, and import reads it (detected by a leading `{`).

```json
{
  "format": "lorenzo-inventory/1",
  "owner": "Mira",
  "equipped": [
    {
      "name": "Backpack",
      "contents": [
        { "name": "Rations", "quantity": 9 },
        { "name": "Waterskin", "note": "filled with water" }
      ]
    }
  ],
  "not_carried": [
    {
      "name": "Chest",
      "place": "the inn at Pal Vaz",
      "contents": [{ "name": "Spare cloak" }]
    }
  ]
}
```

An item has `name` (required), `quantity` (default 1), `ref`, `item`, `weight` (a number, pounds), `value`, `kind`, `note`, `place`, and `contents` (a list of items, which makes it a container). Unknown keys are ignored. A script that writes this and a person who writes the Markdown form are producing the same thing.

## Examples

### From a spreadsheet

A sheet with the columns *Name, Count, Weight, Value, Container, Type, Description* (one row per stack, containers on their own sheet, "holding" for what is in the hand) becomes:

```markdown
format: lorenzo-inventory/1
owner: Mira

## Equipped
- Leather armor +2 | weight: 5 | value: 17 G | kind: armor | note: special, resistance to piercing damage
- Shield | weight: 3 | value: 10 G | kind: armor
- 3 x Dagger | weight: 0.5 | value: 2 G | kind: weapon
- Backpack | weight: 2.5 | value: 2 G
  - Rations | weight: 1 | value: 5 Sb | note: good until the 12th
  - Waterskin | weight: 2.5 | value: 2 Sb | note: filled with water
  - Bag of Holding | value: 2000 G
    - Goodiebag | weight: 0.2 | value: 1 G
      - Mini ship model | weight: 1 | value: 60 G | note: of the ship being built in Cuca
    - 10 x Torches | weight: 0.1 | value: 1 Cp
    - Bedroll | weight: 3 | value: 1 G
    - Clockwork goldfish | weight: 0.2 | value: 75 G | note: a glass filled with water in which a clockwork goldfish swims
    - Scroll of conjure demons | value: 360 G | kind: magical consumable | note: summons lesser demons; activate by dripping blood on the scroll
  - Quiver
    - 22 x Crossbow bolts | weight: 0.04 | value: 5 Cp | kind: ammo

## Not carried
- Chest | place: Pal Vaz
```

Things the sheet did that a file does not need: a *Total weight* column (Lorenzo adds weights up itself), a separate list of containers, container names typed again on each row (nesting says it once), and a count of 0 or a blank row. A typo in a container name (`backpack` / `Backpack` / `Mariner Bag` / `Marinner Bag`) is exactly what indenting avoids: a line is *inside* something, it is not *named after* it.

### From a list in a document

A LaTeX or word-processor list with free-text lines:

```text
\item 4 Dagger
\item 98 Crossbow Bolts
\item 20x20 Holzfaellerparzelle (5g pro Woche)
\item Pearl (100g)
```

becomes

```markdown
- 4 x Dagger
- Quiver
  - 98 x Crossbow bolts
- 20x20 lumberjack plot | note: 5 g per week
- Pearl | value: 100 G
```

where the quiver had to be written in, because a stack of 98 needs something to be in. A number that is not a count (`20x20`, `0.5m³`, `8.5 barrels`) goes in the name or the note, never in front of `x`.

## Converters

Turning a spreadsheet or a document into this format is a conversion step, not part of Lorenzo itself, and `lorenzo inventory import` only ever reads this format. Converters are planned, first for CSV and then for LaTeX lists, and will be published when ready. If you want to write one yourself, this page is the specification, and the examples above are a test you can check yours against.

## Versions

`format: lorenzo-inventory/1` is version 1. Later versions add fields and sections; they will not change what a v1 file means. A reader that meets a version it does not know says so and stops.
