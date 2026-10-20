# Lorenzo Calendars

Calendar authoring and browsing for a library or repository: static Astro and plain TypeScript, the shared brand, Authgear PKCE and the typed API client. [ADR 0311](../../docs/adr/0311-calendar-documents-import-and-app.md) records this slice; [the calendar file guide](../../docs/guides/calendar-file-format.md) covers CLI import and the offline donjon converter.

## Using it

Choose a library and open a calendar and year. A year contains the authored months and festivals, weekday readings, moon phases and the recurring observances available to the reader. There is no current story date. Browsing does not create period entries. Year, month/festival and day notes are separate: broader notes do not silently apply to every day.

An author can create a calendar with ordered months/festivals, independent week advancement and simple periodic leap segments. Week and moon rules are optional expandable sections. New calendars start from an empty authored segment, without setting data. Preview validates the definition before saving. Stable segment identities survive renames and moves. The API refuses edits that invalidate existing periods or observance rules.

Definition edits carry the saved version. A concurrent change retains the draft and shows the current saved definition; the author must review it and preview again before retrying. Repository copies remain local, with upstream definition changes using the existing explicit update review. Calendar rules do not follow prototype graphs.

Opening a date offers Information on that one period, a new Fact or Event, an association to an existing Fact/Event, or a recurring observance. Explicit authoring materializes only the required period and its structural parents. Events and Facts remain separate kinds; date associations establish neither causal nor lived order. A recurring observance keeps a rule, skips absent dates and never pre-creates its occurrences. Existing source and target visibility remain required for date associations.

The entry page reuses the shared text/image bundle editor, LorenzoScript, authorship and independent audience controls. An entry's existence/name gate and each Information audience are separate; a visible event need not expose its private Information. Missing and hidden LorenzoScript links both remain plain text. External images embedded in text are not fetched; authored image payloads use the authenticated file loader. Names, link names, observance rules and existing date associations can be edited here. Fact About relations are shown independently of date associations and LorenzoScript links.

Import is through `lorenzo calendar import`; this app has no import UI. Event creation and date association are two API writes. A failed association keeps the form and identifies the created entry so it can be completed without deliberately making another event. Expanded clocks, calendar placement/inheritance, today, learning history, causal order, time travel and Bench integration remain later work.

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

The Authgear client and Cloudflare Pages project still require setup; no hosting is provisioned by this change. Follow [calendars-setup.md](../../docs/operations/calendars-setup.md). Other app addresses come from `GET /app-links`; the API's optional `CALENDARS_URL` overrides the planned Pages address.
