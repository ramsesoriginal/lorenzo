# RFC: How should an entity's full "address" — its position on every world-model axis beyond physical containment — be modeled?

Status: proposed — Decision open

## Context

[docs/domain/world-model.md](../domain/world-model.md) says one thing (a building, a person, an army) can be positioned along six independent axes at once: **physical containment**, **position in space**, **sphere**, **plane**, **parallel reality (timeline)**, and **multiverse**. It is explicit that these are *not* one hierarchy — "a plane doesn't sit 'inside' a sphere the way a city sits inside a province" — and that an entity's full address is a combination of where it sits on each axis, not one path down a single tree. It also deliberately leaves time and causality open: "it's the kind of thing that needs an RFC once it's actually being built, not an assumption baked into this doc." This is that RFC.

One axis is already built and shipped: physical containment, the `containment` table ([ADR 0016](../adr/0016-containment.md)) over [ADR 0012](../adr/0012-entity-table.md)'s `entity`, with quantity/stacking ([ADR 0041](../adr/0041-containment-quantity-and-stacking.md)) and GM reachability walking it ([ADR 0046](../adr/0046-gm-reachability-widens-to-surroundings.md)). This RFC is about the **other five axes**, how an entity's full address composes all six, and how places on different axes get connected (portals) — not about replacing containment.

Whatever is proposed has to live inside what is already decided: shared schema + `FORCE ROW LEVEL SECURITY` with a `tenant_id` on every tenant table ([ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md), [ADR 0021](../adr/0021-restricted-app-role-for-rls-enforcement.md)), the entity/component core ([ADR 0012](../adr/0012-entity-table.md)), and the acyclic prototype graph ([ADR 0015](../adr/0015-entity-prototype.md)). It also has to coexist with [RFC 0024](0024-repositories.md)'s repositories (a repository is a `tenant.kind`, copied into play tenants), since two published cosmologies sharing one tenant is a headline use case.

### How this was produced

Following [RFC 0024](0024-repositories.md)'s precedent, this design came out of a structured, adversarial debate among eight independently-researched perspectives, each committed to its own needs and no-gos, each grounded in the real schema, over three rounds: independent pitches (none saw the others), adversarial cross-critique (each had to attack at least two pitches, including one close to its own, and pre-empt the strongest attack on its own), then rebuttal and convergence against two moderator-synthesized candidates. Every design was scored 1–5 by its participants on seven criteria: **simple, flexible, pragmatic, best-practice, future-proof, innovative, and fits what's already built**.

| Persona | Role | Core need | No-go |
| --- | --- | --- | --- |
| Alice | tenant owner/admin | predictable cost and migrations as tenants multiply | one campaign's exotic setting degrading every other tenant |
| Bob | basic player | "where's my stuff" in one glance, no axis vocabulary | having to understand spheres or timelines to find his backpack |
| Charlie | Cyberpunk GM, one Berlin neighbourhood in a solar-system setting | street-level and solar-system scale on one space axis | forcing AU coordinates on a Späti, or a street address on Ceres |
| David | D&D GM mixing Greyhawk and Forgotten Realms | two published cosmologies coexisting; portals as first-class, queryable connections | portals bolted onto one axis as a special case |
| Eve | homebrew multiverse worldbuilder | axes composable and extensible for settings nobody has written yet | hardcoding D&D or sci-fi assumptions, including exactly these six axes |
| Frank | programmer | implementable on Postgres + RLS without N+1 or unmaintainable recursion; incremental migration | elegant-on-paper, nightmare-to-query designs |
| Grace | cozy author, one mushroom village | the whole axis system invisible and free when unused | being forced to declare a plane or multiverse, or getting a silent "Prime Timeline" row |
| Heidi | security-minded architect | correct tenant isolation as axes compose; one extension mechanism | "add an axis" meaning a new bespoke table pattern every time |

The Decision below is left open. What *did* converge is written as the shared baseline and two candidate designs; what did not is preserved as named disagreements and verbatim dissents, not smoothed over.

### A defect in shipped code, found along the way

Heidi's round-1 pitch observed — and the moderator verified against the code — that every entity-to-entity edge table (`containment`, `entity_prototype`, `ownership`, and the other `ForeignKey("entity.id")` columns in `apps/api/src/lorenzo_api/models/`) references `entity(id)` with a **single-column** foreign key. Postgres evaluates foreign-key checks without row-level security, and no migration adds a same-tenant constraint or trigger. `PUT /tenants/{tenant_id}/item-instances/{entity_id}/container` (`_perform_set_container` in `routers/item_instances.py`) also does not check that the target container belongs to the caller's tenant (the bulk prototype routes do, via `_validate_prototype_ids_exist`). So a member of tenant A who has another tenant's entity UUID can create a `containment` row whose parent lives in tenant B, and the FK error-vs-success difference is an existence oracle for guessed UUIDs. Random UUIDs keep the practical severity low, but it is exactly the "never rely on application-level filtering alone" failure [AGENTS.md](../../AGENTS.md) warns about — here, there isn't even application-level filtering. Five of the eight round-1 pitches reproduced the same hole in their own new tables, including one hop removed (a composite FK to `entity` but a tenant-less FK to a `frame` row). It is the single most consistent finding of the debate, and it is why the baseline below starts with a retrofit (B0). The live route should be fixed on its own track rather than wait for this RFC.

