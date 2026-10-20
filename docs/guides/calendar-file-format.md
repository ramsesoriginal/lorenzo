# Native calendar files

A `lorenzo.calendar-document/1` JSON document carries an authored calendar definition and
explicitly dated annotations ([ADR 0311](../adr/0311-calendar-documents-import-and-app.md)).
It is independent of LorenzoLedger. The shared validator lives in
`packages/calendar-engine/src/lorenzo_calendar/document.py`.

```json
{
  "format": "lorenzo.calendar-document/1",
  "source_key": "isles",
  "name": "Isles",
  "definition": {
    "format": "lorenzo.calendar/1",
    "segments": [{"key": "spring", "name": "Spring", "days": 27}]
  },
  "annotations": [{
    "key": "note-3286-1-16",
    "date": {"year": 3286, "segment": "spring", "day": 16},
    "text": "The harbour opens.",
    "original_text": "The harbour opens.",
    "classification": "note"
  }]
}
```

`source_key` identifies this source in a receiving library; keep it stable on reimport.
Annotation keys are stable source identities, independent of edited text. A date names one
actual day in this definition. There is no universal clock, current date or historical claim.

Each annotation has one classification:

- `note`: ordinary Information on that day period; no Information/date join.
- `fact`: an independent canonical Fact entry associated with the period.
- `event`: a minimal Event associated with the period. An optional `group` key explicitly
  groups several annotations into one Event; grouped annotations share `title` and audience.
- `observance`: an independent recurring observance, with an explicit `recurrence` rule
  (`segment`, `day`, and optional `when: {"every": 1, "offset": 0}`). Missing dates skip.

`title` is optional. `text` is the authored content; `original_text` preserves its source.
Changing classification or grouping is an explicit import choice. A recurring observance is
not evidence that any particular celebration occurred. Fact About and LorenzoScript links
stay independent. Names/initials in imported text are never parsed as participants.

`source` holds original metadata/exports as JSON. `warnings` holds unique `{key, message}`
records for review. The converter's structure and anchor warnings require deliberate review
before applying an import. Credentials do not belong in a calendar file.

Audiences default to restricted: `is_public` on the document controls the calendar's outer
existence/name gate; `period_is_public` controls newly materialized periods; an annotation's
`is_public` controls its Fact/Event/observance outer gate, and `information_is_public` its
Information. Public Information never opens an outer gate. Explicit grants remain separately
editable through ordinary audience controls.

A file permits at most 1,000 annotations and 2 MB of UTF-8 JSON, including source metadata.
Unknown formats, unknown fields, duplicate keys/identities, invalid dates and unresolved
recurrence/grouping combinations are refused. Calendar definitions retain their separate
versioned schema, stable segment keys and bounds from ADR 0308.
