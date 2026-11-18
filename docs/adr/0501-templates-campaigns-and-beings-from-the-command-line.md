# 0501 - Templates, campaigns and beings from the command line

Status: accepted (2026-11-17), decided with the maintainer, built (2026-11-18). Slice C7 of [RFC 0057](../rfcs/0057-the-command-line-for-game-systems.md).
Builds on [ADR 0451](0451-templates-a-sheet-as-data.md) and [ADR 0452](0452-a-campaign-names-a-system-and-the-sheet-reads-a-template.md).

_Originally numbered 0487; renumbered before merge - the Maps ADRs 0481, 0482, 0490 and 0491 reached `main` first, so the RFC 0057 block moved as a whole to 0495-0507. Same precedent as ADR 0050/0054/0068/0069/0087._

## Context

A template is a filter (a kind, an ancestor entry) and up to fifty slots (stats, information, held, tags, features); a campaign names a
system, and the sheet of a being reads the template that system picks. The CLI reads items, instances and beings without a system or a
template, and cannot create a campaign or a being, so a worked example needs the web apps or `lorenzo api`.

## Decision

- **In the document**: `[[template]]` `name`, `system`, `kind`, `ancestor` (an entry's slug) and `[[template.slot]]` `kind`, `label`, and
  per kind `group` or `stats` (`[{stat, label}]`) with `exclude`, `information_type`, `held_order`.
- **`lorenzo template list [--system S]`**, **`show NAME`** (its filter and slots, by name), **`create --from FILE`** (one `[[template]]`
  table; slots are many and nested, so they are not options), **`delete`**, **`matching ENTRY [--system S]`** (the templates an entry
  matches) and **`view ENTRY TEMPLATE`** (the entry drawn through the template, slot by slot, as the API's view returns it). A template
  is replaced whole, as the API does.
- **`lorenzo campaign list`**, **`create NAME --slug S [--system SLUG] [--description D]`** and **`set-system CAMPAIGN SLUG | --none`**.
  `game_system`, the free-text field, is filled from the system's name when one is given.
- **`lorenzo being create NAME [--parent ENTRY]... [--slug S] [--character --campaign C]`** makes a being through the entity route with
  its parents, and **`being show`** gains `--campaign`, which picks the system and its template as the sheet does, and `--template`.
- **Reads take `--system SLUG`**: `item show`, `item-instance show`, `being show` and the lists pass the API's `system` filter, so a
  library with two systems shows one at a time.

## Consequences

- The workflows of RFC 0057 (a roster, a library with two systems, an author's world) run from the command line alone.
- A being looks the way its campaign's system says, in the terminal as in the apps.

## As built (slice C7)

- `template create --from FILE` creates a template, or replaces the one of its name (the API replaces a template whole). In the
  file, and in a document, `system` is `true` for the document's own system, a slug for another, or false for none.
- `being create` makes a being with its parents and slug; `--character --campaign` is not built: making a character is a player's
  step the apps and `lorenzo api` keep.
- `being show --campaign` and `--template` pass the campaign and the template to the sheet read; `--system` on the three reads
  passes the API's `system` filter to the entry read.
