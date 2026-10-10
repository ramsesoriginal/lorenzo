# @lorenzo/inventory-names

The table of other spellings that `lorenzo inventory import` tries when a name matches no item
([ADR 0193](../../docs/adr/0193-lorenzo-inventory-import-and-export.md)), as data, with a reader for
TypeScript ([ADR 0242](../../docs/adr/0242-inventory-names-the-spelling-table-shared.md)).

- `preprocess.toml`: the table. **Edit it here**, then `mise run //apps/cli:sync-names` to copy it
  into the CLI, which can only ship what is inside `apps/cli`. A CLI test fails when the copy is stale.
- `vectors.json`: names and the alternatives each must give, in order. This package's tests and the
  CLI's both run it, so the two readers cannot drift apart. A new case: add the name, run the
  Python reader over it, and paste what it gives.
- `src/index.ts`: `alternatives(name, table)`, `parseTable(toml)` and `builtinTable()`. The Python
  reader is `apps/cli/src/lorenzo_cli/inventory/preprocess.py`.

```ts
import { alternatives, builtinTable } from '@lorenzo/inventory-names';

alternatives('Seil (Hanf) 50 ft', builtinTable()); // ['seil, ...', 'rope, hempen (50 feet)', 'rope']
```
