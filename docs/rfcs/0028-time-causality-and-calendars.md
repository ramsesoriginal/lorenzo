# RFC: How should in-fiction time, causal order, and calendars be modeled, so that "who knew what, as of when" always has exactly one answer?

Status: proposed — Decision open

## Context

[docs/domain/world-model.md](../domain/world-model.md) leaves time deliberately unresolved: "every one of these axes can keep time differently… a plane can sit outside time entirely, a ship traveling near light speed experiences time differently than the world it left, and parallel timelines aren't necessarily synchronized at all." It goes on: "exactly how far this needs to be modeled — a shared 'true' timeline vs. many independent local ones, and how causality gets tracked across them — is genuinely open… it's the kind of thing that needs an RFC once it's actually being built." [docs/domain/entities-knowledge-and-visibility.md](../domain/entities-knowledge-and-visibility.md) is just as explicit about the other half. Knowledge is "a fact about a specific character at a specific point in the story's timeline, not a global flag", and how that gets represented is "genuinely unbuilt design space." This RFC covers both.

[RFC 0026](0026-world-model-axes-and-address.md) (proposed, Decision open) designs the five non-containment world-model axes and ends by handing this RFC a precise question in three parts:

1. **Attachment:** does time attach to frames, to entities, or to both?
2. **Comparability:** is there one canonical order, or only local clocks joined at sparse sync points?
3. **History and events:** do current-state tables become time-versioned, or does history live in first-class events?

It adds two related questions: play order versus in-fiction order, and what a branch reads before time exists. It also fixes invariants this RFC must not break:

- no time column on any placement table in v1, and never a NOT NULL one;
- absent time data means "not modeled", never "timeless" and never an implicit epoch;
- nothing is seeded;
- no global clock is assumed in the schema;
- time attaches per position and per connection *endpoint*.

The requirements this RFC was asked to meet:

