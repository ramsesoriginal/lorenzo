# System context

```mermaid
C4Context
  title Lorenzo — system context (API, web and authoring clients, command line, Discord bot, and the Android and iOS inventory companions)

  Person(gm, "Game Master", "Runs campaigns, owns the secrets")
  Person(player, "Player", "Sees only what they're allowed to")

  System(web, "Web frontend(s)", "Inventory, account hub, Beings, Bench, Calendars and Sessions")
  System(bot, "Discord bot(s)", "At least one")
  System(mobile, "Mobile app(s)", "Lorenzo Inventory - native Android and iOS")
  System(cli, "Command line", "lorenzo - imports, repositories, scripts")
  System(converters, "Converters", "lorenzo-convert - spreadsheets into ledgers, donjon exports into calendar documents, no API access")
  System(api, "Backend API", "Multi-tenant REST API - source of truth, and GET /app-links for where the apps live")
  SystemDb(db, "PostgreSQL", "Shared schema, row-level security per tenant")

  Rel(gm, web, "Uses")
  Rel(player, web, "Uses")
  Rel(player, bot, "Uses")
  Rel(player, mobile, "Uses")
  Rel(gm, cli, "Uses")
  Rel(player, cli, "Uses")
  Rel(converters, cli, "Files read by")
  Rel(web, api, "HTTPS/JSON, app links")
  Rel(bot, api, "HTTPS/JSON")
  Rel(mobile, api, "HTTPS/JSON")
  Rel(cli, api, "HTTPS/JSON")
  Rel(api, db, "SQL, tenant-scoped")
```

Every client (web, bot, mobile, command line) is a narrower view onto the same API, and there can be more than one of each — see [ADR 0007](../../adr/0007-apps-layout-and-multiplicity.md) and the [architecture overview](../overview.md). The web apps, which link to each other, learn where the others live from the API's registry of app links, `GET /app-links` ([ADR 0273](../../adr/0273-app-links-registry.md)); they share no navigation shell. Converters read a source file and write a native document; they never call the API, and the command line imports what they write ([ADR 0246](../../adr/0246-lorenzo-converters-the-spreadsheet-converter.md), [ADR 0311](../../adr/0311-calendar-documents-import-and-app.md)).
