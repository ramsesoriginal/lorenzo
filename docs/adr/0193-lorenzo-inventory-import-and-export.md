# 0193 - `lorenzo inventory import` and `export`

Status: accepted, decided with the maintainer on 2026-10-06. Amended by [ADR 0226](0226-lorenzoledger.md): the file is a LorenzoLedger, and an import writes and an export reads a “Description” note.

Slice 3 of [RFC 0035](../rfcs/0035-inventory-files-and-placeholder-items.md): the commands that read and write the [inventory file](0191-inventory-file-format-v1.md), over what the API already does and the placeholder of [ADR 0192](0192-the-placeholder-item-the-api-and-the-seed.md). No API change.

## Context

[ADR 0190](0190-lorenzo-item-and-character-commands.md) gave a player `item add`, written as groundwork for importing a whole inventory. The format is fixed ([ADR 0191](0191-inventory-file-format-v1.md)) and what the catalog does not know has somewhere to go ([ADR 0192](0192-the-placeholder-item-the-api-and-the-seed.md)). This is the part that reads a file and makes it.

## Decision

### `lorenzo inventory import FILE`

`FILE` is Markdown or JSON (told apart by a leading `{`), or `-` for standard input. Options: `--tenant`, `--owner` (a character's id or name, which beats the file's `owner:`; the caller's only character when neither says), `--add`, `--dry-run`, `--yes`, `--preprocess TABLE`.

**Plan, then apply**, as the importer does ([RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md)). The plan is worked out before anything is written, and says what each line becomes and what it cannot become:

- **A problem stops everything**, and nothing is written: a line that cannot be made as written (a loose stack, a container that is more than one, a file for another library, more than 1024 item lines, an owner it cannot find among your characters, an unknown format version). Each is reported with its line number. **Warnings do not stop it**: an unknown field, a weight that is not pounds, a heading that is ignored, a title that names several items.
- **`--dry-run` makes nothing** and prints the plan: how many lines, how many matched and how (by id, slug, title, another spelling), which are unsorted. Without it the plan is shown and the person is asked (`--yes` skips that; with no one to ask and no `--yes` it refuses).
- **Create-only.** A character who already has things is refused unless `--add`. With `--add`, a line whose `ref` or `item` is the id of the owner's own instance **moves** that instance (into the hands, into its container, or out of every container for *Not carried*); nothing else about it is touched, and its notes are not written again.

### How a line is made

Matched as [RFC 0035 §3](../rfcs/0035-inventory-files-and-placeholder-items.md#3-how-a-line-finds-its-item): the owner's own instance id, an item id, a slug, the name as an exact title, the name through the preprocessing tables, else the `unsorted` item. Compared without case and without surrounding spaces, against what the caller may see: a player's catalog is the public one.

- A title that names **several** items is not guessed: the line becomes unsorted, with a warning.
- **Preprocessing** is `preprocess.toml`, shipped with the CLI and meant to grow: a table of whole names (each one title or a list tried in order) and of words, written for the two inventories that shaped this (German gear names, typos, and the SRD's spellings such as “Rope, hempen (50 feet)”), plus brackets, lengths and `$math$` stripped and a plural made singular. Homebrew, creatures and one-offs are left out on purpose: they stay unsorted. `--preprocess` adds a table of one's own on top. It runs only when nothing matched, and a spelling counts only if it then names exactly one item.
- **Each line is one `POST .../item-instances`**, owned by the character and named as the file names it (the player's name is the instance's, whatever it was matched to), in its container (a stack's count with it) or in none. A line that is in the hands is then **picked up**, `PUT .../container` to the owner, since creating straight into the hands is a manager's act ([ADR 0186](0186-player-self-service-enforcement.md)).
- **Notes**: a line's `note` is written as a private note titled "Note", and its weight, value, kind and place as one titled "Details" (`Weight: 0.04 lb`, one fact a line). **Each is then told to the owner's character** (`PUT .../information/{id}/knowers/{character}`), which is how a player reads what they wrote ([ADR 0192](0192-the-placeholder-item-the-api-and-the-seed.md)); the GM reaches it as they reach any note.
- **No `unsorted` item in the library**: if any line needs it, import stops and says what the GM runs (`lorenzo seed --layer core`).

**A line that fails** (the API refuses it: a capacity, the self-service switch) does not stop the rest. It is reported, what was to go inside it is skipped, and the exit status is 1. What was made stays made.

### `lorenzo inventory export`

Writes what the character **owns**, from `owned-by`, as the file: *Equipped* is what is directly in the hands, *Not carried* what is in no container, everything else nested in its container. Each line carries the instance's id in `ref` and its item's id in `item`, its name and count, and its "Note" and "Details" read back into `note`, `weight`, `value`, `kind` and `place`. So `export`, edited, then `import --add`, is how a character is rearranged. `--json` writes the JSON form, `-o` a file. A thing inside a container the character does not own is listed under *Not carried* with a `place:` saying where.

## Not in scope

- **A change that is not a move.** `--add` never renames, edits a note or deletes. Sync is a different command, if it is ever wanted.
- **Converters** (CSV, LaTeX): slice 6, separate from this command, which reads only this format.
- **The GM's way to import for someone else's character** beyond what the API already allows: a GM names the character by id with `--owner`, and the API judges.
- **A bulk route**: each line is a few calls. An inventory of a few hundred lines is a minute, which has been fine.

## Consequences

- A player can bring a whole inventory in with one command, and nothing is lost for the catalog not knowing it.
- The cost of a placeholder is only the two extra calls that make its notes readable, which a client has to know about (the board's "Not in the list" does the same, slice 4).
- The importer has no fuzzy matching and never guesses: what it cannot place goes to a GM, who can.
- The export's ids make the file a snapshot: re-importing it into another library finds nothing by id, and falls back to titles.