## Shared baseline (converged — all eight accept)

These held across all three rounds. Each is a condition every candidate below assumes.

- **B0 — composite tenant FKs, first, as their own ADR.** `ALTER TABLE entity ADD UNIQUE (id, tenant_id)`, then retrofit composite `(…, tenant_id) REFERENCES entity (id, tenant_id)` FKs onto the existing edge tables via `NOT VALID` → `VALIDATE CONSTRAINT`, as an explicit amendment to ADR 0015/0016. From then on, **every FK on a tenant table carries `tenant_id`** — including the hop to whatever frame/axis row a placement points at — enforced by a CI check over `pg_constraint`, not by memory. No scope column that participates in such an FK may be nullable (under `MATCH SIMPLE`, a single NULL column silently skips the whole check).
- **Frames are ordinary entities.** A plane, sphere, timeline, or universe is an `entity` row with a small subtype table (the ADR 0012 `item`/`being` pattern), so it gets `information`, knowledge-gated visibility, stats, prototypes, and containment for free. "The Net" can be a plane with GM secrets.
- **Nothing is seeded, ever.** No default plane, "Prime" timeline, epoch, axis row, or relation kind is materialized into any tenant. An unused axis system costs zero rows, zero form fields, zero response keys. **Absence means "not modeled"** — never "unknown", never "default", never "timeless".
- **Placement inherits down physical containment.** An entity with no explicit placement on an axis takes the nearest containing ancestor's (ADR 0046's upward walk, `entity_access.containing_ancestors_ids`). Tag the Material Plane on Toril once and every tavern, mug and PC on it is on the Material Plane. An explicit placement overrides.
- **Positions never inherit through prototypes.** A "Longsword" prototype placed nowhere does not put every longsword somewhere. Definitions may inherit; positions do not.
- **The new axes never feed ADR 0046 GM reachability.** Pinned by a test. This is what killed modeling space as containment (see "Designs considered and dropped").
- **Batched, invoker-rights resolution; never a tenant-wide view.** The full address comes from one `SECURITY INVOKER` function over an id array (`world_address(uuid[])`), so a 30-item inventory is one round trip, with a cycle guard (containment is cycle-tolerant by design, ADR 0016). No recursive view seeded from every entity in the tenant (the `v_effective_stat` pattern is explicitly rejected here). No `SECURITY DEFINER` in any traversal; every view `security_invoker = true`; both CI-checked.
- **The address is opt-in on reads.** `EntityDetailOut` and every list endpoint are unchanged by default. The GM-facing absolute address is a separate `GET …/entities/{id}/address` (or `?include=address`), returns only axes that actually resolve (no `"timeline": null` keys), carries `inherited_from` for debugging, and short-circuits with an `EXISTS` probe when the tenant has no placement rows at all.
- **The player read is viewer-relative and vocabulary-free.** `GET …/whereabouts?relative_to=<character_id>` returns, per item, a `status` of `with_you | stashed | elsewhere | unknown` plus, only when something differs from the viewer's own character, the knowledge-gated *title* of the differing place — never an axis name. Anything the character carries gets no address note. The loot-bot's `/inventory` headings become "On you", "In your Bag of Holding", "Left at …", "Not with the party: …". This read ships **before** the GM `/address`, so the player surface is never retrofitted onto a GM shape.
- **Inventory is never filtered by timeline or variant.** An owned item in another timeline, or inside a place that "doesn't exist" there, is `elsewhere` or `unknown` — it never disappears from `owned-by`, `/inventory`, or `/whereabouts`.
- **Connections (portals, moongates, time rifts, coterminous mirrors) are entities.** `connection` (an entity subtype) plus `connection_endpoint(connection_entity_id, role, endpoint_entity_id, tenant_id)`, one row per end, composite tenant FKs. Connection kinds are prototypes (data), not an enum. "What can I reach from here" is a batched function over `[X] ∪ containing_ancestors(X)`, gated by knowledge. Connections never feed ADR 0046. They are never an axis, a relation kind, or a column on one axis.
- **Mirrors are connections, not prototypes.** The Ethereal echo of Greyhawk City is its own entity joined by a connection with a `Coterminous` prototype — it must not inherit the Material city's population through `v_effective_stat`. Prototypes stay for genuine timeline/universe variants only.
- **No time columns in the first slice.** See "Time and causality".
- **New tables join RFC 0024's lists.** Every new table is named in RFC 0024's repository read-policy and copy-walk table lists, so repository content can carry frames, placements and connections.

## Candidate designs

Round 3 converged on the "Frames" family (six of eight accept it with conditions) and split on one question underneath it: **is the set of axes stored as a fixed list in the schema, or as rows in a platform-owned registry shaped so tenant-defined axes can be added later without a rewrite?** That split is the difference between the two candidates. Both implement the same v1 semantics and API.

### Candidate 1 — Frames with a fixed axis set

Axes are a closed, platform-owned list, identical in every tenant. Adding an axis is a migration plus an ADR — "deliberate, reviewed, and the same for everyone."

