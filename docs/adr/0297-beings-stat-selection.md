# 0297 - Beings shows the being group and valued stats

Status: accepted, scoped with the maintainer on 2026-10-15.

## Context

The tenant can designate its being stat group ([ADR 0296](0296-being-stat-group.md)). Beings currently shows valued stats in Read and Play and the entire vocabulary in Edit ([ADR 0283](0283-beings-sheet-play-stats-and-undo.md)). Libraries with weapon and other vocabularies get unrelated empty fields in Edit, while their primary being stats disappear from Read when unset.

The maintainer chose all stats in the being group, plus any other stat with a value.

## Decision

- The stat band in both Sheet and Datasheet, in Read, Play and Edit, shows the union of the tenant's being group and the being's effective stat values. A stat outside that group is shown when it has an own, inherited or calculated value. Zero and empty text are values. The existing vocabulary order, hints, provenance and controls remain.
- An unset stat in the being group is shown with a dash in Read and Play and with its existing field in Edit. With no being group selected, only valued stats are shown. Clearing the last value outside the selected group removes that row on the next redraw.
- Read the selection from tenant detail alongside the vocabulary. Keep the complete vocabulary for resolving hints and drawing weapons; selection changes only the being's stat band. The sticky bar uses the resulting band. If tenant detail cannot be read, fall back to valued stats.
- Boolean stats retain their existing tag presentation and controls; the selection applies to the numeric, text and enum band. No new tag behavior, stat picker or mode switch is introduced.
- There is no API change, campaign override, setting editor or stat write change. This is the first frontend use of ADR 0296's tenant setting.

## Consequences

A library's primary stat line is present even before its values are filled, while other groups appear only where the being uses them. To start an otherwise empty stat outside that group, author its value through the existing API, CLI or Bench. Edit no longer lists the whole library vocabulary.
