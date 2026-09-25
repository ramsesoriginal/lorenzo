# 0110 - LorenzoScript references: `content_reference`, a Python extractor, and backlinks

Status: accepted

## Context

[RFC 0027](../rfcs/0027-lorenzoscript.md) stage 7 records what description texts link to, and answers "what links here". The RFC fixed three things:

- **The server extracts references itself** (§6), rather than trusting a client. `apps/api` is Python, so it needs its own implementation, held to the same shared `SPEC.md` examples as the TypeScript package.
- **Unresolved targets are kept** (§7), like a wiki's red links, so they count once the slug exists.
- **Backlink reads respect the source's visibility.** A backlink from GM-only text would reveal a secret.

[ADR 0101](0101-editable-information-and-description-payloads.md) left the hook: `description_payloads.write_description` is the only code that writes description text. This ADR decides the rest.

## Decision

### The extractor: `lorenzo_api.lorenzoscript`

A module in `apps/api` ports `@lorenzo/lorenzoscript`'s `parse` and `references` to Python.

- **Where it lives.** It has one consumer. The maintainer chose a module over a separate package under `packages/`, so the API's image still builds from `apps/api` alone.
- **How much of the parser.** It ports all of it: blocks, inlines, and emphasis. Emphasis can't be skipped, because the nesting limit of 32 ([ADR 0100](0100-lorenzoscript-core-parser-and-renderer.md)) counts emphasis too, and a link past that limit isn't one. Rendering, heading ids, and TeX conversion are left out.
- **Where Python differs from JavaScript,** it follows JavaScript:
  - `\s` and `trim` use JavaScript's whitespace set.
  - `\d` and `\w` are ASCII.
  - Unicode punctuation and symbols come from `unicodedata`.
  - Next to a delimiter run, a character outside the Basic Multilingual Plane counts as neither space nor punctuation. JavaScript sees half a surrogate pair there.
  - `{{date 0000-01-01}}` is a valid date, as it is for JavaScript's `Date`.

**Every example now checks references.** Both suites run every `SPEC.md` example, and an example with no references section must have none. One existing example needed a section, and new examples cover what the renderer's examples didn't: links inside code, footnote definitions, table cells, nested containers, and duplicates.

### Hostile input, now on the server too

Parsing on the server means any author's text costs API time, so every scan in both parsers must stay linear however the text is shaped. CodeQL flagged three patterns in the port, and probing found more that the TypeScript package shared. Each took seconds to minutes on inputs of 20 to 100 KB:

- **Line breaks:** a run of blanks before a line break. The check is now a count, not a regex.
- **Directives:** an unclosed `{{name …`. A lazy pattern there was cubic; it's now scanned.
- **Code spans:** one with a single leading space.
- **Trailing attributes:** blanks where a heading's `{…}` could start. Now the last `{` is checked.
- **Link destinations:** `[a](` or `[a](<b` repeated. A bare destination now stops after 32 nested parentheses, as CommonMark allows an implementation to, and `<…>` stops at the next `<`.
- **Link titles:** an unclosed one. A title scan that ran off the end is remembered, since any later one would too.
- **Backtick runs:** runs of many different lengths. Every run is now found once, up front.

Python also had two costs of its own: building text with `+=` on a stored string, and slicing the source.

Behaviour doesn't change, with one exception: a destination with more than 32 nested parentheses isn't a link. `SPEC.md` records it. Both suites now test each of these inputs, and the TypeScript test doesn't finish against the old code.

### `content_reference`

One row per reference, per description payload:

| Column | |
| --- | --- |
| `payload_id` | foreign key to `payload.id`, `ON DELETE CASCADE` |
| `position` | its place among the text's references, first use first; the primary key with `payload_id` |
| `tenant_id` | foreign key to `tenant.id`, `ON DELETE CASCADE` |
| `kind` | `entity`, `image`, `date`, or `calendar` (a check constraint) |
| `hint` | the view hint of an entity or image reference; `''` otherwise |
| `target` | the slug, the ISO date (`YYYY-MM-DD`, so text order is date order), or the calendar expression |

- ENABLE plus FORCE row-level security, with the usual `tenant_isolation` policy ([ADR 0002](0002-multi-tenancy-shared-schema-rls.md)).
- A partial index on `(tenant_id, target) WHERE kind IN ('entity', 'image')` serves backlinks.
- **Keyed by slug, not by entity.** A reference resolves through `entity_slug` when it's read, exactly as rendering does. A slug set later makes old links count, and a slug that moves to another entity takes its links along.
- **Entity and image slugs over 100 characters aren't stored.** No slug can be that long ([ADR 0107](0107-entity-slugs-and-batch-resolve.md)), so they could never resolve, and they'd risk the index's size limit.
- **All four kinds are stored**, by the maintainer's choice. Dates and calendar expressions have no reader yet. A later "what happened on this date" or calendar feature can read them without re-reading every text.

### Writing

`write_description` extracts the references when it creates a description, and whenever the content changes. It replaces all of the payload's rows. A change of locale alone leaves them.

Deleting a payload deletes its rows, as does deleting its information or entity.

There's no backfill. Stages 6 and 7 reach `main` together, so production has no LorenzoScript text yet. An existing description gets its rows the next time it's saved.

### Reading: `GET /tenants/{tenant_id}/entities/{entity_id}/backlinks`

It returns `Page[BacklinkOut]`: one row per piece of information whose description links to the entity, or shows its picture.

- `BacklinkOut` has `entity_id`, `name`, and `kinds` for the entity the information is about, plus `information_id`, `title`, and `type`.
- Rows are ordered by that entity's name, then the information's `order`, then its id.
- **Access.** The same as `GET /entities/{id}`: any tenant participant, and `404` for an unknown entity.
- **Visibility.** Only information the caller can see (`InformationVisibility.can_see`) is listed.
- **Paging.** Rows are filtered in Python before paging, so pages are full and `total` counts only visible rows. That meets [ADR 0109](0109-player-knowers-knower-listing-and-information-list.md)'s concern about short pages that reveal hidden counts. Its SQL form of the same check, `visible_information_clause`, landed alongside this ADR and can replace the Python filter without changing the response.
- An entity without a slug has no backlinks. The entity's own information linking to itself isn't listed.

### inventory-web: "Mentioned in"

The item page lists the item's backlinks under "Mentioned in". Each entry links to that entity's page, chosen by its kinds as in [ADR 0108](0108-lorenzoscript-in-inventory-web.md). The list only appears when there's something in it.

## Not in scope

- Reading date and calendar references.
- "Wanted pages": slugs that texts link to but no entity holds.
- References from anything but description text. RFC 0015's `payload_entity` is an authored reference, a separate thing.
- Showing where in the text a link sits.

## Consequences

- Every description write now parses the text on the server. That's linear in its length (ADR 0100) and happens once per write.
- The parser has two implementations. The shared examples keep them one definition, and every example now checks references as well as HTML.
- A backlink appears for exactly the readers who can see the information it comes from.
