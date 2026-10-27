# 0352 - The look of a Map: themes, a theme name and the legend

Status: accepted with the maintainer on 2026-10-27; RFC 0048 slice 6. Follows the theme boundary of
[ADR 0339](0339-the-map-renderer.md): data says what things are and where, a theme turns that into a
picture.

## Decision

**Themes are code in `packages/map-renderer`**, as ADR 0339 says. This slice adds the second one,
`plain`: a black-and-white schematic with no fills, no relief arcs and no icons. Areas are outlines,
lines are strokes, a place is a small solid dot with its name, a person a small ring with its initials,
and a role is told from another by weight and pattern only (water double, routes dashed, boundaries
dotted, the rest solid). It uses the brand's tokens and nothing else. The list of names is a constant
of the renderer (`THEME_NAMES`: `default`, `plain`) and of the validator (`packages/map-engine`), with
one golden file both tests read, so the two cannot drift.

**A Map carries at most a theme name**: `map.theme_hint`, text, null or one of those names, at most 32
characters. A name this version does not know is read as the default and kept as it is, so a Map made
by a newer version round-trips. The API accepts it on `POST /maps` and `PUT /maps/{id}` (which replaces
`system`, `subject_entity_id` and `theme_hint` together, under `If-Match`; an unknown name on write is
a 422) and returns it in the header. Repository copy and update carry it with the Map: the release
document is format 19, and a copy keeps an unknown name unchanged (it only draws as the default).
Nothing in it grants, hides or measures anything.

**Precedence.** The viewer's local choice, then the Map's name, then the default. The viewer's choice is
one appearance preference of the app ("Look": the Map's own, Default or Plain), remembered in the
browser with the other appearance preference and never sent to the server (ADR 0325, RFC 0048 "no
per-viewer server storage").

**The legend is furniture, not data.** `legend(model, theme)` is a pure function of the renderer: for
each role that appears in the Map (and one line for placements with no role), the role in words and a
small swatch drawn by the theme itself, as a Scene of its own that the same painter draws. It reads no
placement beyond its role and geometry kind, never a name, so a hidden entry cannot reach it; a Map
with nothing drawn has an empty legend. The app shows it in a collapsible section and it follows the
theme and the toggles' groups.

**`setTheme`.** A view takes another theme without losing its zoom, centre or selection.

## Validation and delivery

Renderer: Scene snapshots for the second theme per shape and role; every theme names the same
classes in the stylesheet and passes the CSS guard; the legend of a model (roles, order, swatches,
empty); the golden names file. API: `theme_hint` on create and replace, an unknown name refused, the
header, the repository round trip and the old release format read. App: the precedence, the choice
remembered, the legend for a player and for a writer, light and dark with axe.

## Excluded

More themes, a per-library theme table, a theme chosen by a role, scale bar and compass (furniture for
a later theme), and a theme that carries data.