```sql
-- after B0 (entity has UNIQUE (id, tenant_id))
CREATE TABLE frame (                       -- a frame IS an entity (ADR 0012 subtype pattern)
  entity_id  uuid PRIMARY KEY,
  tenant_id  uuid NOT NULL,
  axis       text NOT NULL CHECK (axis IN ('sphere', 'plane', 'timeline', 'universe')),
  UNIQUE (entity_id, tenant_id, axis),
  FOREIGN KEY (entity_id, tenant_id) REFERENCES entity (id, tenant_id) ON DELETE CASCADE
);

CREATE TABLE entity_frame (                -- "X is on this plane / in this timeline"
  entity_id        uuid NOT NULL,
  tenant_id        uuid NOT NULL,
  axis             text NOT NULL,
  frame_entity_id  uuid NOT NULL,
  PRIMARY KEY (entity_id, axis),           -- contested: see D2
  FOREIGN KEY (entity_id, tenant_id) REFERENCES entity (id, tenant_id) ON DELETE CASCADE,
  FOREIGN KEY (frame_entity_id, tenant_id, axis)
    REFERENCES frame (entity_id, tenant_id, axis) ON DELETE CASCADE   -- tenant AND axis match, in the DB
);
CREATE INDEX ON entity_frame (frame_entity_id) INCLUDE (entity_id);   -- "everything on the Ethereal"

CREATE TABLE spatial_position (            -- majority A-i shape; see D1
  child_entity_id   uuid PRIMARY KEY,      -- at most one place in space, like containment
  parent_entity_id  uuid NOT NULL,         -- Ceres -> Sol; a ship in flight -> the Belt
  tenant_id         uuid NOT NULL,
  -- optional per-edge precision (orbit, coordinates) is a later sub-slice, never required
  FOREIGN KEY (child_entity_id, tenant_id)  REFERENCES entity (id, tenant_id) ON DELETE CASCADE,
  FOREIGN KEY (parent_entity_id, tenant_id) REFERENCES entity (id, tenant_id) ON DELETE CASCADE
);
-- every table: ENABLE + FORCE ROW LEVEL SECURITY,
--   USING (tenant_id = current_setting('app.tenant_id')::uuid)
```

Resolution, for each id: walk up the physical chain, where each hop follows `containment` if the entity has a containment row, otherwise `spatial_position` (**containment wins**, so a docked ship resolves through the dock and a stale in-flight row is ignored). Per axis, the nearest `entity_frame` row on that chain wins. The move service takes `SELECT … FOR NO KEY UPDATE` on the entity row when docking or undocking, so the two tables can't be raced into disagreement. Under the majority view there is no trigger on `containment` (see D1 for Frank's and Grace's dissent).

**Fixed-set variants.** Alice, Charlie and Grace are equally happy with `text + CHECK` or a global lookup table `world_axis(key text PRIMARY KEY, …)` that is read-only to `lorenzo_app`. Frank prefers the lookup table as a home for per-axis display metadata. Nobody accepts a Postgres enum. If tenant-defined axes are ever justified, Alice's additive path is a nullable `custom_axis_id` with a full composite tenant FK plus `CHECK ((axis IS NULL) <> (custom_axis_id IS NULL))`. Nothing is rewritten, and no FK ever goes unchecked.

**Who backs it:** Alice (preferred), Charlie (preferred), Frank (preferred), Grace (preferred). Bob and David accept it but prefer Candidate 2. Heidi accepts it only if space is a fifth `entity_frame` axis (D1). Eve rejects it as an end state.

### Candidate 2 — Frames with an extensible axis registry ("the bridge")

