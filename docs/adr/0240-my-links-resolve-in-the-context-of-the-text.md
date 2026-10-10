# 0240 - `my/` links: a name that resolves in the context of the text

Status: accepted

## Context

A note on a character says "she fights with her [[Longsword]]". Today that names the *catalog* item, or needs the one instance to carry a slug of its own: `[Longsword](aldras-blade)`. Not every instance should need a slug, and "her longsword" is a different thing in every character's notes. The maintainer asked for `[[my/Longsword]]`, which means *the longsword that belongs to whoever this text belongs to*. It must work anywhere a text can be attached to a being: the being's description or notes, a note on an item the being owns (a sharpening stone), a diary entry by the being, later session notes about it. It has to work in backlinks too ([ADR 0110](0110-lorenzoscript-content-references-and-backlinks.md)).

What already exists:

- `my/Longsword` already parses. A target is `(hint/)?slug` with a hint of `[a-z_]+` ([ADR 0105](0105-lorenzoscript-entity-references-and-resolver.md)), so `[[my/Longsword]]`, `[text](my/longsword)` and `![alt](my/longsword)` are references with hint `my`, slug `longsword`. `content_reference` already stores the hint ([ADR 0110](0110-lorenzoscript-content-references-and-backlinks.md)).
- A hint is "a view hint, not a namespace" (RFC 0027 section 3): the entity a slug names does not change with it. `my` breaks that on purpose; it is the first hint that changes *which* entity is meant.
- References are stored by slug and resolved when read, never by entity. A reference keeps working when an entity is renamed or moves.
- `reachable_entity_ids` ([ADR 0040](0040-item-instance-read-visibility.md)) already answers "what belongs to this character": the character, what it owns, and everything contained in either, recursively.
- Item instances get their kind from `entity_prototype`; an instance of the catalog item "Longsword" has it as a prototype.

## Decision

### `my` is a reserved hint

No parser or extractor change: `my/` is a hint like any other, and the `SPEC.md` examples gain one showing the reference `{kind: entity, hint: my, slug: longsword}` so both implementations keep agreeing. What is new is that a resolver gives `my` a meaning. It is reserved: no view may be called `my`.

### The home of a text, and its anchor

A text's **home** is the entity its information is about (the information the description payload belongs to). Its **anchor** is the being it belongs to:

- the home itself, if it is a being;
- otherwise the nearest being found by walking up from the home through *belonging*: today ownership (the item's owner) and containment (the bag it is in), the same two edges `reachable_entity_ids` walks downward;
- none if the walk ends without a being. `my/` then resolves to nothing.

Belonging is defined in one place, a function over those edges. A diary entry or a session note belongs to a being by being information on it (home = the being) or, for a session note, by a relation that does not exist yet: when it does, it is one more edge in that function, not a change to the syntax, the resolver, or backlinks. If a text has several anchors (a session about three beings), they are tried in a fixed order and the first that has a match wins.

### What `my/SLUG` resolves to

`SLUG` is looked up as always. Then, with the anchor's reachable set:

- If it names a **catalog item**: the item instances in the reachable set that are instances of it, an instance being one with that item anywhere in its prototype chain. So `[[my/Sword]]` finds a longsword if "Longsword" derives from "Sword".
- If it names anything else (an instance with its own slug, say): that entity, if it is in the reachable set. Harmless, and `my/` works for either kind of slug.
- Otherwise it does not resolve.

When several match, **any is fine**, but the choice is deterministic so a link reads the same on every render and agrees with backlinks: a direct prototype before an inherited one, then owned directly before merely contained, then by name, then by id.

An unresolved `my/` link is plain text, indistinguishable from any other ([ADR 0105](0105-lorenzoscript-entity-references-and-resolver.md)). There is **no fallback to the catalog item**: "my longsword" must not turn into a link to longswords in general when the being has none, since that would state something false.

### API: `from` on `GET /entities/resolve`

`GET /tenants/{t}/entities/resolve?slug=my/longsword&from=<entity_id>`. `from` is the home of the text being rendered. The slug list stays at 100 and may mix plain and `my/` slugs; one text is still one request. A row answers with `slug` as asked (`my/longsword`), and the instance's `entity_id`, `name` and `kinds`. Without `from`, or when `from` has no anchor, `my/` slugs are absent from the answer.

It must not show an instance the caller cannot see: candidates pass the item-instance read rule of [ADR 0040](0040-item-instance-read-visibility.md), so a hidden dagger does not resolve for a reader who may not know it exists, and looks like an instance the being never had.

### Backlinks

Nothing about a `my/` reference is stored beyond what is already: hint `my` and target `longsword`. The backlinks read, for an entity X:

- the current rule (references whose slug is X's slug, any hint other than `my`);
- plus the `my/` references whose target is the slug of a catalog item X is an instance of (or X's own slug), kept when the source text's anchor resolves that `my/` link to X by the rule above, using the same function. So a note that says `[[my/Longsword]]` is a mention of the one instance it picks, and **not** of the catalog item "Longsword": "my longsword" says nothing about longswords in general.

Candidates come from the existing index on `(tenant_id, target)`; the anchor and the pick are computed per distinct source home, then visibility filters as before. Because the resolution is computed when read, a sword given to another character moves its mentions with it, and nothing is rewritten when ownership changes.

### Bench and other clients

`render` already hands the resolver the hint, so `@lorenzo/lorenzoscript` needs no change. Bench's `LinkResolver` asks with the entry the text belongs to and keys what it remembers by `(home, hint, slug)`; a `my/` answer is kept like a miss, for 30 seconds, since ownership can change. inventory-web's resolver does the same when it wants `my/`.

## Slices

1. API: the belonging function, the pick, `from` on resolve, backlinks, tests; `SPEC.md` example. This ADR becomes accepted with it.
2. Bench: context-aware resolver; sample data with ownership; tests.
3. inventory-web: the same in its resolver.

## Not in scope

- Anchors for session notes and other relations that do not exist yet.
- Other scopes like `my/` (`campaign/`, `party/`): the same mechanism could carry them, with their own ADR.
- Letting the picker offer `my/`.

## Consequences

- One text can mean different things in different places: `[[my/Longsword]]` in a template note copied to another character follows its new home.
- A rename, a gift or a theft changes what the text shows with no rewrite.
- Resolution needs the home of the text, so every renderer must supply it; a renderer that does not simply shows the text.
- Reading "mentioned in" for an instance costs one more query keyed by its prototypes' slugs.

## Open for review

Decided here, easy to turn: containment counts as belonging (an item in the being's pack); no fallback to the catalog item. (`my/` mentions do not count for the catalog item, as the maintainer decided.)

## Addendum: Bench (slice 2)

- `LinkResolver.render(text, home)` and `renderNow(text, home)` take the entry the text belongs to; a description and a note both pass their own entry.
- Plain and `my/` references go in separate requests (`resolveSlugs(slugs)` and `resolveSlugs(['my/…'], home)`), since only the second carries `from`.
- A `my/` answer is remembered under `(home, slug)` for 30 seconds, hit or miss, because who holds what changes.
- A `my/` link nothing is held under stays text and gets its own line under the editor, apart from the "nothing is called" one: "Nothing called “blade” is held by whoever this belongs to".
- `![alt](my/slug)` shows the held instance's main picture, through the same path as any image link ([ADR 0239](0239-bench-pictures-in-text.md)).
- The sample transport models `heldBy` (an owner or container) so the unit and browser tests run the real rule without an API.
