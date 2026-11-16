# 0473 - The Height line tool

Status: accepted, decided with the maintainer on 2026-11-16. Part of [RFC 0050](../rfcs/0050-the-web-interface.md) (slice UI-E, Maps); follows [ADR 0421](0421-maps-redesign.md) and [ADR 0465](0465-maps-moves-into-the-web-shell.md), which ask for an ADR per planned tool. Tracked in [#1210](https://github.com/ramsesoriginal/lorenzo/issues/1210).

## Decision

- **The tool.** Height line (group Terrain, key T): drawn as Line is, with two options, **Height** (a number) and **Unit** (the author's own words, at most 32 characters). Both must be given before the line can be finished, and neither has a first value: a Map's scale says what a unit of the sheet is, never what a height is, and nothing is invented. The pair last used on a Map is remembered in this browser and offered the next time. Not on a sphere.
- **Its output is a line with a value:** one entry for each line, one placement of one `polyline` part that carries `value` and `unit` ([ADR 0337](0337-geometry-roles-and-the-validator.md)), with the role `isoline` already chosen. It is the second role a tool chooses, after a pin's `site` ([ADR 0353](0353-authoring-a-map-in-lorenzo-maps.md)), and can be changed in the panel.
- **The editor keeps and edits a value.** A part's value and unit are kept by every edit of its points, and a placement of one part that carries them shows them as two fields in the panel. Emptying both takes the value away; one without the other is refused, as the API refuses it.
- **The renderer says the value.** A line or curve part that carries a value is labelled with it and its unit ("250 m") at its middle, in every theme, under the *Names* switch, and its accessible name ends with the height. This is the first read of a value anywhere; no distance, reach or shading reads it.
- **Adding to an entry.** Once the editor edits parts ([ADR 0474](0474-editing-the-parts-of-a-placement.md)), the tool can add its line to the selected entry whose parts are height lines, instead of making an entry.

## Validation and delivery

Unit tests: the geometry with its value and unit, that an edit keeps them, the refusal of one without the other, the label's text and place. Browser tests against the real API: a height line drawn with a height and a unit, refused without them, its label read, its value changed in the panel, a point moved without losing the value, undo and redo; axe in light and dark.

## Excluded

A Map's own height unit, shading or colour by height, reading a height at a point, and a value on a pin, a circle or an area in the editor.
