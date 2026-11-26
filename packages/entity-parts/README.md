# @lorenzo/entity-parts

The parts of an entry's page that `apps/beings` and `apps/inventory-web` both draw, written once
([ADR 0526](../../docs/adr/0526-the-entity-parts-package.md), after ADR 0524's "extraction follows").

- **`TagEditor`**: three-state tag editing (inherited, on, explicitly off) for an entry's own page.
- **`SlugEditor`**: the field for an entry's slug (an app calls it "slug" or "link name"), with a suggestion and Save.
- **`DescriptionEditor`**, **`InfoForm`** and **`DescriptionEdit`**: the LorenzoScript editor with notes on links readers will not be able to follow, the form a piece of information is written in, and the description of an entry written in one.
- **`Facts`** and **`FactPage`**: the Facts about an entry, and a Fact's own page.
- **`LibraryList`**: the libraries someone can open, each linking to where the app starts in it.
- **The logic they share**: tags (`tagState`, `tagDefinitions`, `setTag`), slugs (`slugCandidates`, `slugProblem`, `suggestSlug`, `saveSlug`) and an entity's information (`listInformation`, `getDescription`, `saveDescription` and the rest), each taking the app's client.

What an app brings is its own, given once by `createEntityParts(context)`: its `client`, how a protected picture is read (`blobUrl`), the viewer's `locales`, how texts are drawn with its own links (`showDescriptions`), where a Fact's page is, where its libraries link, and the words it uses ("slug" or "link name", "Display title" or "Heading", "Facts about this item"). Each app binds it in one
small file (`lib/entityParts.ts`), as `lib/statValues.ts` binds [`@lorenzo/stat-values`](../stat-values).
The Astro templates are exported beside it:

```astro
import TagEditor from '@lorenzo/entity-parts/TagEditor.astro';
```

The package imports no app. It keeps small private copies of what its parts need (`src/internal`:
`template`, `statusLine`, `errorMessage`, `statLabel`) until where those belong is settled in a decision
of its own.
