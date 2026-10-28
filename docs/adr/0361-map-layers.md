# 0361 - Map layers: pictures under a Map

Status: accepted with the maintainer on 2026-10-28; RFC 0048 slice 9. Adds `map_layer` to
[ADR 0336](0336-maps-the-kind-its-system-and-its-placements.md); pictures are those of
[ADR 0360](0360-pictures-a-stored-fingerprint-svg-and-when-to-leave-postgres.md). A layer is what a
Map is drawn over, never a placement and never where anything is.

## Decision

```sql
map_layer(map_entity_id, position smallint, information_id,
  calibration jsonb NULL, opacity real NULL, reviewed_sha256 bytea NULL,
  PRIMARY KEY (tenant_id, map_entity_id, position))
```

Same-tenant foreign keys to `map` and to `information`, both `ON DELETE CASCADE` (deleting the
Information that holds the picture takes the layer with it); Row Level Security forced, with the
`repository_read` policy; one line in `copyable_tables.py` after `information`. A Map with no layer
rows is a pure data Map, as it was.

- **A layer is a picture of the Map's own Information.** `information_id` must be an Information of
  that Map entry, and a layer shows the **first picture payload** of it, by the payload order. An
  Information with no picture shows nothing. The audience is the Information's: a reader who cannot see
  the row is not told the layer exists, there is no gap marker, and its `position` may be missing from
  what they read.
- **At most 8 layers** a Map; a position is the layer's place in the order, 0 at the bottom. A Map that
  is a **sphere** has none (422), and turning a Map with layers into a sphere is the 409 of ADR 0357.
- **Calibration** says where the picture lies on the sheet, in a document the validator of
  `packages/map-engine` owns: `null` is *fit the sheet*, the picture drawn whole, its proportions kept,
  centred in the extent; or `{"anchors": [{"image": [fx, fy], "at": [x, y]}, ...]}` with two or three
  anchors, `image` a fraction of the picture (0 to 1, from its top left, y down) and `at` a position on
  the sheet in drawing units. Two anchors are a similarity (turn, one scale, move), three are an
  affine map; the anchors' pictures points must differ (and for three not be on a line) and their sheet
  points must differ in the same way, else a 422. Placements are stored in sheet units only, so
  replacing or recalibrating a picture never moves one.
- **Opacity** is `null` (opaque) or a number from 0 to 1.
- **Needs review.** `reviewed_sha256` is the fingerprint (ADR 0360) of the picture the layer was last
  set up for. A layer **needs review** when its picture exists and its hash is not that one: someone
  replaced the picture. Nothing else changes; the layer is still drawn.
- **Reads.** `GET /maps/{id}` returns `layers`, the visible ones in order:
  `{position, information_id, payload_id, content_type, sha256, opacity, calibration, needs_review}`,
  `payload_id`, `content_type` and `sha256` null when there is no picture. The picture itself is read
  from `GET /payloads/{payload_id}/content`.
- **Writes**, authors and GMs only. `PUT /maps/{id}/layers` replaces the whole list under `If-Match`
  with `{"layers": [{information_id, calibration, opacity, reviewed}]}` in one transaction, each
  Information checked to belong to the Map and to be visible to the writer, and answers the Map. A layer
  already there on the same Information keeps its `reviewed_sha256` unless the item says
  `"reviewed": true`; a new one takes the picture's current hash. Logged as `map.layers_set` with ids.
- **Copies.** `map_layer` is content: the release document is format 22 with `map_layers` (its v21
  reader gives none), a copy writes a layer only when its Information was copied and keeps the hash
  (the bytes are identical), and a layer whose Information was not copied is dropped with a reason.
  **Updates from a repository do not carry layers**, as they carry no Information at all.

## Validation and delivery

Engine: golden calibrations accepted and refused (counts, fractions out of range, equal anchors, three
on a line, huge coordinates). API: set, read and reorder layers, the audience (a reader without sight
of the picture reads a Map with no such layer), the information of another entry refused, the cap of 8,
a sphere refusing layers, `needs_review` after a replacement and its clearing by `reviewed`, deleting
the Information, the cascade, the copy and the v21 reader.

## Excluded

A layer from another entry's Information, picture tiles, layers on a sphere, more than three anchors, a
layer that moves with a placement, a layer inside an update from a repository, and per-layer audiences
other than the Information's.
