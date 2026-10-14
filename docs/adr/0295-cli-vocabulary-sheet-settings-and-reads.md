# 0295 - The CLI's stat vocabulary, sheet settings and terminal entry reads

Status: accepted, scoped with the maintainer on 2026-10-15.

## Context

A library can already create stat definitions and groups, edit their display fields and hints, and choose its weapon group and ability information type (ADRs 0278, 0279, 0281). The CLI exposes them only through seed files and raw API requests. It lists items and characters but cannot read their complete entries in the terminal (ADR 0190).

## Decision

- `stat-group list|create|edit` and `stat-definition list|create|edit` take `--tenant` (id or slug, or `LORENZO_TENANT`). Vocabulary references accept ids or exact names; ambiguous names are refused with candidate ids. Create accepts the API's types, enum values, display fields and hints. Edit exposes only the fields the API permits, preserving omitted fields. Nullable fields have explicit clear options; booleans can be turned on or off. Hints remain clues, never limits.
- `tenant sheet-settings TENANT` reads the two settings; its options set or clear the weapon stat group and ability information type. A group can be named by id or name. Writes use the existing tenant update route and permissions.
- `item show`, `item-instance show` and `being show` accept ids, link names or exact names, and `--tenant`. A being read includes the sheet's equipped weapons and abilities. Reads show the entry's resolved stats in vocabulary order, their units and provenance, inheritance, containment and visible notes with authors. Item and instance reads include the existing item detail. JSON returns the unrendered response data as one document. Every read uses the caller's existing authentication and the API's visibility.
- Reuse `packages/lorenzoscript`'s zero-dependency parser and renderer as a committed deterministic JavaScript bundle, run in the already-installed embedded V8. Node and TypeScript are build tools only. A source digest test detects drift; CI declares the CLI's dependency on LorenzoScript. No second dialect or parser is introduced.
- Draw its parsed syntax tree as Rich terminal output: headings, emphasis, lists, quotes, tables, code, tasks and footnotes. Resolve stat chips against the entry's visible stats and units and entity references through the authenticated batch resolver (including `my/` with the source entry). Pictures use alternate text, math a readable textual fallback, and unmodelled calendar dates remain text. Never execute authored JavaScript, fetch external media, or print terminal control sequences from authored content.
- The API and its contracts stay unchanged. Commands keep the existing default-instance notice on writes, machine-readable JSON and concise error handling (ADR 0137).

## Not in scope

Retyping or moving definitions, editing entity values, computed-formula authoring, per-campaign sheet settings, graphical terminal images or interactive play controls.

## Consequences

The CLI can author the vocabulary used by the being sheet and read entries without switching apps. Its wheel carries a generated copy of the existing parser; changes to that package require regenerating it. Tests cover writes and clearing, permissions and ambiguity, syntax fidelity and reads against the real API.
