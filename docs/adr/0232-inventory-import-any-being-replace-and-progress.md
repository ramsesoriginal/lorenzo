# 0232 - `lorenzo inventory import`: any being for a GM, `--replace`, and a progress display

Status: proposed. The three changes were asked for by the maintainer on 2026-10-09; the choices under each are the author's, for review in the pull request.

Amends [ADR 0190](0190-lorenzo-item-and-character-commands.md) (who `--owner` can name) and [ADR 0193](0193-lorenzo-inventory-import-and-export.md) (what an import does and shows). No API change: every route used already exists.

## Context

The first real use of `lorenzo inventory import` was a GM bringing in a character from D&D Beyond ([`lorenzo-beyond`](https://github.com/ramsesoriginal/lorenzo-beyond)). Three things got in the way.

- **A GM cannot name a being by name.** `--owner` finds the caller's *own* characters by name and passes a bare id through for the API to judge ([ADR 0190](0190-lorenzo-item-and-character-commands.md)). A GM who runs a table's NPCs and its players' characters has to look every id up first, though the API already lets them list those beings ([ADR 0078](0078-being-listing-and-search-endpoint.md), [0173](0173-a-gm-lists-the-beings-they-can-see.md)) and act for them ([ADR 0124](0124-groups-own-things-and-moving-is-not-giving.md), [0151](0151-a-being-in-no-campaign-and-who-stands-in-for-its-gm.md), [0152](0152-a-gm-sees-every-being-in-no-campaign.md)).
- **Import only adds.** A being that already has things is refused unless `--add`, and `--add` never removes. Bringing in a corrected sheet over an earlier import means deleting the old things by hand first.
- **A long import is silent.** Each line is a few calls, so a few hundred lines take about a minute ([ADR 0193](0193-lorenzo-inventory-import-and-export.md)), with nothing on screen until the end.

## Decision

### Any being, for whoever the API lets list it

`resolve_owner` ([ADR 0190](0190-lorenzo-item-and-character-commands.md)) looks for a name in this order: the caller's own characters, then `GET /tenants/{id}/beings?q=` (every being for an administrator, the beings in their reach for a GM, a `404` for anyone else, which is read as "none here"). An exact name, without regard to case, picks one; two with the same name are listed with their ids and nothing is guessed. An id still passes through for the API to judge. Because the rule is one function, it applies to `inventory import` and `export` and to `item add` alike, and the API stays the only judge of what may then be done.

A player sees no change: the lookup finds nothing for them and the message they got before is the one they get.

### `--replace`

`lorenzo inventory import FILE --replace` deletes what the being owns, then makes what the file lists.

- **It is an alternative to `--add`**, not a companion: naming both is an error (exit 2). Without either, a being with things is still refused, and the message now names both.
- **What is deleted** is what the being *owns*, as `owned-by` lists it and as `export` writes it. Things the being only carries (another owner's) are not touched. Instances are deleted deepest first, so a container is deleted empty; what was in a container but belongs to someone else is moved out by the API, as for any delete ([ADR 0128](0128-capacity-and-moving-anyway.md), [0132](0132-setting-things-down.md)).
- **Nothing matches an old instance.** A line's `ref` that is the id of an instance being deleted cannot move it, so in replace mode instance ids are not matched; the line falls to its item id, slug, title or spelling like any other. An export edited and read back with `--replace` therefore rebuilds the being, with new instances and the notes the file carries.
- **Plan first, and everything before the first delete.** The file is parsed and every line matched before anything is touched, so a file that cannot be made as written deletes nothing. The summary says how many things will be deleted, in the same breath as how many will be made, and the confirmation asks for both ("Delete 41 and make 38?"). `--yes` skips the question; with nobody to ask and no `--yes` it refuses, as before. `--dry-run` says both and does neither.
- **A failure stops it before it makes anything.** Each delete is a call and the API's refusals are reported by name; if any delete fails, nothing is made, the exit status is 1, and running the command again deletes the rest and then makes. A being half-emptied is a worse outcome than one left as it was, and the second run is the same command.
- **A backup is opt-in**: `--backup FILE` writes what is about to go as a ledger first (the output of `export`), so a replace can be taken back with `import`. It is not on by default: a command that writes a file the person did not name is a surprise, and for the usual case (a sheet re-imported over its own earlier import) the source is the backup. The README says to use it for a player's character.
- **Deleting is the API's act, so the API's rules apply** (the owner or a GM may delete, [ADR 0124](0124-groups-own-things-and-moving-is-not-giving.md)), and each delete is recorded in the activity log and the owner's change feed like any other.

### Progress

While an import writes, a Rich progress bar on standard error shows the steps done of all (deletes, then makes), the line being worked on, and the time. Nothing changes where output is not a terminal: no animation, the same final summary, and `--yes` runs stay scriptable. `--dry-run` prints what would be made as a tree (containers with their contents, each line marked with how it matched: by id, slug, title, another spelling, or unsorted), which is also how a person checks a long file before writing it.

## Not in scope

- **An undo.** `--backup` and `import` are the way back.
- **A bulk delete route.** Each delete is one call, as each create is ([ADR 0193](0193-lorenzo-inventory-import-and-export.md)); a few hundred is a minute.
- **Replacing only a part** (a container, a section). A file is one being's whole inventory.
- **Any API change**, including a way for a GM to list beings they cannot reach.

## Consequences

- A GM can import into an NPC or a player's character by its name, and re-import a corrected sheet in one command.
- `--replace` is destructive, and the ways it is guarded are a plan that deletes nothing until the file is known good, a count in the question, `--dry-run`, and `--backup`. A script that passes `--replace --yes` has chosen it.
- `item add` and `export` can name any being a GM can list, which they could not before; the API still decides what is then allowed.
- One more call per name that is not the caller's own, from a GM or administrator (the beings lookup); players make none.
