# System context

```mermaid
C4Context
  title Lorenzo — system context (target shape, nothing built yet)

  Person(gm, "Game Master", "Runs campaigns, owns the secrets")
  Person(player, "Player", "Sees only what they're allowed to")

  System(web, "Web frontend(s)", "One or many static sites")
  System(bot, "Discord bot(s)", "At least one")
  System(mobile, "Mobile app(s)", "Possibly more than one")
  System(api, "Backend API", "Multi-tenant REST API - source of truth")
  SystemDb(db, "PostgreSQL", "Shared schema, row-level security per tenant")

  Rel(gm, web, "Uses")
  Rel(player, web, "Uses")
  Rel(player, bot, "Uses")
  Rel(player, mobile, "Uses")
  Rel(web, api, "HTTPS/JSON")
  Rel(bot, api, "HTTPS/JSON")
  Rel(mobile, api, "HTTPS/JSON")
  Rel(api, db, "SQL, tenant-scoped")
```

Every client (web, bot, mobile) is a narrower view onto the same API, and there can be more than one of each — see [ADR 0007](../adr/0007-apps-layout-and-multiplicity.md) and the [architecture overview](../overview.md).
