# 0311 - Calendar documents, donjon import and the calendar app

Status: accepted, decided with the maintainer on 2026-10-19. Builds on ADR 0308 to 0310.

## Context

The first user flow is a donjon export converted into a reviewed import, then viewed and edited
in its own calendar app. Bench integration is not required for this slice.

## Decision

A versioned native JSON calendar document carries the definition, stable segment/source-note
keys, dated annotations, source metadata and explicit interpretation choices. It is a separate
contract, not an extension of the inventory-specific LorenzoLedger. A pure donjon converter in
`packages/converters` reads files and writes that document without login or API access, as
ADR 0246. The CLI owns authenticated planning and import. Unknown formats and unresolved
choices are errors, never guesses. Warnings go to stderr; machine-readable output stays JSON.

The donjon mapping preserves month/week structure, fractional moon cycles and dated notes.
Donjon does not declare festival or leap semantics: the author chooses them. The selected
year is a reference, never today. Source moon phase calculations include `first_day`; map
phases against the chosen reference year and advance consistently thereafter. The maintainer's
sample uses 3286. Its 3242/3286 exports have consistent weekdays but inconsistent fixed moon
anchors; report the discrepancy, never invent a fictional jump. Original text/source values
are retained; HTML-entity cleanup is explicit and previewed. Saved celestial-event prefixes
are authored text; the generator toggle is not an exported event history. Blank notes and
repeated notes across snapshots do not become events or duplicates.

Each source note defaults to ordinary Information on its materialized period. The author can
choose a recurring observance, a canonical Fact, or a minimal Event, individually or in batches.
Grouping several annotations into one Event is explicit. The importer never infers that
initials are participants or a repeated phrase is one continuous event. Noninteractive imports
use a choices file and stop on unresolved conflicts. New entries/information remain restricted
unless an audience is explicitly chosen; copying authoring data does not create Player seats.

`lorenzo calendar import` validates/plans before applying. A bounded API operation validates
and writes a complete import atomically. Preview and apply share validation; apply rechecks
versions and standing. Stable ids and source mappings make retries/reimports idempotent.
Changed source notes, local edits and definition changes are shown as conflicts, not replaced
silently; an import receipt names added, unchanged and changed material. No API credentials
are sent to donjon and no remote source is fetched by the importer. Native JSON export enables
round trips without requiring donjon-compatible output.

`apps/calendars` is the dedicated calendar editor/viewer: static Astro and plain TypeScript,
Authgear, shared brand, generated API client and existing information-editor controls. It offers
library/repository selection, calendar listing, year/month browsing, moons/observances,
definition preview/edit, explicit period materialization, dated notes, minimal Event/date
association editing, Fact links and independent audiences. The API calculates calendars and
is authoritative for permissions. Import is CLI-only initially. Writes retain drafts on errors
and handle stale ETags explicitly. Use ordinary app forms, keyboard/touch access and phone
layouts; no new UI framework, Bench dependency or offline promise.

The new app/package get their standard mise tasks, CI dependency/schema checks, labels,
release/dependency configuration, app links and setup docs when scaffolded. Cloudflare/Authgear
provisioning is documented separately from locally testable implementation.

## Delivery and validation

Stacked implementation PRs: calendar core; periods/Events/date links; recurrence. Converter
branches from the stable format/core. CLI depends on recurrence and converter; the app depends
on recurrence and can proceed independently of CLI. Every PR owns its validation and repository
behavior. Real-API tests cover converter/import/app reload, repeat imports, classifications,
concurrency, failed-import rollback and visibility. The provided real export is used for local
acceptance; reusable committed fixtures preserve the structural edge cases with invented notes.

## Not in scope

Clocks/rates, today, placement/inheritance, causal/lived/play ordering, learning/history,
physical existence gates, epistemic confidence/verdicts and persistent offline authoring.
