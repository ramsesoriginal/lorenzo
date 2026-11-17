# Writing source archive

Writing's **Download LorenzoScript** produces a ZIP for one authorized, saved composition
([ADR 0478](../adr/0478-manuscript-export-snapshots.md)). It is source for an author to retain or
process, not a library backup and not an import contract.

`manifest.json` is UTF-8 JSON. `format` is `lorenzo-writing/1`; `root_id` identifies the selected
entry and `version` identifies this content snapshot. `entries` and `payloads` are identity maps
represented as arrays. Their array order is not reading order: start at `root_id` and follow each
entry's ordered `elements`.

| Element kind | Reading |
| --- | --- |
| `payload` | Include the payload with this `id` |
| `chapter`, `scene_telling` | Read the entry with this `id`, recursively |
| `coverage` | Read `target_id`; if `payload_id` is set, include only that payload |

A coverage element has its own stable `id`. Multiple references intentionally repeat the same
entry or payload in the reading; the ZIP stores each payload only once. An exported partial target
contains only selected elements unless another reference selects the complete target. A shared
telling has `uses_scene_manuscript: true` and reuses its permitted payload IDs. World identities
outside the selected graph are omitted. A joined source retains its guarded `joined_destination`
reference without implicitly including that destination's text.

Each payload records `id`, `information_id`, `kind`, `sha256` and a generated `path`.
Text paths are `text/<UUID>.lorenzoscript`: exact UTF-8 encoding of the stored source, including
line endings and any authored BOM. `locale` retains the source locale. Picture paths are
`pictures/<UUID>.<extension>`: unchanged original bytes with `media_type`. Hashes cover those
file bytes. Unknown image extensions use `.bin`; `media_type` remains authoritative.

Entries retain names, kinds, ordered elements, available numbering/contents settings and their
reader-scoped presentation. `number` is the displayed Chapter number; `contents` contains ordered
`id`, `label`, `depth` rows. Null settings mean no explicit settings row. Generated numbering and
contents are not inserted into the authored source files. Footnotes and LorenzoScript headings
remain local to their text payload; a rendering should scope their DOM IDs per occurrence.

No notes, history, grants, personal goals, unsent browser drafts or inaccessible content are
included. File names use UUIDs, never authored titles. `README.txt` identifies the format and
its limits. The JSON preview embeds text and base64 picture bytes; the ZIP replaces those fields
with file paths. Both use the same version and authorization checks.