- **Non-linear time is first-class.** That covers per-plane and per-location time speeds, relativistic dilation, time travel (including arriving before you left), branching timelines, and places outside time.
- **Causal ordering is real, especially for knowledge.** Quoting the brief: "two knowledge facts (or two events) must always be comparable — 'X happened before Y' can never be ambiguous or contradictory, even across branching timelines, time travel, or locations with wildly different local clocks."
- **Calendars are a separate layer on top.** Every location can have its own calendar: month counts and lengths, weekday cycles, moons, leap and intercalary rules, named events. Calendars stay independent of how the underlying order works.
- **Nice to have:** reuse [donjon's Fantasy Calendar Generator](https://donjon.bin.sh/fantasy/calendar/) instead of hand-authoring calendars. It has no documented export format, only a Save/Restore JSON of one state.

Whatever is proposed has to live inside what is already decided:

- shared schema with `tenant_id` and `FORCE ROW LEVEL SECURITY` on every tenant table ([ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md), [ADR 0021](../adr/0021-restricted-app-role-for-rls-enforcement.md));
- the entity/component core ([ADR 0012](../adr/0012-entity-table.md));
- the acyclic prototype graph ([ADR 0015](../adr/0015-entity-prototype.md));
- physical containment ([ADR 0016](../adr/0016-containment.md));
- the static knowledge model ([ADR 0028](../adr/0028-knowledge-and-group-membership.md));
- RFC 0026's frames, connections and B0 composite-tenant-FK baseline;
- [RFC 0024](0024-repositories.md)'s repositories.

It must compose with the other five axes, not replace or duplicate them.

### How this was produced

This design came out of a structured, adversarial debate among four independently researched perspectives, following the precedent of [RFC 0024](0024-repositories.md) and [RFC 0026](0026-world-model-axes-and-address.md). Each perspective was committed to its own needs and no-gos and grounded in the real schema. The debate ran in three rounds:

1. **Independent pitches.** None of the four saw the others.
2. **Adversarial cross-critique**, in two parts. In 2a each participant had to attack at least two pitches on concrete grounds; Ivan and Judy were required to attack each other head-on. In 2b each had to answer, by name, every question put to them, and take a position on six crux questions.
3. **Convergence** against a moderator-synthesized baseline, two candidates and four proposed bridges.

Every design was scored 1–5 on seven criteria: **simple, flexible, pragmatic, best-practice, future-proof, innovative, and fits what's already built**.

| Persona | Role | Core need | No-go |
| --- | --- | --- | --- |
| Ivan | GM who loves time travel and non-linear storytelling | planes outside time, dilation, branching, and arrivals before departure, all as ordinary data without special cases | one universal linear clock; "outside time" as a workaround instead of a first-class state |
| Judy | continuity and causality guardian | one unambiguous, always-comparable order that every event and knowledge fact anchors to | "absolute time" that is secretly `created_at`; any two facts that need ordering turning out incomparable |
| Kevin | the engineer who builds and maintains it | one small general primitive, queryable and incrementally migratable on Postgres + RLS | relativistic math, distributed-consensus machinery, N tables for N time systems, cost on hot reads |
| Liam | calendar pragmatist | data-first per-place calendars (irregular months, custom weeks, moons, intercalary days) that can be imported from donjon | Gregorian-only calendars; conflating "which calendar renders this" with "where this sits in causal order" |

Every pitch had to walk through the same eight stress scenarios. They are referenced throughout.

| # | Scenario |
| --- | --- |
| S1 | Zero cost: a cozy campaign that models no time at all. |
| S2 | Dilation: the *Kalte Mamsell* spends 2 years aboard while 40 pass on Earth; a letter sent in Earth-year 10 chases her. |
| S3 | Outside time: the Astral Plane, where nobody ages; a duel and a secret still happen there. |
| S4 | Branching: timeline B diverges at event E; a spellbook moves in Prime afterwards. |
| S5 | Time travel and bootstrap: Cora learns X in 1500 and tells Yorick in 1480, though Yorick "originally" learned it in 1495. Did Yorick know first? Cora also meets her younger self. |
| S6 | Play order versus story order: a session-12 flashback to before session 1, and "three days ago (story time)" after a real-world week off. |
| S7 | Calendars: Faerûn's Calendar of Harptos and Greyhawk's calendar in one tenant, plus a donjon moon-world with 13 irregular months, a 9-day week and 2 moons. |
| S8 | Knowledge queries: "as of E in timeline B, did Alice's character know?", "who learned X first?", "everything Bob knew on entering the Astral". |

The Decision below is left open. What converged is written up as a shared baseline and two candidates. What did not converge is preserved as named disagreements and verbatim dissents, not smoothed over.

## What "absolute time" can honestly mean

This was the crux of the debate, so here is the outcome up front.

- **A calendar date is not the order.** Cora tells Yorick in 1480 *because* she learned X in 1500, so calendar order would put the effect before its cause.
- **Proper time is not the order either.** Every observer has their own, and two observers' proper times are incomparable, which is Judy's no-go.
- **`created_at` is not the order.** GMs back-fill session notes late, flashbacks are recorded after what they precede, and every RFC 0024 copy walk resets it.

What remains is the order in which recorded causes, travels, lived experiences and GM rulings put events. All four participants ended up at the same shape: **a single, tenant-wide linear extension of that recorded evidence.** Every pair of anchored events compares as exactly one of `before`, `after` or `same` (the same event). Each answer is tagged with the **basis** that decided it:

- `causal`: a path of cause, travel or lived-order links decides it.
- `ruled`: an explicit GM ordering decides it.
- `linearized`: nothing recorded decides it, and the stored order does.

That tag is how the design satisfies Ivan and Judy at once. Judy's "always comparable" is met because no default answer is ever `concurrent`, `looped`, `incomparable` or a set. Ivan's objection, that an arbitrary tie-break must not masquerade as truth, is met because the answer says it was only `linearized`.

Clocks are **coordinates**, not the order. Frames, ships and places each carry one, it can run forward, backward, freely or never, and each event is given readings on it. **Calendars are pure functions** that render a reading on one clock into a date string for the viewer's place. Neither clocks nor calendars are ever consulted to answer "who knew first".

The rounds also showed that the three original ordering primitives were closer than they looked:

- Kevin's Lamport happens-before (a partial order) is the evidence.
- Judy's chronicle key is a stored ruling that respects it.
- Ivan's per-experiencer worldlines are that same evidence, recorded per participant.

## Shared baseline (converged; all four accept)

These held through round 3. Amendments added in round 3 are folded in and attributed where they came from one participant.

- **BL1: Events are entities** (the ADR 0012 subtype pattern), so they carry lore, knowledge-gated information, and prototypes as event kinds ("Duel", "Assassination") for free.
  - Nothing is seeded.
  - A tenant that models no time has zero rows and no new response keys.
  - Hot reads (inventory, `GET /entities/{id}`) never join a time table.
  - The only change to an existing table is `UNIQUE (id, tenant_id)` on `knowledge`, for the composite FK.
- **BL2: The default answer is always comparable.** `compare(a, b)` with no parameters returns exactly one of `before | after | same` plus a basis tag, where `same` means the same event, never "the same hour" (Judy). No default answer is `concurrent`, `looped`, `incomparable`, or a set.
- **BL3: No cycle in the order.** A write that would close one gets a 409 (ADR 0015's rule for anything that must resolve). The check `key(from) < key(to)` on every ordering link is a **database guarantee**: a deferred constraint trigger (Judy). Declared loops are deferred (Bridge 3), but the v1 schema must not rule them out, and that has to be tested (Ivan).
- **BL4: Three orders, never mixed.**
  - In-fiction order is the default.
  - Play order is stored separately and never read by causal queries. The session-12 flashback must not become a causal loop, which is Kevin's attack on Ivan's round-1 "campaign worldline".
  - `created_at` is audit only, never an order, and a key is never derived from it.
- **BL5: A GM ruling is first-class evidence.** "The brawl came before the arrest, same day, time unknown" is an explicit order edge. It fakes neither a date (an invented hour) nor a cause (an invented causal link).
- **BL6: Clocks are declared on any entity** (a frame, ship or place) and resolved nearest-ancestor down RFC 0026's chain: containment, then spatial position, then frames. `runs` is one of:
  - `forward`;
  - `backward` (Merlin's tower);
  - `free` (it ticks but promises no direction, and readings there are pure labels);
  - `never` (the Astral: a declared state, never a NULL).

  No clock row means *not modeled*.
- **BL7: Readings are separate from order position.** This was unanimous by round 2b, after Liam and Judy showed that a fused date/order column turns "same day" into "unordered" and prints ordering facts as fake hours.
  - A reading is an authored **range**, `reading_lo <= reading_hi` (a point is lo = hi), so "sometime in Mirtul" and "c. 1350 DR" have a home.
  - Readings sit only on a *ticking* clock, enforced by a composite FK that carries the clock's `ticks` flag.
  - Readings are **never evidence of order at any rank** (Liam), except in Candidate B, which is exactly why it is contested.
- **BL8: Ageing uses a per-leg clock snapshot** on each participation: Ivan's `ridden_clock`, adopted by Judy after Liam showed that resolving from current placement gives a disembarked crewman "40 years". Proper time returns `{min_days, max_days, unrecorded_legs}`:
  - a `never` leg adds 0;
  - a `free` or not-modeled leg adds *unknown*.

  Nothing is silently summed over a gap.
- **BL9: Knowledge.** ADR 0028's `knowledge` keeps its meaning.
  - Timed changes (`learned | forgot`, Judy) go in a side table **anchored to a participation the knower actually has**. This is Ivan's "you can only learn something at a moment you lived", enforced by FK. A group knower must itself be a participant.
  - A `knowledge` row with no timed change answers `known, when: not modeled`, a third explicit value.
  - `knower_player_id` rows stay static.
  - `group_member` has no history, so group knowledge uses today's roster. That strain is named.
- **BL10: Branches.** A timeline frame (RFC 0026) plus `timeline_divergence(timeline, parent, at_event)`.
  - **history(B) is the prefix of the parent's order up to the divergence event, plus B's own events.** A prefix of a linear extension is closed downward under causality, so an effect can never appear without its cause. This is Judy's attack on Ivan's round-1, date-based history, conceded.
  - An event's timeline is an **explicit `entity_frame(axis='timeline')` row written on the event at insert**, reusing RFC 0026's table instead of adding a column.
    - It is **never inherited** through the event's site; otherwise re-placing a tavern would rewrite history.
    - It is immutable outside a retcon endpoint that re-validates history (Judy).
    - A missing row means "not modeled", and such an event belongs to every history.
  - There is no tenant-wide retag, ever. Judy withdrew hers after Kevin showed that one GM's branch would force every campaign in the tenant to declare timelines.
  - Branch membership is an assertion: any re-key that would move an event across a divergence key takes Bridge 2's 409 path (Kevin).
- **BL11: Every time write takes a per-tenant advisory lock** (Kevin).
  - That covers inserts, re-keys and acknowledgements.
  - It closes the race class that ADR 0015's `entity_prototype_reject_cycles` trigger has today (migration `8fd1b287598a`).
  - Writes to calendar tables skip it, because they never affect order (Liam).
- **BL12: The calendar layer is Liam's, in full.** It is detailed under [The calendar layer](#the-calendar-layer-shared-by-both-candidates).
  - Display is keyed by the **viewer's place**, and the epoch by **(calendar, clock)**.
  - Rendering is a pure `packages/calendar-engine`.
  - donjon and Fantasy-Calendar imports are draft-first.
  - Calendars are never consulted for order. A plain `compare` carries dates only as annotations. Only an explicit `compare?by=date&clock=` compares by date, and it may honestly answer `same_day` or `overlapping`. Knowledge as-of queries never read dates.
- **BL13: A continuity report**, Judy's idea, taken up by all four. It lists every order flip, every acknowledged reading inversion, and every event recorded late in play but placed early in the story.
- **BL14: Placement tables stay current-state.** No time column goes on `containment`, `entity_frame`, `spatial_position` or `connection_endpoint`. Their history is events, so RFC 0026's D2 "one-position-per-axis as a PK" stays viable. "Where is my stuff *now*" never takes a time argument.

### RFC 0026's three-part question, answered

1. **Attachment.** Time attaches in four places:
   - **Order** attaches to events.
   - **Clocks** attach to any entity, uniformly (frames, ships, places), and resolve per position like placements.
   - **Readings** attach to (event, clock).
   - **The clock someone actually lived on** attaches to each participation.

   A connection traversal is a departure and arrival pair of events, so the two ends of a time rift carry different readings with no column on `connection_endpoint`. An optional `endpoint_anchor` ("this rift always lands in 1480 DR") is a later sub-slice, which satisfies "time attaches per endpoint".
2. **Comparability.** There is one canonical order per tenant: the stored linear extension of recorded evidence, with every answer tagged by basis. Clocks relate to one another only through events that carry readings on both (sync points), never as the order. Rates are derived, as Δ/Δ between sync points, and never stored as a per-plane dilation formula.
3. **History and events.** History lives in first-class events. Current-state tables are never time-versioned. Knowledge history is the `learned | forgot` side table. Placement history is a later `event_move` sub-slice.
4. **Play order versus story order.** Play order is its own table, keyed by campaign and session ordinal, and excluded from the causal order.
5. **What a branch reads before time exists.** history(B) is exact for *events* from the first slice. Until `event_move` ships, *placement* reads in a branch still show current state, a named strain every pitch shared. RFC 0026 found the same property in its own designs.

## Candidate designs

Round 3 converged on **Candidate A**. All four accept it, and three prefer it. **Candidate B** is Ivan's preferred design, preserved as a minority candidate. Its gap to A narrowed sharply in round 3; see [What still separates A and B](#what-still-separates-a-and-b).

### Candidate A — "Ruled chronicle" (preferred by Judy, Kevin, Liam; accepted with conditions by Ivan)

The stored key is the verdict. Every piece of recorded evidence must agree with it, and that is checked row-locally.

```sql
-- after RFC 0026 B0 (entity UNIQUE (id, tenant_id)); every table: tenant_id NOT NULL,
-- ENABLE + FORCE RLS tenant policy, composite (…, tenant_id) FKs, listed in RFC 0024's
-- repository read-policy and copy-walk lists. Nothing seeded.
CREATE TABLE clock (                          -- an entity that keeps time (frame, ship, place)
  entity_id  uuid PRIMARY KEY,
  tenant_id  uuid NOT NULL,
  runs       text NOT NULL CHECK (runs IN ('forward','backward','free','never')),
  ticks      boolean GENERATED ALWAYS AS (runs <> 'never') STORED,
  UNIQUE (entity_id, tenant_id), UNIQUE (entity_id, tenant_id, ticks),
  FOREIGN KEY (entity_id, tenant_id) REFERENCES entity (id, tenant_id) ON DELETE CASCADE);

CREATE TABLE event (                          -- ADR 0012 subtype
  entity_id      uuid PRIMARY KEY,
  tenant_id      uuid NOT NULL,
  chronicle_key  numeric NOT NULL,            -- the verdict; fractional (insert-between); non-unique,
                                              --   ties broken by entity_id
  UNIQUE (entity_id, tenant_id),
  FOREIGN KEY (entity_id, tenant_id) REFERENCES entity (id, tenant_id) ON DELETE CASCADE);
CREATE INDEX ON event (tenant_id, chronicle_key, entity_id);

CREATE TABLE event_participant (
  id               uuid PRIMARY KEY,          -- D2: Ivan's surrogate id; Kevin prefers PK (event_id, entity_id)
  event_id         uuid NOT NULL,
  entity_id        uuid NOT NULL,             -- a character, ship, letter, group…
  tenant_id        uuid NOT NULL,
  lived_pos        numeric NOT NULL,          -- this entity's own lived order: evidence, row-checked
                                              --   against chronicle_key, never an FK target (Kevin)
  clock_entity_id  uuid,                      -- BL8 snapshot of the clock they lived this leg on;
                                              --   any kind (a 'never' leg adds 0); NULL = not modeled
  UNIQUE (event_id, entity_id),               -- v1; relaxing it is Bridge 4's one-entity option
  UNIQUE (id, entity_id, tenant_id));

CREATE TABLE event_link (
  from_event_id  uuid NOT NULL,
  to_event_id    uuid NOT NULL,
  tenant_id      uuid NOT NULL,
  kind           text NOT NULL CHECK (kind IN ('causes','travel','order')),
  PRIMARY KEY (from_event_id, to_event_id));
  -- deferred constraint trigger under the BL11 lock: key(from) < key(to)  (BL3)

CREATE TABLE event_reading (                  -- a LABEL, never order evidence
  event_id                   uuid NOT NULL,
  clock_entity_id            uuid NOT NULL,
  tenant_id                  uuid NOT NULL,
  clock_ticks                boolean NOT NULL DEFAULT true CHECK (clock_ticks),
  reading_lo                 numeric NOT NULL,
  reading_hi                 numeric NOT NULL CHECK (reading_lo <= reading_hi),
  inversion_acknowledged_at  timestamptz,     -- Bridge 1 (Judy)
  PRIMARY KEY (event_id, clock_entity_id),
  FOREIGN KEY (clock_entity_id, tenant_id, clock_ticks)
    REFERENCES clock (entity_id, tenant_id, ticks));   -- no readings on the Astral, by construction
CREATE INDEX ON event_reading (clock_entity_id, reading_lo);

CREATE TABLE timeline_divergence (            -- BL10
  timeline_entity_id         uuid PRIMARY KEY,  -- composite FK to RFC 0026 frame(axis='timeline')
  parent_timeline_entity_id  uuid NOT NULL,
  at_event_id                uuid NOT NULL,
  tenant_id                  uuid NOT NULL);

CREATE TABLE knowledge_change (               -- BL9: when an ADR 0028 knowledge row was learned/forgotten
  knowledge_id      uuid NOT NULL,
  participant_id    uuid NOT NULL,
  knower_entity_id  uuid NOT NULL,
  tenant_id         uuid NOT NULL,
  change            text NOT NULL CHECK (change IN ('learned','forgot')),
  PRIMARY KEY (knowledge_id, participant_id),
  FOREIGN KEY (knowledge_id, knower_entity_id, tenant_id)
    REFERENCES knowledge (id, knower_entity_id, tenant_id) ON DELETE CASCADE,
  FOREIGN KEY (participant_id, knower_entity_id, tenant_id)          -- you can only learn at a moment
    REFERENCES event_participant (id, entity_id, tenant_id)          --   you actually lived
    ON DELETE RESTRICT);                      -- D4: Kevin argues NO ACTION

CREATE TABLE event_session (                  -- play order (BL4); never read by causal queries
  event_id            uuid NOT NULL,
  campaign_entity_id  uuid NOT NULL,          -- campaign.entity_id already exists
  session_ordinal     numeric NOT NULL,
  tenant_id           uuid NOT NULL,
  PRIMARY KEY (event_id, campaign_entity_id));
-- + calendar, calendar_use, calendar_reckoning (see "The calendar layer")
```

That is eight time tables and three calendar tables, and the count stays the same however many time systems a tenant uses.

**The write path.** Endpoints place an event with `after: <event>`, `before: <event>`, or `at: <reading>`.

- `at` is only a **suggestion**, Judy's "Rule R": place the event right after the last event in the target history whose reading on that clock is at or below the given one.
- With no anchor at all, the default is "after the actor's latest lived event". Never `now()`.
- Once placed, editing a reading never touches the key. It can only raise Bridge 1's inversion check (Liam).
- Re-keys use incremental topological ordering (Pearce–Kelly), bounded to the affected key window rather than to history, and every flipped pair is reported (Bridge 2).

**Reads.** `compare(uuid[], uuid[])` is one batched `SECURITY INVOKER` function (Kevin).

- Any evidence path from a to b runs only through events whose keys lie between the two, so the walk that computes the basis is **bounded to that key interval**.
- It is never a tenant-wide view and is never called on a hot read.
- "What did K know as of E in timeline T" returns one of `known`, `not known` or `known, when: not modeled`. It reads K's `learned`/`forgot` changes within K's lived past as of E (by `lived_pos` and travel links) intersected with history(T).

**Conditions attached in round 3.** None of these was contested by another participant, except where a D-number says so.

- *Ivan:*
  - **A1.** Participations get a surrogate `id`, so one entity at one event twice stays one additive step away (D2).
  - **A2.** No endpoint ever writes `chronicle_key` directly. Rule R placements and GM drags are stored as `event_link(kind='order')` rulings, so the key is always rebuildable from evidence (modulo `entity_id` ties), and a property test pins `rebuild(evidence) = stored keys`. *Nobody else reviewed this condition. It is the first thing to check (see the Decision).*
  - **A3.** An inversion explained by a `travel` link is ordinary data: no 409 and no acknowledgement, and the continuity report lists it as travel, not as a slip.
  - **A4.** Loops use Bridge 3(a), never fork-only.
  - **A5.** A pair that only the key decides is tagged `linearized`, never `causal`.
- *Judy:*
  - The key-ordering check stays in the database (BL3).
  - No key ever comes from `created_at`.
  - The flip report names the affected *knowledge answers* (knower and information), not just event pairs.
- *Kevin:*
  - `lived_pos` as per-entity evidence. A linearized flip may never reorder one entity's `lived_pos`, or cross a divergence key.
  - `compare` is bounded to the key interval.
  - The lock covers re-keys and acknowledgements.
- *Liam:*
  - Readings and reckonings carry the `clock_ticks` referencing column. This FK to a generated column has never been run, so the ADR pins it with a test on `postgres:17-alpine`, the version `infra/docker-compose.yml` uses.
  - The participation clock snapshot is unrestricted by kind.
  - Date placement is a one-time suggestion.
  - The calendar slice ships before clocks.

**Self-meeting (S5):** young Cora is an ordinary NPC entity in v1. See Bridge 4.

**Loops:** see Bridge 3.

### Candidate B — "Evidence-derived verdict over worldlines" (preferred by Ivan)

The GM writes only evidence. The key is **derived** from ranked evidence, cached by the service, and never written by an endpoint.

```sql
clock(entity_id PK, tenant_id, kind text CHECK (kind IN ('metric','retrograde','free','atemporal')), …)
event(entity_id PK, tenant_id, order_key numeric NOT NULL)            -- cache; service-maintained only
worldline_step(id uuid PK, entity_id, pos numeric NOT NULL, event_entity_id,
               ridden_clock_entity_id, tenant_id,
               UNIQUE (entity_id, pos) DEFERRABLE)                    -- per-experiencer lived order
event_stamp(event_entity_id, clock_entity_id, reading_lo, reading_hi, tenant_id)
order_ruling(earlier_event_id, later_event_id, tenant_id)             -- GM ruling (BL5)
play_step(campaign_id, pos, event_entity_id, tenant_id)               -- never read by causal_past
timeline_divergence(…)                                                -- as in A
knowledge_change(knowledge_id, step_id → worldline_step(id) ON DELETE RESTRICT, change, …)
-- + the same calendar tables
```

**Derivation.** Evidence is ranked: causal (worldline adjacency and links, taken transitively) > **date** (same history, same directed clock, disjoint ranges) > GM ruling > play order > `entity_id`, which is tagged `arbitrary`. Each rank is added only where it doesn't contradict a stronger one, and the result is topologically sorted. A new ruling or date that contradicts stronger evidence gets a 409; it is never dropped silently. Ivan amended this in round 3.

**Self-meeting:** native. One entity can take part in one event twice (two steps), and a bare question defaults to the latest occurrence.

**Loops (later):** a declared fixed-past rift. Ivan now prefers Bridge 3(a) to condensing strongly connected components.

**Conditions others attached to B:**

- *Judy* accepts B if:
  - **B1:** play order is removed from the ranks. As ranked, a date-less session-12 flashback sorts after sessions 1–11, which breaks S6 by construction.
  - **B2:** a date-versus-cause conflict raises a 409.
  - **B3:** re-derivation diffs the cache and reports every flip.
  - **B4:** the self-meeting default is tagged `occurrence: latest`.
- *Liam* rejects B **unless rank 2 (date) is dropped.** With it:
  - a date typo fix reorders the verdict;
  - two date labels outrank an explicit GM ruling, which breaks BL5;
  - "what does the calendar say" and "what happened first" stop being independently answerable.
- *Kevin* rejects B for v1:
  - The rank-by-rank derivation is greedy and order-dependent, so two replays of the same evidence can produce different keys unless the insertion order is pinned too.
  - Date evidence implies O(n²) pairwise constraints per clock.
  - `UNIQUE … DEFERRABLE` can back neither `ON CONFLICT` nor an FK.
  - Nothing in the repo derives state this way.

### What still separates A and B

Once A carries Kevin's `lived_pos` (each entity's lived order as its own evidence), Ivan's surrogate participation id (the self-meeting kept one step away) and Ivan's A2 (the key rebuildable from evidence), A has absorbed most of B. Three differences remain:

1. **Dates as order evidence.** B ranks a disjoint pair of readings on one directed clock above a GM ruling. A never lets a reading decide order; it only flags inversions (Bridge 1).
2. **Whether the key is authoritative or a cache.** This dissolves if A2 is accepted.
3. **Whether meeting your younger self is native in v1** (B) or an NPC stopgap until RFC 0026's D3 variants (A).

Judy's proposal for settling A versus B: measure the write cost on a realistic 200-session fixture, not argue it on taste.

## The calendar layer (shared by both candidates)

Liam's design, adopted in full by the other three by round 2b.

### Storage and resolution

```sql
CREATE TABLE calendar (                       -- ADR 0012 subtype: lore, knowledge-gating, RFC 0024 copy
  entity_id   uuid PRIMARY KEY,
  tenant_id   uuid NOT NULL,
  definition  jsonb NOT NULL CHECK (definition->>'format' = 'lorenzo.calendar/1'),  -- Pydantic-validated
  UNIQUE (entity_id, tenant_id), /* composite FK to entity */);

CREATE TABLE calendar_use (                   -- DISPLAY: "dates seen from here render in calendar K"
  entity_id           uuid NOT NULL,          -- place, frame, ship, or a campaign's entity
  calendar_entity_id  uuid NOT NULL,
  tenant_id           uuid NOT NULL,
  rank                smallint NOT NULL DEFAULT 0,
  masked              boolean  NOT NULL DEFAULT false,   -- stop inheriting K from here down
  PRIMARY KEY (entity_id, calendar_entity_id));          -- deliberately NO ticking FK

CREATE TABLE calendar_reckoning (             -- EPOCH: "on clock C, calendar day 0 is reading X"
  calendar_entity_id  uuid NOT NULL,
  clock_entity_id     uuid NOT NULL,
  tenant_id           uuid NOT NULL,
  clock_ticks         boolean NOT NULL DEFAULT true CHECK (clock_ticks),
  day_zero            numeric NOT NULL,
  PRIMARY KEY (calendar_entity_id, clock_entity_id),
  FOREIGN KEY (clock_entity_id, tenant_id, clock_ticks) REFERENCES clock (entity_id, tenant_id, ticks));
```

- **Display is keyed by place, and the epoch by (calendar, clock), in two separate tables.** Liam's round-2a attack found a failure in each other design:
  - Keying the epoch on a place (Ivan, Judy) lets the same calendar carry two conflicting epochs, rendering one event as 1492 DR in Baldur's Gate and 1491 DR in Waterdeep.
  - It also silently applies Toril's epoch to a Feywild glade with its own clock.
  - Keying display on the clock (Kevin) shows Greyhawk CY dates to every Faerûn player when both worlds share a Material Plane clock.
- **`calendars_at(uuid[])`** is a batched `SECURITY INVOKER` function.
  - It walks the same chain as clocks (containment, spatial position, frames), with the campaign entity as a last fallback.
  - It **unions** `calendar_use` rows, ordered by (distance, rank), and a `masked` row cuts off inheritance for that calendar.
  - Rows never inherit through prototypes, since they are positions (RFC 0026 baseline).
  - Because display has no ticking FK, a party in the Astral still sees "back home it's Midsummer" in Harptos, reckoned on Toril's clock.
- **Four render outcomes:**
  - exact: "3rd of Mirtul, 1492 DR";
  - range: "sometime in Mirtul 1492 DR";
  - outside time: "outside time (Astral Plane)", bracketed as "after 3 Mirtul, before 9 Mirtul 1492 DR (Toril reckoning)" where the entry and exit carry readings;
  - not modeled: no response key at all.
- **The first `jsonb` column in the schema.** A grep of `apps/api/src/lorenzo_api/models/` and `apps/api/migrations/versions/` finds no existing `jsonb`; the moderator verified this. Liam's case: a calendar is read whole, evaluated in Python, and never joined into or traversed. It is closer to `payload_document` than to `stat_definition`, and normalizing it would mean six tenant tables, each with RLS, composite FKs and a copy-walk entry, for no query benefit. He would accept validated `text` instead.

### The definition shape (`lorenzo.calendar/1`)

A calendar is an ordered list of **segments**, each a month or a festival.

- `kind: "festival"` means the segment gets no month ordinal.
- `in_week: false` means the weekday doesn't advance across it.
- These are **two separate flags**. Harptos's festivals sit outside both the months and the week. Greyhawk's festival weeks sit outside the months but *inside* the week (Richfest 4, 576 CY is a Godsday).
- `when` is a structured periodic rule (Shieldmeet: `{"every": 4}`), losslessly mappable from Fantasy-Calendar's `"400,!100,4"` interval strings.
- Days are numbered, never named, so nobody types 365 day names.
- The same document also covers eras, year names, alternative year counts (`reckonings`), moons (`period`, `new_on_day`), recurring holidays, and time of day.

An abbreviated Harptos:

```json
{"format": "lorenzo.calendar/1",
 "week": {"length": 10, "names": null, "label": "tenday", "reset": "segment"},
 "segments": [
  {"key": "hammer", "name": "Hammer", "aka": ["Deepwinter"], "days": 30},
  {"key": "midwinter", "name": "Midwinter", "days": 1, "kind": "festival", "in_week": false},
  "… Alturiak, Ches, Tarsakh, Greengrass, Mirtul, Kythorn, Flamerule, Midsummer …",
  {"key": "shieldmeet", "name": "Shieldmeet", "days": 1, "kind": "festival", "in_week": false, "when": {"every": 4}},
  "… Eleasis, Eleint, Highharvestide, Marpenoth, Uktar, Feast of the Moon, Nightal"],
 "eras": [{"abbr": "DR", "name": "Dalereckoning", "from_year": 0}],
 "formats": {"month": "{d_ord} of {segment}, {y} {era}", "festival": "{segment}, {y} {era}"}}
```

Worked checks from Liam's round 1, re-derived by the moderator:

- *3rd of Mirtul 1492 DR* is calendar day 545,077: 1,492 × 365 + 373 Shieldmeets + 122 days before Mirtul + 2.
- On Greyhawk's calendar, Richfest 4, 576 CY is day 209,849. It is a Godsday, and both Luna (period 28) and Celene (period 91) are full, as the setting has it.

### The engine and the importers

`packages/calendar-engine` is a pure, DB-free Python package, in line with AGENTS.md's "generic code becomes its own package". It provides:

- `to_date` and `to_day`;
- `parse`, including relative input ("3 days ago") and ranges derived from what was typed ("1492 DR" is the whole year, "c. 1350 DR" is ± `circa_years`);
- `format`;
- `moons`;
- `mean_year`.

`POST …/calendars:import?from=donjon|fantasy-calendar` returns a **draft** plus `warnings[]` and `choices[]`, and persists nothing until the author confirms.

Liam checked the donjon mapping against donjon's own `/fantasy/calendar/control/compiled.js`. The moderator has not independently re-fetched it, and Ivan's and Kevin's fetches were blocked. Its Save/Restore keys are `year_len, events, n_months, months, month_len, week_len, weekdays, n_moons, moons, lunar_cyc, lunar_shf, year, first_day, notes`.

| donjon | Lorenzo |
| --- | --- |
| `months` + `month_len` (keyed by name) | month segments; duplicate names warn, since they collide in donjon's own dict |
| `year_len` | validated against the segment sum (donjon pads the last month) |
| `week_len`, `weekdays`, `first_day`, `year` | a continuous week (`reset: never`), with `anchor = (first_day − year·year_len) mod week_len` |
| `lunar_cyc`, `lunar_shf` | `period` and `new_on_day = lunar_shf − first_day` (see below) |
| `notes{"812-7-14": …}` | asks, per note: a recurring holiday (the default), or a one-off *event* handed to the time layer |
| `events` | dropped: random flavour seeded by donjon's PRNG, not structure |

**donjon cannot supply** leap rules, weekless or intercalary days, eras, year names or hours, because those fields don't exist there. Its presets are Earth, Eberron, Golarion and Greyhawk; there is no Harptos. A Harptos import therefore arrives without Shieldmeet, and the author adds one `when` flag.

**A finding worth keeping:** donjon's moon epoch is `year·year_len + first_day + doy`. So an importer that copies `lunar_shf` straight into a phase offset is off by `first_day` days, which is what Ivan's and Kevin's round-1 sketches both did. The Greyhawk preset has `first_day: 0`, so **a Greyhawk-only test fixture passes with the bug in place**. The primary fixture must be a save with a non-zero `first_day`, such as Liam's moon-world (`first_day: 4`, year 812), with Greyhawk second. A second importer handles Fantasy-Calendar JSON, where `intercalary` maps to `in_week: false`.

## Bridges (proposed by the moderator in round 3; all four accept, with the amendments shown)

- **Bridge 1: an inverted reading gets an acknowledgeable 409, never a database veto.** This settled a three-way split: Judy's DB veto on directed clocks, Ivan's 422 unless the step is a named rift, and Kevin and Liam's 201 plus a warning.
  - The service answers 409 `reading_order`, and the write proceeds with `?acknowledge=reading_order`.
  - The acknowledgement is stored on the reading (`inversion_acknowledged_at`, Judy) and in `audit_log` ([ADR 0063](../adr/0063-tenant-activity-log.md), Kevin).
  - It fires only on **disjoint and inverted** ranges (`new.hi < prev.lo`), and it is direction-aware on `backward` clocks.
  - It never fires on `free` clocks, never on an inversion explained by a `travel` link or connection traversal (Ivan), and never on an edit that *removes* an inversion.
  - RFC 0024 copy walks and confirmed imports acknowledge in bulk into the continuity report (Liam).
  - No database constraint ever enforces it.
  - Judy's honest cost: "calendars may now lie within a timeline, but only on the record." Backward travel no longer forces a branch, so Ivan's fey "back an hour before we left" is ordinary data.
- **Bridge 2: the flip policy.**
  - A pair decided only by the key (`linearized`) may re-order automatically when new evidence decides it.
  - The write reports every flipped pair and every affected knowledge answer, and the continuity report records them.
  - A pair decided by cause or ruling never flips without a 409 and an explicit retraction or `?confirm`.
  - No flip may cross a divergence key or reorder one entity's `lived_pos` (Kevin).
  - So nothing flips silently, and nothing anyone *asserted* flips unconfirmed. Ivan's framing: answers only ever flip *upward* in strength.
- **Bridge 3: declared loops, deferred but not foreclosed.**
  - v1 rejects every cycle.
  - The later slice uses option (a), accepted by all four: a first-class loop-closing record, **excluded from the order**. It is one record, so there is no B′/B″ chain of branches (Ivan's objection to fork-only), and `origin_of(X)` returns `bootstrap: no recorded origin`.
  - Any answer whose deciding path would cross the closure is tagged `basis: loop` (Ivan).
  - The closure may join two occurrences of one entity, not only an entity and its variant (Ivan).
  - Condensing the loop inside the order, option (b), is rejected (Judy, Kevin, Liam; Ivan withdrew it). Fork-only, option (c), survives only as what (a) looks like plus an annotation.
  - *Where the closure lives* is disputed (D3).
- **Bridge 4: meeting your younger self is deferred, split 2–2.** Ivan and Liam want one entity at one event twice. Judy and Kevin want a variant entity.
  - v1 ships neither formally: young Cora is an ordinary NPC.
  - The decision rides with RFC 0026's slice 7 (D3 there).
  - Conditions: the participation schema must keep "she *is* Cora" one additive step away (Ivan, via A1), and the D3 decision must say how a variant's age is computed (Liam), so the UI can still show "Cora (14)".

## Worked scenarios (Candidate A; B's differences noted)

- **S1: zero cost.** Zero rows in every new table. `knowledge` gains only a UNIQUE constraint, no field. As-of endpoints short-circuit on `NOT EXISTS (SELECT 1 FROM event)`. No clock, trunk timeline or epoch is materialized, and no response key appears.
- **S2: dilation.** Earth and the *Kalte Mamsell* each get `clock(runs='forward')`.
  - Departure: Earth 0, ship 0. Return: Earth 40y, ship 2y. Two sync points.
  - The letter's send S reads Earth 10y. The GM records its receipt Q on the ship at, say, 1.5y (the letter chased the ship). The API offers ≈0.5y by interpolation between sync points, flagged `approximate`. `event_link(S→Q, 'causes')` enforces S ≺ Q.
  - Ageing sums Δreading over each participant's snapshot clock: 2 years for the crew, 40 for Earth. A crewman who later disembarks still reads 2, because the snapshot is per leg.
  - There is no dilation formula anywhere.
- **S3: outside time.** The Astral gets `clock(runs='never')`.
  - The FK makes readings there impossible. The Astral is not a NULL.
  - Enter (reading Toril t) ≺ duel ≺ secret ≺ exit (Toril t+3d), by the participants' `lived_pos` and the key.
  - Two parties who never meet there are ordered only by the key, tagged `linearized`. Kevin conceded to Ivan that ordering the Astral by its own strand had imposed exactly the linear clock the Astral is supposed to lack.
  - Ageing across the stay is 0.
  - A Toril viewer sees the duel as "outside time (Astral Plane), after 3 Mirtul, before 6 Mirtul 1492 DR".
- **S4: branching.** `timeline_divergence(B, Prime, E)`.
  - history(B) is Prime's key prefix up to E, plus B's own events. The spellbook's later move in Prime is not in it.
  - Knowledge learned at or before E is shared; later learning is split per branch.
  - **Strain:** until `event_move`, a *placement* read in B shows current containment, never a guess.
- **S5: time travel.**
  - Prime: Yorick learns X at Y95 (reading 1495), Cora at L (1500), and she departs at D.
  - Her arrival A in B carries reading 1480 and follows `event_link(D→A, 'travel')`. The inversion is explained by travel, so it gets no 409. She tells Yorick at T.
  - "Did Yorick know X before Cora?":
    - in **Prime**: `before`, basis `linearized` (`ruled` under Ivan's A2, which stores the date-suggested placement as an order ruling; under B: basis `date`);
    - in **B**: `after`, basis `causal` (L → D → A → T);
    - **tenant-wide first**: Y95.
  - The dates 1480 and 1500 come back as annotations, never as the sort. Three questions get three stable answers, none contradicting another.
  - **Younger self:** v1 NPC; see Bridge 4.
  - **A stable Novikov loop:** deferred to Bridge 3.
- **S6: play versus story.**
  - The flashback is created `before: <session 1's first event>` (or `at: 1470` as a suggestion), with `event_session(…, 12)`.
  - "Three days ago" is `at: (the actor's latest reading − 3 days)` on their resolved clock. The real-world week is irrelevant, and `created_at` is never read.
  - The continuity report lists the flashback as recorded late but placed early.
  - A slip like "day 57 after day 60" gets Bridge 1's 409 instead of silently corrupting "did my character know that yet?".
- **S7: calendars.**
  - `calendar_use`: Toril → Harptos, Oerth → Greyhawk, the moon-world → its donjon import.
  - `calendar_reckoning`: each calendar on the clock it counts.
  - A Waterdeep viewer sees "Midsummer, 1492 DR". A Greyhawk City viewer sees "Godsday, Richfest 4, 576 CY" if the event carries a reading on a clock Greyhawk's calendar is reckoned on; otherwise the answer is "not reckoned on Oerth's clock", never a guessed date.
  - Moving the event's order changes nothing about its dates. Changing the viewer changes only *which* dates are shown.
- **S8: knowledge queries.**
  - (a) "As of E in B, did Alice's character know the Duke is a lich?" Look for a `learned` change within her lived past as of E, intersected with history(B), with no later `forgot`. The answer is `known`, `not known`, or `known, when: not modeled` for an untimed row.
  - (b) "Who learned X first?" The minimum key over `learned` changes: one answer plus its basis. Ties mean the same event, reported as `same`.
  - (c) "Everything Bob knew on entering the Astral" is (a) over every information row, cut at his entry participation's `lived_pos`, with untimed rows listed separately.

## Scoring

Final round-3 scores (simple / flexible / pragmatic / best-practice / future-proof / innovative / fits what's built):

| Scorer | Candidate A | Candidate B |
| --- | --- | --- |
| Ivan | 4 / 3 / 4 / 4 / 3 / 3 / 5 | 3 / 5 / 3 / 4 / 5 / 5 / 4 |
| Judy | 4 / 4 / 4 / 4 / 4 / 4 / 5 | 2 / 5 / 3 / 3 / 4 / 5 / 3 |
| Kevin | 4 / 4 / 5 / 4 / 4 / 3 / 5 | 2 / 5 / 2 / 3 / 4 / 5 / 3 (rejects for v1) |
| Liam | 4 / 4 / 5 / 4 / 4 / 3 / 5 | 2 / 5 / 3 / 3 / 4 / 5 / 3 (rejects unless rank 2 is dropped) |
| **Median** | **4 / 4 / 4.5 / 4 / 4 / 3 / 5** | **2 / 5 / 3 / 3 / 4 / 5 / 3** |

The spread repeats RFC 0026's lesson. B leads on *flexible* and *innovative*, and A leads on *simple*, *pragmatic*, *best-practice* and *fits*. Ivan's own lower future-proof score for A (3) is specific: in plain A, "lived order *is* key order". Kevin's `lived_pos` condition answers that. The two were written in parallel, so Ivan's scores don't reflect it.

Where each round-1 pitch started (self-score, then the median of the other three participants' round-2a scores):

| Pitch | Shape | Self | Peers (median) |
| --- | --- | --- | --- |
| Ivan, "Worldlines, not clocks" | per-experiencer `worldline_step`; a cycle-tolerant partial order; six-valued `compare`; the caller names the order | 3/5/3/4/5/5/4 | 3/5/3/3/4/5/3 |
| Judy, "One Chronicle" | a tenant-wide UNIQUE `chronicle_key`; cause-before-effect check (I1); readings may never go backwards within a timeline (I2), so past arrival forces a branch | 3/4/4/4/5/4/4 | 3/2/3/3/3/4/3 |
| Kevin, "Marks on strands" | Lamport happens-before over per-strand `pos`; a cycle trigger plus lock; fork on loop | 4/4/5/4/4/3/5 | 4/3/4/4/4/3/5 |
| Liam, calendar layer | a `lorenzo.calendar/1` document; display per place; epoch per (calendar, clock); a pure engine; a verified donjon import | 4/5/5/4/4/3/4 | 4/5/5/4/4/3/3 |

Candidate A is essentially Judy's chronicle, corrected by Kevin's buildability attacks and made honest by Ivan's attack on the `authored` tie-break. It carries Liam's calendar layer unchanged.

## Designs considered and dropped

- **A universal linear clock, or wall-clock `created_at` as story order.** Never pitched; excluded by Ivan's and Judy's no-gos from the start. `created_at` fails S6 in practice (back-filled notes, loot-bot writes, RFC 0024 copy walks), which is also why Judy's round-1 use of it for *play* order was dropped (Kevin).
- **A causal order that tolerates cycles, with `concurrent`, `looped` and `incomparable` answers and a caller-named order** (Ivan, round 1). Judy's attack held:
  - In Ivan's own S5, one question on one clock got three answers ("Yorick first" by date, `concurrent` by causality, `unplayed` by play order).
  - `looped` names a contradiction rather than preventing it.
  - ADR 0015, not ADR 0016, governs anything that must *resolve*.

  Ivan withdrew all three in round 2b.
- **Lamport `concurrent` as a public answer** (Kevin, round 1). Judy showed that two events on the same day on one metric strand came back `concurrent`, so "as of the confrontation, did she know?" had no answer. The only fixes were a fabricated time of day or a fabricated cause. Kevin adopted the stored key.
- **A date column that doubles as order** (Kevin's metric `pos`). It printed ordering facts as fake hours and made a strand's `metric` flag impossible to change after 200 sessions (Liam).
- **A database veto from clock readings** (Judy's I2: readings may never go backwards within a timeline, so arriving in the past forces a branch).
  - Kevin showed it is neither row-local nor race-free: it needs a downward branch walk, and two concurrent inserts can each pass.
  - Liam showed it breaks backward-running clocks, date typo fixes and approximate dates.
  - Ivan showed it forces a new timeline for every fey "same morning" return.

  Replaced by Bridge 1.
- **A tenant-wide retag on first branch, with `event.timeline_entity_id` NULL meaning "trunk"** (Judy, round 1). One GM's branch would force every campaign in the tenant to declare timelines, and the NULL's meaning changed at runtime. It also duplicated RFC 0026's `entity_frame`. Withdrawn and replaced by BL10.
- **An ordered strand for a timeless place** (Kevin's `metric=false` Astral). It imposed a linear clock on the one place meant to have none (Ivan). Replaced by `runs='never'` plus the experiencers' own lived order.
- **A calendar epoch keyed on a place, or display keyed on a clock** (Ivan, Judy, Kevin). See [the calendar layer](#storage-and-resolution).
- **`NULL` for "outside time"** (Liam's round-1 `clock_for`). All three others attacked it under RFC 0026's "absence never means timeless". Replaced by the declared `runs='never'`.
- **Knowledge anchored to a mutable order position** (Ivan's FK to `worldline_step (entity_id, pos)`). Correcting an order either failed or silently cascaded the learning away (Kevin). Replaced by an anchor on the participation's *identity*, never its position (the exact key is D2, the delete rule D4).
- **Play order as the campaign's own worldline** (Ivan, round 1). An ordinary flashback became a causal loop (Kevin). Play order is now its own table, never read by causal queries.
- **Condensing loops inside the order** (Ivan, round 2b; option (b)). Withdrawn in favour of Bridge 3(a).

## Unresolved disagreements

These did not converge and are left for the Decision.

**D1: Candidate A or Candidate B?** The narrowed version of this question is set out in [What still separates A and B](#what-still-separates-a-and-b):

- dates as rank-2 order evidence (Ivan, for; Liam, a rejection; Kevin, against);
- the key as the authority or as a cache (dissolves if Ivan's A2 is accepted);
- the self-meeting as native in v1.

Judy proposes deciding it on measured write cost.

**D2: The identity of a participation.**

- **Surrogate `id`** (Ivan's A1). Knowledge anchors to `participant_id`, and `UNIQUE (event_id, entity_id)` can later be dropped to allow one entity twice.
- **PK `(event_id, entity_id)`** (Kevin). Knowledge anchors to `(event_id, knower_entity_id)`, the identity itself, and a plural answer to "what did Cora know at Z?" is ruled out structurally, per BL2.

This must be decided before sub-slice 3, because `knowledge_change` anchors on it.

**D3: Where a declared loop's closure lives.**

- **An `event_link(kind='closes_loop')` value** (Judy). `kind` is text plus a CHECK, so it is a one-line migration, excluded from ≺ like play order.
- **Its own `event_loop_closure` table** (Kevin). With a `kind` value, every ordering query, trigger, basis walk and history(B) must remember `WHERE kind <> 'closes_loop'`, which is "the service knows" filtering of the core invariant. In a separate table, no ordering query can reach it by accident.

Ivan and Liam accept (a) without taking a side on this.

**D4: `ON DELETE RESTRICT` or `NO ACTION` on the knowledge anchor.**

- Judy and Ivan specified `RESTRICT`, so an anchor is never silently dropped.
- Kevin argues `NO ACTION`. Deleting a character cascades down two paths (`entity → knowledge → knowledge_change` and `entity → event_participant`). `RESTRICT` is checked immediately, so the delete fails or succeeds depending on which cascade Postgres runs first. `NO ACTION` is checked at the end of the statement, and still blocks a direct participant delete.

Only Kevin has examined this. It should be settled by a `test_cascades.py` case, not by argument.

**D5: Smaller calendar questions** (Liam's open list):

- the definition as `jsonb` (the schema's first) or validated `text`;
- `calendar_use` by union plus mask, or nearest-set-wins;
- whether a Greyhawk event seen from Waterdeep also carries its *native* date as a secondary annotation;
- the precision of typed approximate dates (`circa_years`);
- whether calendar definitions vary by copy only, or through prototype or variant inheritance (B's "Regency" era).

**D6: Whether `free` belongs.** All four accepted it in round 3, and Judy offered to drop it if nobody wanted it. It is recorded here only because it was the last clock state to be added, and its ageing rule (unknown, never 0) came from Ivan alone.

## Dissents (verbatim, as each participant asked them to be preserved)

> **Ivan (time-travel GM):** "Every design here keeps the order acyclic, and for v1 I accept that. But a table running *Dark*, *Primer* or *Prisoner of Azkaban* plays one timeline in which the future caused the past. Lorenzo must be able to store that as one timeline, not as a fork the UI renames, nor as an NPC who happens to share Cora's face. The order may exclude the closing link; the data must not. I ask the RFC to keep two rules. First, no endpoint ever writes the order key: every position must be rebuildable from recorded evidence. Second, 'outside time', 'runs backward' and 'went back in time' are declared, ordinary data, never errors to be acknowledged."

<!-- -->

> **Judy (continuity guardian):** "Every design here ended up agreeing that 'did my character know that yet?' gets one answer. Keep it that way. The day any endpoint's default returns `concurrent`, `looped` or a set, or lets a server timestamp decide story order, continuity is lost, and it is lost silently. I accepted that an inverted date becomes an acknowledged warning instead of a database veto. I accepted it only because the order itself stays total and database-guarded: no cycle can be stored, and every flip is caused by a recorded fact and reported. If a later slice puts loops inside the order, or lets an acknowledgement excuse a cycle, 'never contradictory' becomes a promise the schema no longer keeps."

<!-- -->

> **Kevin (engineer):** "I'm the one paged when a tenant with forty thousand events and one time traveller can't load an 'as of' page. So every time write takes the tenant lock. Every check is an index probe. Every compare is a batched, key-bounded, invoker-rights function. No tenant-wide recursion, no time join on a hot read. The key is a ruling, not a fact, and the API must say which. A character's own lived order is evidence and must never be reshuffled by a linearization. Cycles never enter the order; a declared loop lives in its own table, where no ordering query can reach it by forgetting a WHERE clause. If staying consistent depends on 'the service knows', it isn't consistent."

<!-- -->

> **Liam (calendar pragmatist):** "A date is a label someone wrote on an event, not a witness to what caused what. Every design here that let readings decide order — I2 as a veto, a fused `pos`, dates as rank-2 evidence — turned a typo fix into a reordering and a backwards-running tower into a paradox. Keep them apart. Causes and GM rulings decide the order. The viewer's place decides which calendars render it, and each calendar is reckoned per (calendar, clock). Never consult a calendar to answer 'who knew first', and never let a reading silently move an event. And nobody should type 365 day names: import donjon, correct its moon epoch, and let authors write 'sometime in Mirtul'."

## What each participant gave up

| Persona | Gave up |
| --- | --- |
| Ivan | Cycle tolerance in the order, in v1 and (under Bridge 3(a)) for good: loops live beside the order, not in it. `concurrent`, `looped` and `incomparable` as answers, and "name your order". A purely derived, never-stored order, which he accepts as a stored key under his A2. Knowledge anchored on an order position. Play order as a worldline. An event's timeline inherited through its site. The place-keyed calendar epoch. Causation only through carriers. Point-only readings. A one-entity self-meeting in v1. |
| Judy | A UNIQUE key (ties now break by `entity_id`). The database veto on inverted readings, and with it "the calendar never lies within a timeline" and "backward travel always forces a branch" (Ivan won the fey case). One `authored` label, split into `ruled` and `linearized`. `created_at` as play order. The tenant-wide retag and the timeline column. Her calendar keys. Ageing from current placement. Loops as two branches. Insisting the order be stored rather than rebuildable. |
| Kevin | `concurrent` as a public answer; it is now at most a basis tag. His recursive cycle trigger, replaced by Judy's row-local key checks ("hers is better"). The fused date/order `pos`. Strands as *the* primitive. An ordered Astral. His calendar display rule and donjon importer. "A stored ruling never flips." The self-meeting in v1. |
| Liam | `NULL` for "outside time". "Any clock can be reckoned": now only ticking ones. 201 plus a warning, in favour of Bridge 1's 409. The one-entity self-meeting in v1. "Name your order" as a general parameter, narrowed to `by=date&clock=`. One-off named events inside a calendar: they belong to the event layer. A free hand on locking, in exchange for calendar writes being exempt. |

## Open questions (genuinely open, beyond D1–D6)

1. **`group_member` history.** Group knowledge "as of" uses today's roster. What does a group's learning give a member who joined later?
2. **Timed player-level knowledge.** `knower_player_id` rows are static. Should out-of-character knowledge ever anchor to play order?
3. **Branch placement reads.** `event_move` or `containment_change`, and what B shows for the spellbook before it ships. This is the same limitation RFC 0026 names.
4. **Cross-campaign and cross-cosmology `linearized` answers.** Show them, hide them, or scope the key per campaign? Every candidate puts two unrelated campaigns in one tenant into one order that nobody asked for.
5. **RFC 0024 copies of events.** How a repository's canon history is spliced into a tenant that already has one, and who chooses the interleaving. Ivan notes that A2's rebuild-from-evidence would make an affine key splice unnecessary.
6. **Key growth and re-key cost.** When and how fractional keys are renormalized in crowded gaps, under the lock. Whether Pearce–Kelly's O(window) holds on a realistic 200-session fixture. Whether the key-bounded basis walk ever needs a materialized reachability index. Measure before promising any of it.
7. **The loop slice.** Exactly which answers get `basis: loop`, and D3's shape.
8. **The self-meeting.** Bridge 4 and RFC 0026 D3, including how a variant's age is computed.

## Decision

Open. To reach one, decide these in this order:

1. **Accept the shared baseline (BL1–BL14) and the calendar layer.** Both are prerequisites whichever candidate wins. So is RFC 0026's B0 (composite tenant FKs), which is itself still undecided there.
2. **Review Ivan's A2 on its own.** A2 says no endpoint writes the key, and the key is rebuildable from evidence. Only its author has checked it. If accepted, the stored-versus-derived half of D1 goes away.
3. **D1, Candidate A or B.** Narrowed to dates as order evidence and a v1-native self-meeting. Judy proposes measuring write cost on a 200-session fixture rather than arguing it.
4. **D2, the participation's identity.** Needed before timed knowledge (sub-slice 3).
5. **D4.** Settle by a cascade test in sub-slice 3's ADR.
6. D3, Bridge 4 and D5 can wait for their own slices.

## Proposed sub-slices (once decided)

Following this repo's smallest-tested-vertical-slice practice, each is its own ADR and milestone. None starts until the step before it is decided and scoped. The order is Kevin's round-3 plan (for Candidate A), amended by Liam's condition that calendars ship before clocks.

0. **Prerequisites.** RFC 0026 B0, plus `UNIQUE (id, tenant_id)` on `knowledge`.
1. **Calendars, standalone.**
   - `packages/calendar-engine`, `calendar` and `calendar_use`.
   - Format, parse, weekdays, moons and holidays, with no clocks yet.
   - Fixtures for Harptos, Greyhawk and a non-zero-`first_day` donjon save, none of them seeded.
   - This can run in parallel with slice 2.
2. **The order core.**
   - `event` (with `chronicle_key`) and `event_link` (`causes`, `order`).
   - The tenant lock, the deferred key-order trigger, and batched `compare()` with basis tags. `GET …/events/compare`.
   - Tests: cycle gets a 409, a two-connection race, RLS isolation, `test_cascades.py`, and a CI check that every function is `SECURITY INVOKER`.
3. **Timed knowledge.**
   - `event_participant` (with `lived_pos` and the clock snapshot) and `knowledge_change`.
   - `GET …/characters/{id}/knowledge?as_of=`, answering known / not known / untimed.
   - Decides D2 and D4.
4. **Play order.** `event_session`, relative authoring ("three days ago"), and continuity report v1.
5. **Clocks and readings.**
   - `clock`, `event_reading` and `calendar_reckoning`.
   - Bridge 1, date-suggested placement, ageing, and `GET …/events/{id}/dates`.
   - Pins the generated-column FK with a test.
6. **Importers.** donjon and Fantasy-Calendar, draft-first.
7. **Branches.** `timeline_divergence`, history(B), and the `travel` link kind. After RFC 0026's frames slice.
8. **Later, each its own RFC or ADR:**
   - the self-meeting (Bridge 4, with RFC 0026 D3);
   - `endpoint_anchor`;
   - `event_move` with `/address?as_of=`;
   - declared loops (Bridge 3, deciding D3).

## Not in scope

- **Relativistic or any other physical time math.** Rates are derived only, as Δ/Δ between sync points, and interpolation is a flagged hint, never stored truth.
- **Any web or bot UI** for placing events, authoring calendars, or reading the continuity report. This RFC fixes the data model and the read contracts, not the authoring surfaces.
- **Placement history** (`event_move`), timed `group_member`, and timed player-level knowledge.
- **Declared loops and the self-meeting.** Shaped here, deferred to their own slices.
- **Merging or splicing two repositories' canon histories** (RFC 0024), beyond naming the question.
- **Any change to `containment`, `entity_frame`, `spatial_position` or `connection_endpoint`.** This RFC adds no column to any of them.

## Consequences

Easier:

- "Did my character know that yet?" gets exactly one answer, with its basis, across branches, time travel, dilation and timeless planes.
- Knowledge can only be recorded at a moment the knower actually lived, and the database enforces it.
- Every place can render dates in its own calendars, including Gregorian-shaped, festival-heavy and multi-moon ones, and calendars can be imported rather than typed.
- A cozy single-setting story pays nothing.

Harder:

- **Eight new time tables and three calendar tables.** Each is small, but the as-of read semantics (lived past crossed with branch history) take real care to get right.
- **Writes carry the complexity.** Re-keys under a per-tenant lock, flip reports and the continuity report all live on the write path. Their cost has to be measured, not assumed.
- **Calendars can now be wrong within a timeline.** Judy's honest cost of Bridge 1: an acknowledged inversion stays on the record rather than being refused.

Given up by the design, whichever candidate wins:

- A cycle inside the order, ever. Declared loops live beside it.
- `concurrent` as an answer. Unrelated events are ordered, and say they were only `linearized`.
- Dates deciding order, under Candidate A.
- A native self-meeting and stable loops in v1.

Gained:

- **One `compare` for every client.** The debate replaced three competing ordering primitives with one stored linear extension of recorded evidence, carrying a basis tag.
- **A verified donjon import path, and a bug caught before shipping.** The import mapping is based on donjon's actual code, and the moon-epoch offset bug would have passed a Greyhawk-only test.
- **A new column type, flagged openly.** The schema's first `jsonb` column is called out rather than slipped in.
