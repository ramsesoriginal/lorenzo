# @lorenzo/stat-values

Reading and writing an entry's stat values through `apps/api`, and parsing what a person types for
one ([ADR 0263](../../docs/adr/0263-inventory-web-editing-stat-values.md), extracted by
[ADR 0272](../../docs/adr/0272-beings-editing-stats-and-handing-over.md)). Used by `apps/inventory-web`
(for items) and `apps/beings` (for beings).

- `statDefinitions(client, tenantId)`: every stat that is not a tag, with its group's name.
- `statVocabulary(client, tenantId)`: every stat, tags included, in the library's group and definition order (ADR 0278, 0283).
- `getEntityDetail(client, tenantId, entityId)`: the entry and its effective stats.
- `statRows(definitions, entity)`, `sourceOf(row)`: what an entry resolves each stat to, and whether
  that is its own.
- `parseStat(definition, text)`, `decimalText(n)`: what typing gives; a decimal keeps its point.
- `setStat` / `clearStat(client, tenantId, entityId, ...)`: write or remove the entry's own value,
  refusing with `StatChangedError` if it moved since it was read.

The calls take the app's `LorenzoClient`, so each app keeps its own token and base URL. The editing
form itself (DOM) stays in each app: it is bound to the app's templates and status lines.