The same v1 semantics, API and axis list as Candidate 1. The difference is that the axis is a foreign-keyed row, never a name in a column, CHECK list or primary key, so a later ADR can add tenant-defined axes (Eve's *Resonance*, *Dream-depth*) as additive steps. This candidate exists because round 3 showed that the obvious bridge sketch was unsafe, and Heidi and Eve independently specified the conditions under which it isn't:

```sql
CREATE TABLE world_axis (
  id       uuid PRIMARY KEY,
  key      text NOT NULL,                 -- 'plane', 'timeline', ...: the global identity RFC 0024 copies match on
  scope    uuid NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',  -- nil = platform. Never NULL.
  max_one  boolean NOT NULL,
  acyclic  boolean NOT NULL,
  UNIQUE (scope, key),
  UNIQUE (id, scope),
  CHECK (scope = '00000000-0000-0000-0000-000000000000')   -- v1: platform rows only; dropped by a later ADR
);
REVOKE INSERT, UPDATE, DELETE ON world_axis FROM lorenzo_app;   -- ADR 0021's default grants would
                                                               -- otherwise make it writable; test-pinned

CREATE TABLE entity_frame (
  id               uuid PRIMARY KEY,        -- surrogate key: "one per axis" is NOT the PK (T1)
  entity_id        uuid NOT NULL,
  tenant_id        uuid NOT NULL,
  axis_id          uuid NOT NULL,           -- never an axis name (T3)
  axis_scope       uuid NOT NULL CHECK (axis_scope IN ('00000000-0000-0000-0000-000000000000', tenant_id)),
  frame_entity_id  uuid NOT NULL,
  FOREIGN KEY (axis_id, axis_scope) REFERENCES world_axis (id, scope),
  -- plus the composite entity/frame FKs from Candidate 1
);
CREATE UNIQUE INDEX entity_frame_one_per_axis ON entity_frame (entity_id, axis_id);
  -- later, if non-exclusive axes arrive: carry max_one into the FK and make this partial
```

The three tests Eve set (T1–T3), and Heidi's two holes, as design rules:

- **T1.** One-position-per-axis is a unique index, not the primary key.
- **T2.** Platform rows use a non-null nil-UUID scope, not `tenant_id IS NULL`. This is Heidi's fix for the `MATCH SIMPLE` skip that Alice, Charlie and Grace each found in the NULL-tenant version. When tenant rows arrive, `world_axis` gets an RLS policy `scope = nil OR scope = current tenant`, which is a new RLS shape and needs its own ADR 0002 amendment.
- **T3.** Rows reference `axis_id`, never a name.
- **No app writes.** The registry is read-only to the app role.
- **No shadowing.** This is David's condition. A future tenant axis may never reuse or shadow a platform `key`, so two published settings copied into one tenant always land on the same `plane` axis by construction.

**The later B ADR would then be:** drop the CHECK, add the policy, and re-grant INSERT under that policy's `WITH CHECK`. Bob adds a player-safety condition to that ADR: every tenant axis declares `in_player_read boolean DEFAULT false` and a written rule for what "elsewhere" means on it. With the default, an unknown axis degrades to silence in player reads, never to leaked vocabulary or a wrong "elsewhere."

**Honesty caveat, preserved.** Frank, Charlie and Grace dispute that this makes tenant axes "additive" in any meaningful sense. Coordinates, per-kind rules carried into the FK, and a mixed platform/tenant RLS policy are still real design and migration work, and the RFC should not claim otherwise. Heidi's nil-scope sketch answers the FK-safety objection, but it arrived in round 3 and **has not been reviewed by the other seven**. It is the first thing to check if this candidate is chosen. Alice rejects the lookup table as speculative structure (AGENTS.md: "don't add application code speculatively"), and prefers Candidate 1 plus a later `custom_axis_id`.

**Who backs it:** Bob (preferred), David (preferred), Heidi (preferred), Eve (as the v1 path, only if T1–T3 hold). Frank, Charlie and Grace accept it only as "Candidate 1 with a nicer lookup table", without its future-proofing claim. Alice rejects it.

### Worked examples (both candidates)

- **Grace's village.** Zero `frame`, `entity_frame`, `spatial_position` or `connection` rows. `GET …/entities/{bufo_pantry}` is byte-identical to today. `/address` returns `{ "path": [pantry, Grandma Bufo's burrow, Toadstool Row] }` and nothing else. No form gains a field.
- **Bob's backpack.** Bram's items resolve through `containment` exactly as now. `/whereabouts?relative_to=bram` says `with_you` for everything he carries, and for the armour stashed in Blackstaff Tower, `stashed` + "Blackstaff Tower". If the party is on the Ethereal Plane and the armour isn't, it says `elsewhere` + "Blackstaff Tower", still with no axis word.
- **Charlie's Berlin.** Kreuzberg streets, the Späti and the rooftop are ordinary `containment`. Street addresses are `information` payloads (GM-only if wanted), never coordinates. Earth has `spatial_position → Sol`, Ceres `→ Sol`, the *Kalte Mamsell* in flight `→ Belt`. Docking the ship at Ceres Dock 4 writes `containment` and, under row lock, clears the space edge, and the resolver would ignore a stale one anyway. The Späti's space answer is inherited through Berlin → Earth → Sol, with no precision forced anywhere. The Net is a `plane` frame with its own lore.
- **David's two cosmologies.** Toril `entity_frame(plane → Prime Material)`, `(sphere → Realmspace)`; Oerth `(plane → Prime Material)`, `(sphere → Greyspace)`. Both repositories' placements land on the same `plane` axis by construction. Reconciling the two "Prime Material" frame entities is an entity-level RFC 0024 copy choice (merge/skip), or the choice disappears if both depend on a shared cosmology repository. The Waterdeep tavern-cellar portal is a `connection` entity with a `Portal` prototype, one endpoint contained in the cellar and one in Greyhawk City's Ethereal echo. That echo is itself joined to Greyhawk City by a `Coterminous` connection. "What can I reach from this cellar" lists both hops, each knowledge-gated. The portal can have a command word nobody has learned yet, be locked, or be carried in a backpack.
- **Eve's *Undertow Choir*.** Under either candidate in v1, Resonance (musical key) and Dream-depth are *not* address axes. They become `group_member` rosters, stats, or `information`, and a bell in two keys is one entity with a grouping, not two positions. Candidate 2 keeps the door open to making them real axes; Candidate 1 routes them through a platform ADR. Eve's dissent below says why she considers this a real loss rather than a modeling convenience.

## Scoring

Final round-3 scores, the **median of the eight participants' own 1–5 ratings** (per-persona scores are in the debate record):

| Criterion | Candidate 1 (fixed set) | Candidate 2 (bridge) | Tenant axes-as-data now (dropped for v1) |
| --- | --- | --- | --- |
| Simple | 4 | 4 | 2 |
| Flexible | 3 | 3–4 (4 once the tenant-axis ADR lands) | 5 |
| Pragmatic | 5 | 5 | 3 |
| Best-practice | 4.5 | 4.5 (5 from its backers; 3 from those who see a latent FK hole if T2 is dropped) | 4 |
| Future-proof | 3 | 4 | 4 |
| Innovative | 3 | 3 | 4 |
| Fits what's built | 5 | 5 | 3 |

Round-1 self-scores of the eight original pitches (simple / flexible / pragmatic / best-practice / future-proof / innovative / fits built), for the record of where each started:

| Pitch | Scores | Shape |
| --- | --- | --- |
| Alice | 4/3/5/4/3/3/5 | space as containment extended upward; opt-in `frame` + `entity_frame` |
| Bob | 5/3/5/4/3/3/5 | `entity_frame` + viewer-relative `/whereabouts` |
| Charlie | 3/4/4/4/3/4/4 | separate `space_anchor` tree + `entity_layer` |
| David | 3/5/4/4/4/4/5 | frames + `connection` / `connection_endpoint` entities |
| Eve | 3/5/3/4/5/4/4 | tenant-defined `axis` kind + generic `axis_position` with coordinates |
| Frank | 4/4/5/4/4/3/5 | `spatial_position` + `frame`/`entity_frame` + `entity_variant`, batched resolver |
| Grace | 5/4/5/4/4/3/5 | one sparse `placement` table, zero-cost when unused |
| Heidi | 3/5/3/5/4/4/4 | tenant `relation_kind` registry + generic `entity_relation`, DB-enforced rules |

The spread tells the story. Every design that scored 5 on *flexible* scored at most 3 on *simple* or *pragmatic*. Candidate 2 is the attempt to buy back future-proofing without paying for flexibility up front.

## Designs considered and dropped

- **Position in space as containment extended upward** (Alice, round 1). Dropped unanimously; Alice withdrew it herself in round 2. ADR 0046's GM reachability walks up to the containment root and back down, so a player in Charlie's Späti would widen the GM's view to a whole solar system's GM-private content, including other campaigns' in the same tenant. It would also put Selûne in Toril's `children`, show Sol as a container on the inventory-web kanban board, and change `v_item_instance.container_entity_id` semantics.
- **Tenant-defined axes-as-data in v1** (Eve, Heidi). Not rejected in principle; deferred. Several round-2 objections landed:
  - Per-tenant rules (`max_one`, `acyclic`) change response shapes, so one tenant returns a list and another an object.
  - Two repositories each shipping a "Plane" axis produce duplicates or a merge prompt on built-in vocabulary, which is exactly David's two-setting case.
  - No player-safe way to word an axis the client has never seen was specified.
  - Heidi (freeze rules) and Eve (loosenable rules) disagreed on rule changes; they later converged on cascade + atomic re-validation with a 409.
  - Eve's strongest counter stands on the record: ADR 0014 already accepted per-tenant schema-in-data for `stat_group`/`stat_definition`. The reply from Alice and Frank is that axes are *traversed* and their rules shape query plans and API shapes, while stats are only *read*.
- **One generic edge table for every relation** (Heidi's `entity_relation` + `relation_kind`). Heidi gave up "one relation table for everything" in round 3. Portals went to connection entities, `causes` was deferred with time, and Frank's argument held: four tables for four genuinely different semantics (a single-parent forest, a tag, a lineage, identity shadowing) is not four patterns for five axes.
- **Mirrors and parallel versions as prototypes only** (Alice, Bob, Charlie, Grace in round 1). Mirrors are coterminous, not is-a (David). "Everything in Timeline B" can't be listed from `entity_prototype`, which can't tell a counterpart from an is-a edge (Frank). Prototypes stay as *one* ingredient of timeline variants, not the whole mechanism.
- **Seeding default kinds, axes or frames into every tenant** (Heidi round 1). It violates Grace's zero-cost invariant, and every later platform change becomes a per-tenant data migration (Alice).
- **A tenant-wide recursive address view** (Heidi and Eve, round 1). A tenant-wide view walks every entity in the tenant on every single-entity read. Replaced by Frank's id-array function.
- **Putting the address on every read** (Grace's `exclude_none` field, Frank's round-1 list endpoints). Every tenant pays even with zero rows, and one tagged frame would put "plane: Outlands (via Sigil)" chrome on every player's items across every campaign in the tenant (Bob against Grace).
- **Time columns in v1** (David's `clock_label` / `local_time`, where `NULL` meant "timeless"). David withdrew them. A NULL must never carry lore meaning.

## Unresolved disagreements

These did not converge and are left for the Decision.

**D1 — Is position-in-space its own containment-shaped tree, or a fifth `entity_frame` axis?**

- *Separate tree* (`spatial_position` / `space_anchor`): Alice, Bob, Charlie, David, Frank. Charlie's three reasons:
  - Space needs the *opposite* precedence of frames: a containment parent overrides a lower space row, whereas for frames the nearest explicit row wins.
  - Space targets are bodies, not layers, so every orbited moon and station would otherwise have to become a `frame` row.
  - Per-edge precision has exactly one home.
- *Fifth axis* in `entity_frame`: Heidi, Grace, Eve. One placement mechanism, so "the next axis" never argues about which pattern to copy. Heidi rejects Candidate 1 outright with a second tree.
- *Enforcing "containment wins", within either shape:*
  - Resolver precedence plus a service row lock, with no trigger on `containment`: Alice, Charlie, David, Heidi. A stale space row can exist; it is harmless only because of precedence, and Charlie names that as a real concession.
  - Frank wants a DB-enforced either/or trigger on both tables that locks the entity row first, and says a stale row is "still a lie the RFC 0024 copy walk would read".
  - Grace, under the fifth-axis shape, wants an auto-clearing (never rejecting) trigger on `containment`.
  - Either trigger is an explicit ADR 0016 amendment. That ADR's "no CHECK and no trigger" was about cycle prevention, but it is still a new write-path cost on a hot table.

**D2 — Can "one position per axis" be the primary key?**

- *No, it must be a unique constraint over a surrogate-keyed row* (Frank, Heidi, Eve). History can then later swap it for `EXCLUDE USING gist (entity_id WITH =, axis WITH =, validity WITH &&)` without re-keying anything that references a placement. Eve adds that two time-separated positions on one exclusive axis are just one entity's normal history.
- *It can stay the primary key, because history belongs in a separate table* (Bob, Charlie). `containment` and `entity_frame` stay current-state, and "where is my stuff *now*" never needs a time filter. History arrives as its own additive table keyed on (entity, frame-local time).
- Alice and Grace require only "no time column in v1" and are compatible with either.
- Candidate 2 is T1 by definition. Candidate 1 as sketched uses the PK, so choosing Candidate 1 also means choosing a side here.

**D3 — How is "doesn't exist in this timeline" represented, and on which axes?** (All agree `entity_variant(origin, frame, variant)` ships in its own later sub-slice, and that it never filters ownership or inventory reads.)

- A NULL `variant_entity_id` tombstone: Frank, David, Heidi.
- An explicit `kind = 'absent'` rather than a meaningful NULL: Charlie, consistent with the baseline's "no NULL carries lore meaning".
- A "destroyed" variant entity: Alice's and Bob's preference, for readability only.
- Keyed by timeline only (Frank), timeline or universe (Charlie), or any frame (Eve: "the bell does not exist in this Vault").

**D4 — Is a thing ever in two places on one axis?** Eve: yes. The chord-bell sounds in two keys, and a Braided Strand timeline has two parents. Alice, Bob, David and Grace: in v1 that is a grouping (`group_member`) or information, not a position; single-parent branching until a lineage table is justified. Only Candidate 2 leaves room to change this without re-keying.

## Dissents (verbatim, as each participant asked them to be preserved)

> **Alice (tenant owner):** "Per-tenant configurable structure is a cost the tenant never sees and the platform pays forever. Every tenant-specific rule is a query shape, an API shape and a support answer that differ per tenant, and none of them show up in a demo. I accept that A turns worldbuilders' novel axes into platform requests. That is the correct direction for the cost to flow. Before any tenant-extensible axis is ever built, it should have to show a real user, a real query plan, and a migration story that doesn't involve touching tenants one at a time."

<!-- -->

> **Bob (player):** "Storage can be as rich as the GMs need, but a player's question 'where is my stuff?' must have one answer, relative to their own character, readable at a glance. Any axis a player's own character isn't meaningfully 'elsewhere' on stays silent. Anything the player is carrying never gets an address note. An empty placement means 'normal', never 'unknown'. Timeline variants, tombstones or visibility filters may hide *world* content, but they must never make an item the player owns disappear from their inventory. It is 'elsewhere' or 'somewhere you can't reach right now', never gone. Any future tenant-defined axis stays invisible to player reads until it is deliberately opted in and has a defined rule for what 'elsewhere' means on it."

<!-- -->

> **Charlie (Cyberpunk GM):** "Position-in-space is not a layer like plane or timeline. It is the continuation of physical containment past the scale seam, where things stop being *inside* and start *floating*. Model it as a layer, whether a fifth `entity_frame` axis or a tenant-configurable kind, and you inherit layer semantics: 'nearest explicit row wins', possibly multi-valued, target must be a frame. Each of those is wrong for a docked ship. The Späti needs no coordinates, and Ceres needs no street address. Only a containment-shaped tree whose precedence yields to containment, with precision on the edge and optional forever, gives both for free. If a later design folds space into a generic mechanism, it must re-prove the docking case first."

<!-- -->

> **David (D&D GM):** "A portal is not a relation between two places; it is a *thing* that sits somewhere, has a command word nobody told you, can be locked, broken, or carried in a backpack, and leads somewhere else. Every design that tried to express it as an edge kind or an axis ended up needing an optional reified entity beside it, and therefore two ways to find the same portal. The first slice must ship connection-as-entity, even if with only two endpoint columns and no time, because the day portals become 'an axis with in_address=false' is the day 'what can I reach from this cellar' needs a UNION across mechanisms. Mirrors are connections too, not prototypes: an Ethereal echo is coterminous with Greyhawk City, it is not a kind of Greyhawk City."

<!-- -->

> **Eve (worldbuilder):** "Every axis in world-model.md was lifted from a specific genre: spheres from Spelljammer, planes from D&D, a multiverse from Marvel. A fixed platform list is therefore a list of whose fiction Lorenzo supports. I accept a platform-owned list for v1 only because the storage is shaped so a tenant-defined axis is one more row, not a migration. If a later slice puts 'one position per axis' back into a primary key, or names axes in a CHECK constraint, it has quietly decided that settings nobody has written yet are out of scope. That decision deserves its own ADR, not a side effect."

<!-- -->

> **Frank (programmer):** "Frank dissents from treating 'axes as data' as the destination the fixed set merely approximates. Addresses are traversed, not looked up. Their cost and correctness depend on shape rules (cardinality, cyclicity, precedence against containment) that the planner, the indexes and the test suite have to know at build time. A tenant-configurable rule is a tenant-configurable query plan and a tenant-configurable API shape. If B is ever built, it should be its own RFC with its own migration project. It should not be presumed 'additive' because the axis name happens to sit in a lookup table."

<!-- -->

> **Grace (cozy author):** "An unused world axis must cost a tenant nothing it can observe: no rows, no form fields, no response keys, no words in the UI. A single-setting story is the common case, not the edge case. Any future change — axes-as-data, time, variants — that materializes a default plane, timeline, clock or epoch 'so the join works', or that turns a disclosure on tenant-wide because one campaign used it, breaks this invariant and should be rejected on that ground alone. Absence means 'not modeled', never 'unknown' and never 'default'."

<!-- -->

> **Heidi (security architect):** "Every integrity hole found in this debate, in shipped code and in five of eight pitches, had the same shape: a foreign key that referenced a row without also referencing its tenant, silently checked with RLS off. Postgres will not catch this for us, and review has already missed it repeatedly. I accept a fixed axis set for v1 only because the bridge keeps the door to tenant-defined axes open *additively*. But the scope column must be non-null from day one, and a global lookup table must be read-only to the app role. If either condition is dropped as 'later hardening', I withdraw my support: that is how the original hole got in."

## What each participant gave up

| Persona | Gave up |
| --- | --- |
| Alice | "Zero new tables" for space, since space needs its own table. Tenant-defined axes, multi-position, braided timelines. Speed of change: a homebrew axis waits for a platform ADR, and she fields "why can't I just add it?". One more upfront ADR (B0) before any user-visible slice. |
| Bob | Players never see the full cosmology of their stuff: a Bag of Holding's Astral interior stays hidden while carried, and a GM who wants it known uses item information. The server-built English summary; bot and web word the four states themselves and can drift. Accepting a tombstone table he originally opposed. |
| Charlie | DB-enforced containment/space exclusivity under the majority no-trigger shape. Computed comms lag and distances in v1, because the locator is a later sub-slice. Multi-valued spheres: Luna can't be in both "EarthGov jurisdiction" and "Lunar Free Port". A "Blackwall depth" axis becomes nested plane frames or waits for a platform ADR. |
| David | Time travel within one timeline ("the party is in 1358 DR of the canon timeline") is not representable in v1. No per-endpoint time on connections yet. One generic mechanism across all axes: portals, space, frames and variants are four shapes. Tenant-invented axes, for now. |
| Eve | Her own tenant-defined axes in v1, if the bridge ships. Axis-as-entity. Changing a rule freely: tightening can fail with a 409. Per-axis coordinate dimensions. The "Physical" pseudo-axis. The claim that two repositories' "Plane" axes stay distinct by default. |
| Frank | Tenant-defined axes. More than one position per axis. Braided timelines. Per-edge coordinates in v1. Every new axis costs a migration, an ADR and possibly a new structural pattern. If D1 goes his way, a real new trigger on `containment`, a hot table. |
| Grace | One thing in two places on one axis means two entities. A custom axis needs a platform ADR. Her `exclude_none` trick; the address is opt-in. Under her D1 preference, a space auto-clear trigger on `containment`. |
| Heidi | Tenant-defined axes in v1. One relation table for everything. Rule immutability via `RESTRICT`. The four-table retrofit moves out of this work into B0, which she prefers anyway. "Innovative" as a goal: the bridge is deliberately boring on the surface. |

## Time and causality — the remaining open question

All eight agree that time stays out of the first slice. What they converged on is the *shape* of the question, not an answer.

**The question, in three parts:**

1. **Attachment.** Does in-fiction time attach to *frames* as clocks (rate, offset, or explicitly timeless), to *entities* (a near-lightspeed ship, Charlie's relativistic comms), or to both?
2. **Comparability.** Is there one canonical in-fiction order with per-frame mappings into it, or only frame-local clocks related by explicit, sparse, possibly absent sync points (Eve's partial order), with a campaign's "now" as just one more frame?
3. **History and events.** Do the current-state tables (`containment`, `entity_frame`, `knowledge`) become time-versioned ("where was the *Kalte Mamsell* on day 40", bitemporal validity intervals)? Or does history live in first-class in-fiction **event** entities, stamped at *(frame, frame-local ordinal)* and related by an acyclic `causes` relation? Timeline branching ("B diverges at event E") and causality both depend on this. It is not a detail. It is the same missing concept as [RFC 0001](0001-core-domain-data-model.md)'s open question #4 ("facts") and [docs/domain/entities-knowledge-and-visibility.md](../domain/entities-knowledge-and-visibility.md)'s "who knows what, and as of when."

Two related questions also came up:

- **Play order vs. in-fiction order** (David). Lorenzo may need to record the table's experienced sequence separately from fictional chronology. "Did the party know this before they went back in time?" depends on play order.
- **What a branch reads before time exists** (Frank, Alice). Without a divergence point, a branch timeline can only read its parent's *current* state, minus its shadows. If a spellbook moved in the Prime timeline after B branched, B sees the new location. Every design here has this property, prototype-only designs included; only a time model can freeze a branch at its divergence point.

**Invariants the first slice must not break (agreed):**

- No time column on `entity_frame`, `spatial_position`, `containment` or `connection_endpoint` in v1, and no NOT NULL time column ever on a placement table.
- Absent time data means "not modeled", never "timeless" or an implicit epoch; there is no seeded "Prime" or epoch row.
- No global clock is assumed anywhere in the schema.
- Time attaches per position and per connection *endpoint*, never per connection or per entity row. A time rift's two ends have two different times, which is why `connection_endpoint` is one row per end.
- "Where is my stuff *now*" stays answerable with no time argument.

**Invariant still contested:** whether "one position per axis" may be a primary key (D2). This decides whether history later means changing a constraint or adding a separate table.

## Decision

Open. To reach one, these need deciding, in this order:

1. **Accept the shared baseline**, and B0 in particular, as its own ADR, which is a prerequisite whichever candidate wins. The live `PUT …/container` gap should be fixed on its own track, not wait for this RFC.
2. **Candidate 1 or Candidate 2.** If Candidate 2, first have Heidi's nil-scope FK design (T2) reviewed on its own, since only its author has checked it.
3. **D1** (space as its own tree or a fifth axis), plus the trigger-vs-precedence enforcement question within it.
4. **D2** (whether one-position-per-axis may be a primary key). This is forced by the choice in step 2 if Candidate 2 wins.
5. D3 and D4 can wait for the timeline-variant sub-slice.

## Proposed sub-slices (once decided)

Following this repo's smallest-tested-vertical-slice practice, each is its own ADR and milestone. None starts until the step before it is decided and scoped.

1. **B0: composite tenant FKs.** `UNIQUE (id, tenant_id)` on `entity`; retrofit `containment`, `entity_prototype`, `ownership` and the other entity edges via `NOT VALID` → `VALIDATE`; add the CI catalog check. Amends ADR 0015/0016.
2. **Frames and placement.** `frame`, `entity_frame` (and `world_axis` if Candidate 2); the batched `world_address(uuid[])` function; the ADR 0046 non-participation test; and the RFC 0024 table-list additions.
3. **Player read.** `GET …/whereabouts?relative_to=`, plus the `where` block on `owned-by` groups and the loot-bot `/inventory` headings.
4. **GM read.** `GET …/entities/{id}/address`, with the empty-tenant short-circuit.
5. **Position in space.** Whatever D1 decides; per-edge precision (locator) is a later sub-slice after that.
6. **Connections.** `connection` + `connection_endpoint`, plus "what can I reach from here".
7. **Timeline variants.** `entity_variant`, deciding D3 and D4.
8. **A separate time/causality RFC**, starting from the three-part question above.

## Not in scope

- Time, clocks, history, events and causality. They are named precisely above but not designed.
- Tenant-defined axes, under either candidate. Candidate 2 only keeps them reachable.
- Per-edge spatial precision: coordinates, orbits, distances, comms lag.
- Any web or bot UI for placing things on axes. This RFC fixes the read contracts (`/whereabouts`, `/address`), not the authoring surface. Placement is its own action and never a new field on existing create/edit forms (Grace).
- Changing `containment`'s semantics. It stays the physical axis, cycle-tolerant, exactly as ADR 0016 describes, amended only by B0 (and by D1's trigger if that is chosen).

## Consequences

Easier:

- "Where is X" gets one answer across every axis, from one batched call. Players get it without learning any vocabulary.
- Two published cosmologies can share a tenant without their axes colliding.
- Portals become ordinary, knowledge-gated, stat-bearing things.
- A single-setting story pays nothing.

Harder:

- B0 comes first and delays the first user-visible slice.
- Four new small tables each have their own semantics.
- Every future axis needs either a platform ADR (Candidate 1) or a carefully specified registry path (Candidate 2).

Given up by the design, whichever candidate wins:

- Tenant-invented axes in v1.
- Multiple positions per axis.
- Braided timelines.
- Time travel within one timeline.

Gained:

- The debate surfaced a real cross-tenant reference gap in shipped code, and a rule (every FK carries its tenant, checked in CI) that closes that whole class of bug for everything built afterwards.
