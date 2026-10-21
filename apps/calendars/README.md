# Lorenzo Calendars

Calendar authoring and browsing for a library or repository: static Astro and plain TypeScript, the shared brand, Authgear PKCE and the typed API client. [ADR 0311](../../docs/adr/0311-calendar-documents-import-and-app.md) records this slice; [the calendar file guide](../../docs/guides/calendar-file-format.md) covers CLI import and the offline donjon converter.

## Using it

Choose a library and open a calendar and year. Use the Month or festival / Whole year tabs to show one segment or every segment in definition order. Both views use the same day renderer and content cache; the whole year retains one shared four-date loading limit. The view stays selected when changing years and is included in the URL. On phones, selecting a date in the whole year opens its detail panel with a Back to calendar control. A year contains the authored months and festivals, weekday readings, moon phases and the recurring observances available to the reader. Month cells show permitted day-note snippets, dated entry names and recurring observances, with compact Unicode moon phases (names and phases on hover, in the date’s accessible description, and in the selected-day panel). Saved-day content is loaded only for displayed months, four dates at a time, and cached while switching views or months. There is no current story date. Browsing does not create period entries. Year, month/festival and day notes are separate: broader notes do not silently apply to every day.

An author can create a calendar with ordered months/festivals, independent week advancement and simple periodic leap segments. Week and moon rules are optional expandable sections. New calendars start from an empty authored segment, without setting data. Preview validates the definition before saving. Stable segment identities survive renames and moves. The API refuses edits that invalidate existing periods or observance rules.

Definition edits carry the saved version. A concurrent change retains the draft and shows the current saved definition; the author must review it and preview again before retrying. Repository copies remain local, with upstream definition changes using the existing explicit update review. Calendar rules do not follow prototype graphs.

Opening a date offers Information on that one period, a new Fact or Event, an association to an existing Fact/Event, or a recurring observance. Explicit authoring materializes only the required period and its structural parents. Events and Facts remain separate kinds; date associations establish neither causal nor lived order. A recurring observance keeps a rule, skips absent dates and never pre-creates its occurrences. Existing source and target visibility remain required for date associations.

The entry page reuses the shared text/image bundle editor, LorenzoScript, authorship and independent audience controls. An entry's existence/name gate and each Information audience are separate; a visible event need not expose its private Information. Missing and hidden LorenzoScript links both remain plain text. External images embedded in text are not fetched; authored image payloads use the authenticated file loader. Names, link names, observance rules and existing date associations can be edited here. Fact About relations are shown independently of date associations and LorenzoScript links.

Readers can open **Order and causes** on an Event they can see ([ADR 0315](../../docs/adr/0315-reader-scoped-event-order-and-sharing.md)). Their view uses explicitly shared relationships whose two Events are visible to them. Compare Events shows a permitted recorded causal chain, recorded ordering, or an explicitly linearized display order with no visible recorded path. Hidden Events and private relationships influence neither that reader's order nor its explanations, counts or pagination. Different readers may receive different linearized display orders; dates do not create assertions.

Full-visibility Owners/Organizers can also add/remove assertions and use **Share relationship** or **Make relationship private** on each relationship. Existing and newly created assertions start private. Sharing does not open either Event or its Information. Happened before and Caused on the same pair have independent sharing choices. Conflicting edits retain the selection and require refreshing saved relationships before retrying. Ordering edits remain unavailable to Authors, campaign GMs, players and administrators with an opt-out.

Import is through `lorenzo calendar import`; this app has no import UI. Event creation and date association are two API writes. A failed association keeps the form and identifies the created entry so it can be completed without deliberately making another event. Expanded clocks, calendar placement/inheritance, today, full historical knowledge and time travel remain later work.

The **Events** page creates undated Events, searches their names, and offers full-visibility
Owners/Organizers participant filters, and all readers permitted causal filters and story order ([ADR 0313](../../docs/adr/0313-event-participation-browsing-and-calendar-addresses.md)).
Causal filters follow causes in either direction from one Event; branches remain independent.
Story order derives the authorized graph before name/causal filters and pagination, and labels unconstrained positions as
linearized. Full-visibility staff retains the complete canonical graph. Event pages add/remove participating beings with version checks. Participation
records neither knowledge nor lived order and grants no visibility. Authors/readers may browse permitted Event names, shared order and shared causal relationships, but receive no structured participation surface.

