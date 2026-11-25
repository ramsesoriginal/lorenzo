# @lorenzo/entity-parts

The parts of an entry's page that `apps/beings` and `apps/inventory-web` both draw, written once
([ADR 0526](../../docs/adr/0526-the-entity-parts-package.md), after ADR 0524's "extraction follows").

- **`TagEditor`**: three-state tag editing (inherited, on, explicitly off) for an entry's own page.
- **`DescriptionEditor`**: a LorenzoScript editor with the notes on links readers will not be able to follow.
- **Tags' logic**: `tagState`, `tagDefinitions`, `setTag`, `STATES`.

What an app brings is its own, given once by `createEntityParts({ client })`; each app binds it in one
small file (`lib/entityParts.ts`), as `lib/statValues.ts` binds [`@lorenzo/stat-values`](../stat-values).
The Astro templates are exported beside it:

```astro
import TagEditor from '@lorenzo/entity-parts/TagEditor.astro';
```

The package imports no app. It keeps small private copies of what its parts need (`src/internal`:
`template`, `statusLine`, `errorMessage`, `statLabel`) until where those belong is settled in a decision
of its own.

Later parts join it in the pull requests of ADR 0526: the link name editor, the description form,
Facts and a Fact's page, the library list.
