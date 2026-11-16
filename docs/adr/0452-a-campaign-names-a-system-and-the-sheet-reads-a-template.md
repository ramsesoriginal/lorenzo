# 0452 - A campaign names a game system, and the sheet reads a template

Status: accepted, built (2026-11-12). Slice Y5 of [RFC 0052](../rfcs/0052-game-systems-in-one-library.md). Builds on
[ADR 0448](0448-a-game-system-as-a-row.md) (a system), [ADR 0451](0451-templates-a-sheet-as-data.md) (templates and their filter)
and [ADR 0281](0281-sheet-settings-and-the-sheet-read.md) (the sheet read and its settings). Resolution does not change.

## Context

A campaign has a free text `game_system` that nothing reads, and the sheet read accepts a `campaign_id` that it was told to
ignore until a campaign could override the library's sheet settings ([ADR 0296](0296-being-stat-group.md)). A
table plays one system, and a library holding several needs the sheet of that table to be drawn from that system's view.

## Decision

- **`campaign.system_id`** is nullable, one of the library's game systems, in `POST /campaigns`, `PATCH /campaigns/{id}` (set,
  change, or clear with `null`) and in both campaign responses. The free text `game_system` stays as the display name; nothing
  reconciles the two. A system that is not the library's is a 422 (`invalid-system`). A system a campaign names is not deleted
  (409), like one a group or a template belongs to.
- **The sheet read draws from a template when there is one.** `GET /beings/{id}/sheet` takes `campaign_id` as before and a new
  `template_id`:
  - with `template_id`, the sheet is drawn from that template, whatever system it belongs to; one that is not the library's is a
    404, one the being does not match (ADR 0451's filter) a 409;
  - without it and with a campaign that names a system, the candidates are that system's templates whose filter matches the
    being; if exactly one does, the sheet is drawn from it;
  - otherwise (no campaign, a campaign with no system, no candidate or several) the library's own settings draw the sheet, as
    before: nothing is chosen for the caller when two match.
- **What drawing from a template means.** The three settings the sheet has stand for slots: the `being_stat_group_id` is the group
  of the template's first `stats` slot that shows a group, the weapons are the things the being holds with the columns of the
  first `held` slot (its group less what it leaves out, or its listed stats), and the abilities are the notes of the type of the
  first `information` slot. A slot the template has not leaves that section not configured (`weapons_configured` or
  `abilities_configured` false), and the library's setting does not stand in for it. What the caller may see of the weapons and
  the abilities is as it was: ADR 0040's reach and the information visibility check.
- **The response says what was used.** `template` is the summary of the template the sheet was drawn from, `null` when the
  library's settings were used, and `templates` the candidates of the campaign's system (empty without one), so a client that
  finds several can offer the choice and send `template_id`.
- **Nothing else changes.** Every existing request keeps its path, body and status; a library with no template reads as it did,
  and so does a campaign that names no system.

## Design

`campaign.system_id` is a composite key with `tenant_id` to `system` (ADR 0117), with no clearing action; the API refuses the
delete first. `pick_sheet_template` (in the templates router module) loads the candidates with their slots in one statement,
checks the filter as `matching-templates` does, and the sheet read substitutes the three settings before it runs the queries it
ran. A sheet read costs the statements it did, plus one for the campaign's system when `campaign_id` is sent, and two to three
when a campaign names a system (the candidates, the prototype walk and the kinds).

## Validation and delivery

A test for each: naming, changing and clearing a campaign's system, and the library's own; a system that is not the library's, on
create and on patch, and a system a campaign names that is not deleted until it is cleared; a sheet with no template (with and
without a campaign) that is drawn from the settings as before; the one matching template of the campaign's system that draws it
(the weapons, the abilities and the group); a template without a held or information slot; two matches, where nothing is chosen
and both are offered; `template_id` for one, for another system's, for one the being does not match and for an unknown one. The
OpenAPI change is a field on three schemas and a query parameter; the CLI models and `packages/api-client` are regenerated.

## Consequences

- A library with several systems draws each table's sheet from its own system's template, with one setting on the campaign.
- The sheet settings of the library stay for a library that has no templates; they are the fallback, not deprecated.
- Y6 carries systems and templates with a repository, so a vocabulary repository for a system brings its sheet.