Calendar, period and Event link names use the existing entry editor. Calendars URLs accept
UUIDs or slugs and prefer an entry's defined slug; internal identities stay UUIDs. An explicit
`slug` parameter handles UUID-shaped link names. Tenant links also prefer the library slug.
LorenzoScript supports `[[calendar/reckoning]]`, `[[event/arrival]]`,
`[[calendar_period/first-day]]` and computed dates such as `{{cal reckoning 3286/Quirm/16}}`
or `{{cal reckoning 3286/6/16}}`. A year or month alone works too. Numbers count every
segment in authored order, including festivals and absent leap segments. Names are matched
uniquely after Unicode normalization and case folding. Use `key:segment-6` or `name:123`
for an explicit key or a numeric name, and percent-encode `/` inside a name. Computed links
create no period and disclose no hidden period or Information. Existing apps share these
calendar links through the app registry.

In-app links keep a bounded session-memory cache and revalidate the account, library role
and Event-order capability before a protected view is drawn. Full-visibility staff can reuse
recent responses (10 seconds, at most 64 bodies / 2 MiB, with oversized bodies skipped).
Other readers deduplicate simultaneous requests but fetch private content afresh on entering
a view. Slug lookups always stay fresh; cache identities use resolved UUIDs. Writes invalidate
reads before and after the request, and late reads cannot repopulate an invalidated cache.
Sign-out, denied reads, scope changes and full-page history restores clear private state.
No private Information is stored in localStorage or available as an offline fallback.

Hovering or focusing a calendar, date or entry can prefetch its visible details. Small
calendars also prefetch the next year's first pages. Prefetch uses at most two requests at
once, eight queued and sixteen distinct intentions per view; it respects the full-visibility
check, does not change the selected date and never authors periods. Existing four-date
loading for visible month content remains in place. In-app navigation uses Astro's built-in
client router; every new page remounts behind its fresh session check.

The appearance toggle remembers an explicit light/dark choice in this browser and preserves it
through page navigation and browser history. Without a saved choice, the system appearance is
used. When preference storage is unavailable, the toggle still works throughout the visit.

## Development and checks

Use Node from the root `mise.toml` and the workspace pnpm version. Copy `.env.example` to `.env` and set this app's Authgear endpoint/client; register the slash-suffixed callback. The API must allow the local origin through CORS.

```bash
mise run //apps/calendars:dev        # http://127.0.0.1:4325
mise run //apps/calendars:lint
mise run //apps/calendars:test
mise run //apps/calendars:build
mise run //apps/calendars:test-e2e
```

Browser tests use the real API and PostgreSQL plus a fake Authgear on ports of their own: auth 4412, API 8777, site 4343. They recreate only `lorenzo_calendars_e2e` (or an explicitly supplied `E2E_DATABASE` ending in `_e2e`). Start the local Postgres from `infra/docker-compose.yml` on port 55432; overrides are `E2E_POSTGRES_URL` and `E2E_APP_POSTGRES_URL`. Chromium's headless shell must be installed (`pnpm exec playwright install chromium-headless-shell`). CI runs this suite separately and includes it in the required summary.

The browser fixtures import the supplied nineteen-segment, 387-day calendar structure with invented notes. They cover no-write browsing, explicit period and event creation, information, reader visibility, stale-definition review, phone layout and PKCE. Unit checks cover permission-filtered links and safe text rendering.

## Hosting

The app is deployed at [lorenzo-calendars.pages.dev](https://lorenzo-calendars.pages.dev/). Follow [calendars-setup.md](../../docs/operations/calendars-setup.md). Other app addresses come from `GET /app-links`; the API's optional `CALENDARS_URL` overrides the planned Pages address.

## Optional learning records

Full-visibility Owners and Organizers can open **Learning** on an Event page ([ADR 0314](../../docs/adr/0314-optional-event-learning-records.md)). Add the being as a participant first, refresh saved learning if needed, then choose the participant, find an entry and select its specific Information bundle. **Record learning** creates an explicit story association without sharing either the Information or its entry. Public Information needs no Knowledge grant for this association.

The Event lists its recorded learning. Following the being link opens its recorded learning occasions in Calendars; Information cards offer **Recorded learning** on demand. These lists are associations, not a claimed lived or causal sequence. Readers outside the full-visibility capability receive no learning controls or background reads. Conflicting writes keep the selection and require **Refresh saved learning** before retrying.

Removing a learning record corrects provenance; it does not revoke access, mean forgetting or remove participation. Remove dependent learning records before removing a participation or deleting its Information/entry. Records follow Information identity through wording edits and do not snapshot the earlier text. An empty list means no learning history is recorded, not that nobody knew. Existing audience grants and untimed workflows remain unchanged.


Sharing a relationship through an Event that is hidden from a reader does not reveal a path through that Event. To disclose only that Arrival happened before Departure, record and share that direct ordering assertion. The reader is never told a hidden intermediary exists. Participation and learning records keep their full-visibility staff restriction in this slice; viewing an Event or its shared causes grants neither of those records.
