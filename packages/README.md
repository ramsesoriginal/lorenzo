# packages/

Code that more than one app uses, extracted into its own small package with its own README, tests and version. Generic code does not go into an `apps/*/utils` folder; see [docs/guides/adding-a-package.md](../docs/guides/adding-a-package.md) for how a package is added and [ADR 0098](../docs/adr/0098-branding-css-app-and-package.md) for the rule that a package appears when a second consumer needs it.

| Package | Language | What it is |
| --- | --- | --- |
| [`api-client`](api-client) | TypeScript | The typed client for `apps/api`, generated from its OpenAPI schema, shared by the bot and the web apps ([ADR 0122](../docs/adr/0122-api-client-package.md)) |
| [`app-shell`](app-shell) | TypeScript and Astro | The head, header, footer and page frame of Calendars and Sessions over the shared brand ([ADR 0322](../docs/adr/0322-calendars-and-sessions-share-a-header-and-the-brand-base.md)) |
| [`brand`](brand) | CSS | `apps/brand`'s tokens, fonts, layout, components and icon atlas, copied in for bundling at an app's build ([ADR 0098](../docs/adr/0098-branding-css-app-and-package.md)) |
| [`calendar-engine`](calendar-engine) | Python | Validation and calculation of authored calendars: days, years, weeks and moon phases, with no clock and no current date ([ADR 0308](../docs/adr/0308-authored-calendars-and-calculation.md)) |
| [`converters`](converters) | Python | Converters from files players already have (`lorenzo-convert sheet` for CSV and Excel; the donjon calendar converter) into Lorenzo's own documents, never touching the API ([ADR 0246](../docs/adr/0246-lorenzo-converters-the-spreadsheet-converter.md), [ADR 0311](../docs/adr/0311-calendar-documents-import-and-app.md)) |
| [`information-editor`](information-editor) | TypeScript | Framework-free controls for notes and descriptions: audiences, ordered text and picture payloads ([RFC 0044](../docs/rfcs/0044-facts-audiences-and-information-bundles.md)) |
| [`inventory-names`](inventory-names) | TOML and TypeScript | The table of other spellings the importer tries when a name matches no item ([ADR 0242](../docs/adr/0242-inventory-names-the-spelling-table-shared.md)) |
| [`lorenzoscript`](lorenzoscript) | TypeScript | LorenzoScript, Lorenzo's Markdown dialect for text: parser and HTML renderer ([RFC 0027](../docs/rfcs/0027-lorenzoscript.md)) |
| [`lorenzoscript-editor`](lorenzoscript-editor) | TypeScript | A textarea editor for LorenzoScript with a toolbar and live preview |
| [`map-engine`](map-engine) | Python | The one validator of Map systems and placement geometry: numbers, simple polygons, roles, styles and limits, with no database ([ADR 0336](../docs/adr/0336-maps-the-kind-its-system-and-its-placements.md), [ADR 0337](../docs/adr/0337-geometry-roles-and-the-validator.md)) |
| [`map-renderer`](map-renderer) | TypeScript | A hand-written SVG drawing of a Map: layout to a Scene, painting, hit testing, themes and the pan, zoom and selection around them ([ADR 0339](../docs/adr/0339-the-map-renderer.md)) |
| [`period-picker`](period-picker) | TypeScript | One control for choosing a calendar day, month, year or several, instead of flat lists of every period ([ADR 0323](../docs/adr/0323-the-calendar-period-picker.md)) |
| [`read-cache`](read-cache) | TypeScript | A bounded read cache in front of `fetch` and a prefetch queue; scoped reads stay in memory and are never authorization ([ADR 0325](../docs/adr/0325-one-read-cache-and-what-it-may-hold.md)) |
| [`stat-values`](stat-values) | TypeScript | Reading, parsing and writing an entry's stat values, and the library's stat vocabulary in its order ([ADR 0272](../docs/adr/0272-beings-editing-stats-and-handing-over.md)) |
