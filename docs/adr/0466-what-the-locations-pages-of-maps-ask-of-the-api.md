# 0466 - What the Locations pages of Maps ask of the API

Status: accepted, built in the same stack as [ADR 0465](0465-maps-moves-into-the-web-shell.md) (issue #1214). Three reads the design of the Locations pages ([docs/design/web/maps](../design/web/maps/README.md), screens 03 to 05) shows and the API did not give. All three are additive, change nothing stored, and say nothing about what the reader may not see.

## Decision

- **A Location says on how many Maps it is drawn.** `map_count` is on the rows of `GET /locations` (also with `root=true`), of `GET /locations/{id}/parts` and on `GET /locations/{id}`. It counts the Maps the reader may see that hold a placement of that Location; a Map they may not see is not counted, so two readers of one library can read two numbers and neither learns of the other's. It is absent elsewhere a Location is named as a stub.
- **The Maps an entry is drawn on are a filter of the Maps list.** `GET /maps?placed={entry_id}` lists the Maps the reader may see that hold a placement of the entry, in the list's own order and pages, with its date lens as before. An entry the reader may not see and one that does not exist are the same 404, as for whereabouts, so the filter cannot be used to find out that a hidden entry is drawn somewhere.
- **A Location says where each character would say it is.** `GET /locations/{id}/whereabouts` is a page, by character name, of `{character, state, place?}`: the answer of [ADR 0334](0334-whereabouts-the-players-read.md) for that Location, for each character the reader may ask for. A reader who reaches everything is given every character the library holds that they may see; any other reader the characters they own and the ones their campaigns' GMs reach (the reach of [ADR 0040](0040-item-instance-read-visibility.md)'s item filter, which is what `?relative_to=` already checks). A hidden Location and a missing one are the same 404.

## Consequences

- No table, no migration. A count is one grouped read of `map_placement` with the Map visibility clause, per page.
- The generated clients (`packages/api-client`, `apps/cli`) change by the new fields and the two reads.
- Maps draws them: "1 Map" on a row of the Locations tree, "On these Maps" and "Where is…" on a Location's page.
