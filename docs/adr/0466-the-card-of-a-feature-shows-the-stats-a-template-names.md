# 0466 - The card of a feature shows the stats a template names

Status: accepted, built (2026-11-16). Slice G2 of the follow-ups tracked in #1229. Takes up what
[RFC 0054](../rfcs/0054-features-grants-and-choices.md) section 8 says of a feature's link preview ("its description and a few stats")
and [ADR 0457](0457-the-features-slot-of-a-template.md) left out ("the stats a library gives its features are its own names, which the
card does not know"). Builds on [ADR 0264](0264-link-previews.md) (the card) and [ADR 0451](0451-templates-a-sheet-as-data.md)
(templates).

## Context

The card of an item names the stats it shows in code (`damage`, `armor`, `weight`...), because an item's vocabulary is shared. A
feature's is not: one library's spells have `damage` and `range`, another's boons have a `cost`. The card cannot know the names, so
it showed none, and the library had no way to say.

## Decision

- **A template says it.** The card of an entry of the kind `feature` or `feature_instance` shows the stats of the first template of the
  library, by name then id, whose filter matches the entry (its kind, and its ancestor when it names one, as `matching-templates` has
  it) and that has a `stats` slot: those of that template's first `stats` slot, in the slot's order (a slot of a group: the entry's
  stats of the group, in the entry's own order, less what the slot leaves out), named as the slot labels them (the stat's own name when
  it does not), the ones the entry has a value for, at most four. A tag is not on a card, as on any card.
- **A template for the kind `feature` does not cover an instance, nor the other way round**, so a library can show an instance's own
  state (uses left) where its feature shows what it does; an instance reads what its feature gives through its prototype like any
  entry.
- **Nothing else changes.** No template, no stats, as before; the card of any other kind is the one its kind has, whatever templates
  the library makes (an item's card is not redrawn by a template for items). A template hidden by an ancestor the caller may not see
  is not used.
- **The card loads the markers.** The route did not load what makes an entry a feature or an instance, so it read neither as one (its
  `kinds` left them out and its template was the fallback); it now loads both, so `kinds` says `feature` and `template` says `feature`.

## Design

`card_stats` in `routers/templates.py` reads the templates with their slots (`_SLOT_LOAD`), applies the template filter of `_matches`,
and picks the slot as the template view (`get_entry_template`) does; the link preview route calls it for the two kinds and keeps
`pick_stats` for the rest. A fixed number of statements, whatever the library holds: the templates with their slots, and the entry's ancestors only when there is a template; a library with none pays one query, and only for a feature.

## Validation and delivery

Tests: no template, no stats; a template naming them, in order, labelled, skipping a missing value; an instance with a template for
instances and one for features not covering it; a group slot with an exclusion and a tag left out; the first by name among several, one
without a stats slot passed over, one for another kind ignored, four at most; an item's card unchanged by a template for items. The
OpenAPI change is none.

## Not in scope

Templates drawing the cards of other kinds (their code templates stay, ADR 0264), a per-library cut of the number of stats, units on the
card, and choosing among templates that all match (the first by name wins here, since a card has to be one).

## Consequences

- A library gives its spells and boons a card by making the template it may already have for their sheet.
- The card of a feature says it is one (`kinds`, `template`) now that the markers are read.
