# RFC: How should in-fiction time, causal order, history, and calendars be modeled, so that "who knew what, and where everything was, as of when" always has exactly one answer?

Status: proposed — Decision open

This RFC has two parts, debated by the same four participants.

- **Part 1** (most of this document) designs time itself: the causal order, clocks, knowledge "as of", and calendars.
- **[Part 2](#part-2-history-of-containment-ownership-group-membership-and-existence)** was added at the requester's follow-up: "now that we have the possibility of having time for knowledge, we should also have the same for containment, group membership and ownership… and maybe even 'existence'". It extends part 1's history pattern to those four relations and amends part 1 in a few places. Each amendment is marked where it lands.
- **[Amendment: declared clock relations](#amendment-declared-clock-relations)** was added after both debates, at the requester's request, and **was not debated**. It lets a GM declare "plane X runs twice as fast as clock Y", optionally with an anchor ("day 0 here is day 0 there"), so a crossing's readings on the other clock are filled in automatically.

The [Decision](#decision), [sub-slices](#proposed-sub-slices-once-decided), [Not in scope](#not-in-scope) and [Consequences](#consequences) sections cover both parts.

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
  - `group_member` has no history, so group knowledge uses today's roster. That strain is named. *Closed by Part 2's `membership_change` ([PB-groups](#groups-access-while-a-member)).*
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
3. **History and events.** History lives in first-class events. Current-state tables are never time-versioned. Knowledge history is the `learned | forgot` side table. Placement, ownership, membership and existence history follow the same pattern, designed in [Part 2](#part-2-history-of-containment-ownership-group-membership-and-existence). That replaces the `event_move` sub-slice part 1 originally named.
4. **Play order versus story order.** Play order is its own table, keyed by campaign and session ordinal, and excluded from the causal order.
5. **What a branch reads before time exists.** history(B) is exact for *events* from the first slice. Until Part 2's change tables ship, *placement* reads in a branch still show current state, a named strain every pitch shared. RFC 0026 found the same property in its own designs. Part 2 closes this for every recorded move: B shows the spellbook where it was before Prime moved it.

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
                                              --   against chronicle_key, never an FK target (Kevin);
                                              --   Part 2's P2-D1 may add lived_claim ('lived'|'placed')
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
    ON DELETE NO ACTION);                     -- D4, resolved in Part 2 (PB6)

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
- "What did K know as of E in timeline T" returns one of `known`, `not known` or `known, when: not modeled`. It reads K's `learned`/`forgot` changes within K's lived past as of E, **computed through** history(T) and travel links (by `lived_pos`). It is not intersected with history(T): that would drop what Cora learned in Prime before she travelled into B. Judy caught this drafting error in part 2, and all four agreed. One `lived_past()` function serves knowledge and Part 2's history reads alike.

**Conditions attached in round 3.** None of these was contested by another participant, except where a D-number says so.

- *Ivan:*
  - **A1.** Participations get a surrogate `id`, so one entity at one event twice stays one additive step away (D2).
  - **A2.** No endpoint ever writes `chronicle_key` directly. Rule R placements and GM drags are stored as `event_link(kind='order')` rulings, so the key is always rebuildable from evidence (modulo `entity_id` ties), and a property test pins `rebuild(evidence) = stored keys`. *Nobody else reviewed this condition in part 1. It is the first thing to check (see the Decision).* **Amended in Part 2:** a date-suggested placement is stored as `event_link(kind='placed')` and reads as `linearized`, not as an `order` ruling. Liam's point: otherwise a bulk import turns thousands of date labels into ruling-strength evidence, and "ruled" masquerades as a GM decision nobody made. All four accept this. The key stays rebuildable from evidence, which is what A2 asked for.
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
  - There is no physics formula anywhere. If the GM *knows* the ratio ("20 Earth years per ship year"), they can declare it once as a [clock relation](#amendment-declared-clock-relations). The receipt's missing reading is then derived exactly, instead of offered as an interpolation hint.
- **S3: outside time.** The Astral gets `clock(runs='never')`.
  - The FK makes readings there impossible. The Astral is not a NULL.
  - Enter (reading Toril t) ≺ duel ≺ secret ≺ exit (Toril t+3d), by the participants' `lived_pos` and the key.
  - Two parties who never meet there are ordered only by the key, tagged `linearized`. Kevin conceded to Ivan that ordering the Astral by its own strand had imposed exactly the linear clock the Astral is supposed to lack.
  - Ageing across the stay is 0.
  - A Toril viewer sees the duel as "outside time (Astral Plane), after 3 Mirtul, before 6 Mirtul 1492 DR".
- **S4: branching.** `timeline_divergence(B, Prime, E)`.
  - history(B) is Prime's key prefix up to E, plus B's own events. The spellbook's later move in Prime is not in it.
  - Knowledge learned at or before E is shared; later learning is split per branch.
  - **Strain in part 1 alone:** a *placement* read in B shows current containment, never a guess. Part 2 closes this: see [S11](#worked-scenarios-part-2).
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
  - (a) "As of E in B, did Alice's character know the Duke is a lich?" Look for a `learned` change within her lived past as of E, computed through history(B) and travel links, with no later `forgot`. The answer is `known`, `not known`, or `known, when: not modeled` for an untimed row.
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

Only Kevin had examined this in part 1. **Resolved in Part 2 ([PB6](#part-2-baseline-converged-all-four-accept)).** All four adopted `NO ACTION` for every history anchor, subject and target. Deleting a history-bearing subject becomes *end*, and `?purge=true` is the only erasure path. A `test_cascades.py` case, including a whole-tenant purge, still pins it.

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

1. **`group_member` history.** *Closed by Part 2:* group knowledge is access while a member, and memory is an explicit anchored `learned`. See [Groups](#groups-access-while-a-member).
2. **Timed player-level knowledge.** `knower_player_id` rows are static. Should out-of-character knowledge ever anchor to play order?
3. **Branch placement reads.** *Closed by Part 2 for every recorded move:* `containment_change` with a captured `from`, read through history(B). See [S11](#worked-scenarios-part-2).
4. **Cross-campaign and cross-cosmology `linearized` answers.** Show them, hide them, or scope the key per campaign? Every candidate puts two unrelated campaigns in one tenant into one order that nobody asked for.
5. **RFC 0024 copies of events.** How a repository's canon history is spliced into a tenant that already has one, and who chooses the interleaving. Ivan notes that A2's rebuild-from-evidence would make an affine key splice unnecessary.
6. **Key growth and re-key cost.** When and how fractional keys are renormalized in crowded gaps, under the lock. Whether Pearce–Kelly's O(window) holds on a realistic 200-session fixture. Whether the key-bounded basis walk ever needs a materialized reachability index. Measure before promising any of it.
7. **The loop slice.** Exactly which answers get `basis: loop`, and D3's shape.
8. **The self-meeting.** Bridge 4 and RFC 0026 D3, including how a variant's age is computed.

## Amendment: declared clock relations

*Added after both debates, at the requester's request. **Not debated or reviewed by the four participants.** Treat it as a proposal on the same footing as an unreviewed round-3 condition (see the [Decision](#decision)).*

### The gap it fills

Part 1 relates two clocks only through **sync points**: events that carry a reading on both clocks. It derives a rate as Δ/Δ between two or more of them, and offers interpolation only as a flagged hint. So in the requester's example:

- the party leaves on day 17 of clock 1;
- they spend six days on a plane whose clock runs twice as fast;
- they come back.

Nothing fills in "day 20" on clock 1. There is only one sync point, so there is no rate to derive, and the GM has to type it. A GM who *knows* how two clocks relate has had no way to say so once.

### The relation

```sql
-- after part-1 slice 5 (clock, event_reading). tenant_id NOT NULL, ENABLE + FORCE RLS,
-- composite (…, tenant_id) FKs, RFC 0024 lists, all FKs NO ACTION (PB6). Nothing seeded.
ALTER TABLE clock ADD directed boolean GENERATED ALWAYS AS (runs IN ('forward','backward')) STORED,
                  ADD UNIQUE (entity_id, tenant_id, directed);        -- clock is itself a new RFC 0028 table

CREATE TABLE clock_relation (
  clock_entity_id            uuid NOT NULL,     -- e.g. plane X
  reference_clock_entity_id  uuid NOT NULL,     -- e.g. clock 1 (the Material Plane)
  tenant_id                  uuid NOT NULL,
  rate                       numeric NOT NULL CHECK (rate <> 0),
                                                -- days on this clock per day on the reference:
                                                --   2.0 = X runs twice as fast; negative = runs against it
  anchor_reading             numeric,           -- OPTIONAL anchor: this clock reads anchor_reading
  anchor_reference_reading   numeric,           --   when the reference reads anchor_reference_reading
  clock_directed             boolean NOT NULL DEFAULT true CHECK (clock_directed),
  reference_directed         boolean NOT NULL DEFAULT true CHECK (reference_directed),
  CHECK ((anchor_reading IS NULL) = (anchor_reference_reading IS NULL)),
  CHECK (clock_entity_id <> reference_clock_entity_id),
  PRIMARY KEY (clock_entity_id, reference_clock_entity_id),
  FOREIGN KEY (clock_entity_id, tenant_id, clock_directed)
    REFERENCES clock (entity_id, tenant_id, directed),
  FOREIGN KEY (reference_clock_entity_id, tenant_id, reference_directed)
    REFERENCES clock (entity_id, tenant_id, directed));
```

- **Rate only** says how fast two clocks run relative to each other. **Rate plus anchor** also pins their day counts together. "Day 0 here is day 0 there" is `anchor_reading = 0, anchor_reference_reading = 0`.
- **Only directed clocks** (`forward`, `backward`) can be related, and the composite FKs enforce it:
  - a `free` clock promises no rate, which is the whole point of `free` (Feywild drift);
  - a `never` clock has no readings at all.

  The service checks that the rate's sign agrees with the two clocks' declared directions.
- **One relation per ordered pair.** The reverse direction is implied (rate 1/r, anchor swapped), and the service refuses to store both directions.

### How readings get derived

When an event has a reading on one clock and a read asks for it on a related clock, the reading is **derived at read time, never stored**. Fixing a wrong rate therefore corrects every derived date at once. The sources, strongest first:

1. **An explicit reading** on that clock. It always wins.
2. **The nearest sync point, plus the rate.** Take the latest event in the traveller's lived past (computed through history(T) and travel links) that carries readings on both clocks. Add the elapsed time since then, multiplied by the rate. A portal crossing whose GM gave both sides' dates is such a sync point. So a **rate-only** relation becomes fully automatic after one crossing has been dated on both sides.
3. **The anchor, plus the rate**, when there is no nearer sync point. With an anchor, derivation is automatic from the very first event.
4. **Part 1's interpolation hint** (Δ/Δ between sync points, flagged `approximate`), when no relation exists.
5. Otherwise, **not reckoned** on that clock. The value is never guessed.

Derived readings keep their range: `reading_lo` and `reading_hi` are each converted. Responses tag them `derived`, as interpolation is tagged `approximate`, and calendars render them like any other reading.

**Chains compose.** X → Y and Y → Z give X → Z: rates multiply, and anchors map through. `derive_reading(event_ids uuid[], clock uuid)` is a batched `SECURITY INVOKER` function with a depth cap. It uses a direct relation first, else the shortest path. If two paths between the same pair of clocks disagree, the answer is flagged and listed in the continuity report, never silently picked.

**Explicit readings that disagree.** When an entered reading and the derived value disagree (their ranges don't overlap), the write gets Bridge 1's treatment: a 409 `reading_relation_mismatch`, acknowledgeable with `?acknowledge=`, and listed in the continuity report. No database constraint ever enforces it.

### What it does not change

- **Order.** Readings, derived or not, still never decide order (BL7). Rule R may *suggest* a placement from a derived reading, which is stored as `placed` and reads `linearized`, like any other date.
- **Ageing.** It still sums Δreading over the clock each participant actually lived on (BL8). Derived readings simply fill legs that would otherwise count as `unrecorded_legs`. The party in the example ages six days; the friends they left behind age three.
- **Calendars.** Unchanged. They render a reading on a reckoned clock whether it was entered or derived.
- **Anything, when unused.** No relation rows means part 1's behaviour exactly.

### The requester's example

```text
clock 1: Material Plane (forward)        plane X: its own clock (forward)
clock_relation(X → clock 1, rate 2.0, anchor 0 = 0)       -- "twice as fast; day 0 = day 0"

Departure from the Material Plane / arrival on X:  clock 1 = 17 (entered) → X = 34 (derived, anchor)
Six days on X ("+6 days" on the party's clock X):   X = 40
Return to the Material Plane:                        clock 1 = 17 + 6 ÷ 2 = 20 (derived)
```

**Without the anchor (rate only):**

- The first crossing needs X's own date once (say, X day 1 at arrival). That makes it a sync point.
- The return is then derived as 17 + (7 − 1) ÷ 2 = **day 20**, and every later trip is automatic.

### Scope change, stated plainly

This reverses one line of part 1's Not-in-scope list: "rates are derived only". It does **not** reverse the part-1 no-gos behind that line:

- It is not physics math.
- It is not a bespoke formula per plane (Kevin's no-go). It is one linear relation per clock pair, in one table.
- It never makes a date into order evidence (Liam's).

### Open (for whoever reviews this)

1. **A rate that changes over time** ("the rift slowed after the Sundering"). Options:
   - v1 keeps one constant relation per pair, and a GM uses sync points or a `free` clock;
   - a later version adds validity between events.
2. **Trip-relative durations with no absolute count on X at all** ("they were gone six days of *their* time", when X has no calendar and no anchor). This may need a duration-only authoring shortcut that doesn't invent X's date.
3. **Whether a derived reading may serve as a sync point** for further derivation, or only explicit readings may. It is safest to allow only explicit readings, so derivation never builds on itself.

## Part 2: history of containment, ownership, group membership, and existence

### Why this belongs in the same RFC

Part 1 gave *knowledge* a history: a `learned | forgot` side table anchored to a participation the knower actually lived. The requester's follow-up was to do the same for **containment, ownership and group membership, and maybe even existence**, as part of the same topic.

Part 1 already pointed there:

- its open question 1 (`group_member` history) and 3 (what a branch shows for the spellbook);
- the `event_move` sub-slice it deferred;
- [docs/domain/client-views.md](../domain/client-views.md)'s "ledger of ownership — tracking ownership provenance over time" as a future direction.

Three things already in the codebase had to be reckoned with:

- **[ADR 0099](../adr/0099-player-facing-change-feed.md)'s `entity_change` feed.** A real-world-time, per-recipient, 90-day notification log of item moves and hand-overs. It is not in-fiction history.
- **Stacks that split and merge** ([ADR 0041](../adr/0041-containment-quantity-and-stacking.md), [ADR 0044](../adr/0044-loot-assignment-split-merge-bulk-assign.md)). A split mints a new entity; a merge deletes one.
- **RFC 0026's baseline.** "Inventory is never filtered by timeline"; "'where is my stuff *now*' never takes a time argument"; its open D3 on "doesn't exist in this timeline".

### How part 2 was produced

The same four participants each started from their converged part-1 positions and ran the same three rounds:

1. **Independent pitches**, each answering seven questions:
   - H1: how history is represented;
   - H2: whose "now" is authoritative;
   - H3: existence;
   - H4: cost and scope;
   - H5: what absence means;
   - H6: who can see history;
   - H7: branches and travel.
2. **Adversarial attacks**, with required pairings aimed at each other's weakest point.
3. **Defence and convergence** against a moderator-synthesized design with five bridges.

New stress scenarios extended part 1's eight:

| # | Scenario |
| --- | --- |
| S9 | Zero cost: the cozy campaign again, plus a busy loot-bot campaign that never asks an as-of question. |
| S10 | "Where was the Sword of Kas when Alice learned the Duke is a lich?" "Where was the *Kalte Mamsell* on day 40?" A 50-gold stack split 20/30 and partly merged back: what is the 20's provenance? |
| S11 | Branch placement: the spellbook moves study → vault in Prime after divergence E. What does B show? Then a thief takes it from the study in B. |
| S12 | Ownership ledger: who owned Ashfang before Alice? And the bootstrap watch: old Cora gives it to young Cora, who carries it back and gives it to *her* younger self. |
| S13 | The Harpers learned X at G. Alice joins at J and leaves at K. What does she know, and when? |
| S14 | Existence: the Duke dies, the tavern burns, Ashfang is forged in 1350 and destroyed in 1402, and Alice drinks a potion. In B the Duke never dies. |
| S15 | Retroactive edits: "the ring was in the vault all along since 1400"; a move recorded at the wrong event. |
| S16 | Drift: a loot-bot `/give` (a real-world write with no in-fiction event) moves a tracked item. |

Round 1 converged unusually fast on the *shape*. All four independently proposed four per-relation change tables, rejected versioned rows, and kept current state authoritative for "now". Rounds 2 and 3 were about what makes that shape honest. Every participant moved on at least four points. Every bridge was accepted by all four, with amendments. What is left open is small, and it is named below.

### Part-2 baseline (converged; all four accept)

- **PB1: Four per-relation change tables.** They are `containment_change`, `ownership_change`, `membership_change` and `existence_change`.
  - There is **no generic `relation_change`**. RFC 0026's "four semantics" argument (Frank) applies to history even more strongly:
    - containment is single-parent with quantity arithmetic;
    - ownership is single-valued;
    - membership is a set;
    - existence is a lifecycle with lineage.

    Each has its own chain rule, and a generic table would lose them all.
  - There are **no validity intervals.** In chronicle-key terms they would put order positions on placement rows (BL14), they would rot on every Bridge 2 re-key, and a shared branch prefix would need intervals duplicated per history.
  - No existing table gains a column. BL14 holds, so RFC 0026's D2 primary key survives.
- **PB2: `from` and `to` on every change, each with a declared state.** Liam originally proposed `into`/`out` rows with no `from`. Ivan showed that B could then only answer `not_modeled` for the spellbook, even though the server held "study" at write time. Liam conceded.
  - **State values.** `from_state` and `to_state` are `contained | uncontained | unrecorded` (for ownership: `owned | unowned | unrecorded`). **`unrecorded` is a declared state, never a NULL**; this was Liam's attack, and all four accepted it.
    - "Ashfang vanished from the vault in 1402 and resurfaced in Blackstaff Tower in 1480" is `vault → unrecorded`, then `unrecorded → tower`.
    - That asserts neither "it lay loose for 78 years" nor "it moved vault → tower in 1480", the two lies a NULL-only schema forces.
  - **Where `from` comes from.** On a *head* write, `from` is captured from the current row, at no authoring cost. On a retroactive or compiled insert, it comes from the lived-order predecessor's `to`. With no predecessor it is explicitly `unrecorded`, never borrowed from today's row: a 1350 span must not claim "moved from where it sits in 1492" (Liam, Kevin, Ivan).
- **PB3: The current row is the head of the subject's *home history*.** This is Judy's design, adopted by the other three.
  - **Home** is an explicit `entity_frame(axis='timeline')` row on the subject. It is untagged by default, which covers every tenant that never branches. It is never inherited.
  - The "now" of any other history is **derived** from the ledger.
  - This replaced Kevin's "last-written key wins, flagged `contested`". Judy showed that it let a timeline-B thief's bag appear in Prime's `/inventory`: a hot read stating a fact false in the reader's own history.
  - It also replaced Ivan's v1 `worldline_fork` 409.
- **PB4: Evented writes, and plain writes that stay plain.**
  - **Evented writes.** Existing routes gain an optional `as_part_of=<event>`, or `at:`/`after:`. An evented write inserts the participation, the change row and the current row **in one transaction**, under BL11's lock. A head write **always** updates the current row.
  - **Plain writes** (loot-bot, inventory-web) touch current state only, as today. They take no lock and write no history.
  - A single-item plain write on a history-bearing subject returns `history: unrecorded_change`. Bulk routes skip that per-item probe, because the gap is structural anyway (Kevin).
- **PB5: Retroactive inserts must chain.**
  - A non-head insert that contradicts a recorded lived-order neighbour gets 409 `ledger_discontinuity`, naming the neighbour. `unrecorded` matches anything.
  - In draft mode (the span compiler, "record the present"), the discontinuity becomes a `choices[]` entry instead of failing the batch (Liam).
- **PB6: End is in-fiction; purge is erasure.**
  - **Ending.** `existence_change(ended)` clears the subject's current containment, ownership and membership rows, **and its `item_instance` subtype row** (Kevin's trick). The `entity` row survives with its lore and its ledger. It drops out of `v_item_instance`, `owned-by`, `/inventory` and `/unowned` without a single hot query learning the word "exists". That honours "inventory is never filtered".
  - **ADR 0044 changes:**
    - a merge whose source has history *ends* it (`absorbed_into`) instead of `session.delete`-ing it, which would cascade the provenance away;
    - `DELETE` of a history-bearing subject becomes *end*.

    Subjects without history behave byte-identically to today.
  - **`?purge=true` is the only erasure.** It computes the flip report from rows still present and writes it to `audit_log` and the continuity report *before* it removes anything.
  - **Every FK is `NO ACTION`**: subject, target and anchor. It is checked at statement end, so tenant purges and multi-path cascades don't race. This resolves part 1's D4.
  - **A target named in others' ledgers** can only be ended, never deleted.
  - **Rejected alternatives:**
    - Kevin's round-1 subject `CASCADE`. Judy showed that deleting the Harpers would silently flip Alice's as-of knowledge, with nothing left to report it from.
    - Judy's round-1 `RESTRICT`. Kevin showed that it is checked immediately, so a tenant purge's outcome depended on cascade order.
- **PB7: The kind of change is an event prototype.** "Forged", "burned", "consumed", "died" and "split" are never an enum (BL1). The only structural columns are `lineage_entity_id` and `lineage_kind` (`split_from | absorbed_into | diverged_from`).
- **PB8: Visibility.**
  - A change is visible to a player only if its **event** is visible to them under ADR 0028. Participation alone isn't enough: Bram, asleep in the room during the secret ring swap, saw nothing.
  - Players **never receive `from` fields**. Otherwise a visible move *out of* a secret hiding place would reveal where it was (Judy).
  - GMs see the full ledger.
  - "Where Bram *thinks* the ring is" stays out of scope. Belief is authored `information` (RFC 0001's open question 1), not history. This matches [RFC 0029](0029-epistemic-status-of-information.md) (proposed separately), which puts a knower's certainty on the `knowledge` edge and a GM's belief in a GM-only `information` row. RFC 0029 relies on this RFC's `learned` changes for "as of when".
  - **Named strain** (Ivan, Judy): present-tense `/inventory` and ADR 0099's feed already reveal possession, so gated history can't make a theft *of Bram's* ring secret. Only a swap to a fake ring entity can.
- **PB9: Opt-in per subject, and absence.**
  - A subject has history if and only if it has change rows. There is no flag, nothing is seeded, and **nothing is backfilled**, on ADR 0099's precedent that unrecorded history can't be reconstructed.
  - A draft-first "record the present at event E" action snapshots current rows.
  - A subject with no rows answers `not_modeled`, with current state attached as a labelled hint, never asserted as of the cut.
- **PB10: Liam's span compiler.** Authors don't hand-write change rows. They write spans:
  - "the sword lay in the vault from c. 1350 to 1402 DR";
  - "the Duke held the Open Lordship 1479–1488".

  `POST …/history/spans?commit=false` (and a CSV/TSV `:import`) then works in five steps:
  1. **Resolve names**, turning ambiguity into `choices[]`.
  2. **Parse dates** through the calendar engine. `circa_years` defaults to 5, settling part 1's D5 item.
  3. **Create one lore-less event per endpoint.** Chained spans share an endpoint.
  4. **Write one `order` ruling per span**: the author's own "from … to". Every other placement is `event_link(kind='placed')`, which reads as `linearized` (the part-1 A2 amendment).
  5. **Later, `absorb`** re-anchors placeholder events onto named ones ("left the vault *during the Heist*").

  Offices are groups: "ruled Waterdeep" is membership in "Open Lord of Waterdeep".
- **PB11: Existence.** "X exists as of cut C in T" means: the latest `existence_change` in X's lived past, computed through history(T) and travel links, at or before C, is `began`.
  - It follows the **chronicle, never dates**: a watch forged in 1600 and carried back to 1480 exists in 1485.
  - No record at all means `not_modeled`, never "always has".
  - Knowledge *about* a thing that doesn't exist yet (a prophecy of Ashfang) is ordinary lore, because knowledge points at `information`.
  - Stack provenance is **per-stack lineage, not per coin**: ADR 0041's units are indistinguishable by design.
  - This also answers RFC 0026 D3's *temporal* half. "Absent in B" is "no `began`, or an `ended`, within history(B)". Variants remain for "differs in B".
- **PB12: Travel carries its contents.** This was Judy's idea. Ivan stole it, Kevin and Liam conceded, and all four accept it.
  - **The rule.** At a `travel` write, every *history-bearing* entity transitively contained in the traveller becomes a participant of both departure and arrival. It is one `INSERT … SELECT` over `entity_access`'s recursive descendant walk (depth 50, cycle guard), under the lock. For a retroactive travel, the contents come from `state_as_of` at the departure (Kevin's amendments).
  - **Why.** Without it, a watch Cora buys in Prime *after* divergence E, then carries into B, has its purchase filtered out of history(B). As-of reads would put it back in the shop while `/inventory` says her pocket. That contradiction sank "rides its container" and the plain `event_id` anchor.
- **PB13: `entity_change` (ADR 0099) is a sibling.** History shares its call sites (`record_change`, beside `record_activity`), never its rows. An evented head write still calls `record_change`, because *now* changed.
- **PB14: What part 2 closes.** Part 1's open questions 1 and 3, the `event_move` sub-slice (replaced), part 1's D4 (resolved), and part 1's A2 (amended to `placed`).

### Schema

```sql
-- after RFC 0026 B0 and part-1 slices 2–3. Every table: tenant_id NOT NULL, ENABLE + FORCE RLS,
-- composite (…, tenant_id) FKs, listed in RFC 0024's lists. EVERY FK NO ACTION (PB6). Nothing seeded.
CREATE TABLE containment_change (
  participant_id         uuid PRIMARY KEY,     -- the SUBJECT's own participation (anchor, below);
                                               --   the key's exact shape follows part 1's D2
  subject_entity_id      uuid NOT NULL,
  tenant_id              uuid NOT NULL,
  from_state             text NOT NULL CHECK (from_state IN ('contained','uncontained','unrecorded')),
  from_parent_entity_id  uuid,
  from_quantity          int,
  to_state               text NOT NULL CHECK (to_state   IN ('contained','uncontained','unrecorded')),
  to_parent_entity_id    uuid,
  to_quantity            int,
  -- split so no comparison can evaluate to NULL (a NULL CHECK passes): Liam's catch
  CHECK ((from_state = 'contained') = (from_parent_entity_id IS NOT NULL)),
  CHECK ((from_state = 'contained') = (from_quantity IS NOT NULL)),
  CHECK (from_quantity >= 1),
  CHECK ((to_state = 'contained') = (to_parent_entity_id IS NOT NULL)),
  CHECK ((to_state = 'contained') = (to_quantity IS NOT NULL)),
  CHECK (to_quantity >= 1),
  FOREIGN KEY (participant_id, subject_entity_id, tenant_id)
    REFERENCES event_participant (id, entity_id, tenant_id),        -- it moved at a moment it was there
  FOREIGN KEY (from_parent_entity_id, tenant_id) REFERENCES entity (id, tenant_id),
  FOREIGN KEY (to_parent_entity_id,   tenant_id) REFERENCES entity (id, tenant_id));
CREATE INDEX ON containment_change (subject_entity_id);
CREATE INDEX ON containment_change (to_parent_entity_id) WHERE to_state = 'contained';   -- "what was in the vault"

-- ownership_change:  same anchor; from_/to_state IN ('owned','unowned','unrecorded') + from_/to_owner_entity_id
--                    (ADR 0025: an owner is any entity); the same split CHECKs.
-- membership_change: anchored to the MEMBER's participation; group_entity_id; change IN ('joined','left').
-- existence_change:  same anchor; change IN ('began','ended'); lineage_entity_id, lineage_kind
--                    ('split_from','absorbed_into','diverged_from'), both-or-neither. Quantities of a split
--                    live on the two containment_change rows, not here.
```

**The anchor is always the subject's own participation.** This generalizes part 1's BL9 FK: a thing can only be moved, change hands, join, leave, begin or end at an event it took part in. Kevin and Liam started from a bare `event_id` anchor and moved, for three reasons:

1. "The ring moved during the royal wedding" while it sat in Undermountain becomes an FK violation.
2. Only participations import a traveller's past through a rift (PB12).
3. Kevin's own part-1 rule, that a linearized flip must never reorder one entity's lived order, needs the subject's changes on its lived line.

The cost is one participation row per change. Liam's example is 600 rows for a 300-row pasted timeline, and all four accepted it.

**Reads.** `state_as_of(subject_ids uuid[], cut_event uuid, timeline uuid)` is one batched `SECURITY INVOKER` function.

- **Per subject and relation,** it takes the latest change in the subject's lived past (through history(T) and travel links) at or before the cut. For containment it then walks up the parent chain *as of the cut*, with part 1's cycle guard and depth cap.
- **Cost:** O(each subject's own changes). Never tenant-wide, never on a hot read.
- **Endpoints:** GM `GET …/entities/{id}/history`, `…/address?as_of=` and `…/whereabouts?as_of=`, plus player reads gated by PB8.
- **Every answer carries a basis:**
  - `ledger`: a recorded change covers the cut.
  - `inferred`: the cut precedes the first change, so the answer is that change's `from`.
  - `unrecorded_window`: a drift gap covers the cut (see below). The answer is the last recorded state, flagged.
  - `not_modeled`: there are no changes at all.
  - A **declared** `unrecorded` state answers "whereabouts unrecorded". That is the author saying *unknown*, and it is distinct from a detected drift (Kevin, Liam).

### Drift: record the truth, never fabricate a moment

This was the hardest part-2 fight. Judy's round-1 **seam** put a deferred constraint trigger on `containment`, `ownership` and `group_member`, so the current row could never differ from the ledger head. To satisfy it, a loot-bot `/give` on a tracked item would auto-create an "offscreen transfer" event. Three attacks landed:

- **Kevin: hot-path cost.** A 40-item loot-bot bulk-move would write an entity, an event and 40 participations and change rows, and block on the per-tenant lock behind any GM re-key. Postgres has no deferred *statement*-level constraint trigger, so "one probe per write" is one probe per row at commit, cascaded deletes included.
- **Liam: `created_at` in costume.** The offscreen event's participations enter everyone's lived order, and lived order is `causal` evidence. So a Discord click on a Tuesday night could decide a causal knowledge answer. That is Judy's own part-1 no-go.
- **Kevin: it hijacks placement.** The fabricated event becomes the characters' "latest lived event", so the GM's next scene is placed after a click.

Judy conceded all three and withdrew offscreen events. The converged rule (Bridge 6):

- A plain write moves current state only.
- The next evented **head** write takes `from` from the current row and **always** updates the current row. That drops Kevin's round-1 "update only if current still equals the old tip", which Judy showed freezes the row out of the story forever after one off-record `/give`.
- So an unrecorded drift is **structural**: the previous change's `to` ≠ this change's `from`. An as-of cut inside that window gets **one** answer, the last recorded state, tagged `unrecorded_window`, and the continuity report lists the window.
- The seam holds at every evented write by construction (one transaction), plus Ivan's property test `heads(ledger) = current` for every subject without a reported gap.
- A plain write on a tracked subject can instead say `?as=correction` (Judy). It rewrites the head's `to` rather than opening a gap, for "the loot-bot entry was a typo, not a move".

### Groups: access while a member

Part 1's BL9 used today's roster for group knowledge. Part 2 split 2–2 on what `membership_change` should mean, then converged 4–0 on **access**:

- **The rule.** Alice knows X "via the Harpers" as of cut C exactly when the Harpers knew X as of C *and* she is a member as of C. This mirrors today's `information_visibility.py`, so the as-of answer and the present-tense visibility read can't disagree.
- **Why not memory.** Judy's and Kevin's round-1 "memory" said she keeps what the group knew after leaving. Ivan's attack settled it: after she leaves, none of *her* participations anchors X, which breaks part 1's "learn only at a moment you lived". It also makes a one-scene double agent download every group secret for good.
- **Memory is always an explicit, anchored `learned`.** On `left`, the UI offers a draft "record what she takes with her" (Liam).
- **A leave is recorded, never silent.** It is a `membership_change`, so any as-of answer it changes is caused by a recorded fact and listed in the continuity report. That is Bridge 2's flip report extended to roster changes, and it answers Judy's "a roster change silently flips a knowledge answer".
- A group with no membership history keeps today's roster, tagged `basis: roster_not_modeled`.

### Worked scenarios (part 2)

- **S9: zero cost.** Both campaigns have zero rows in all four tables. Loot-bot writes run today's statements: no lock, no event, no trigger. `/inventory`'s SQL is unchanged. The only addition anywhere is one indexed `EXISTS` on the merge and delete paths, deciding end versus delete.
- **S10: where was it?**
  - **The Sword of Kas when Alice learned the secret:**
    1. The cut is her `learned` participation.
    2. The sword's latest change at or before it gives the vault (`ledger`).
    3. The vault's own change gives Undermountain. A hop with no record ends the path with `not_modeled`.
  - **The *Kalte Mamsell* on day 40:** "day 40 on the ship's clock" becomes an explicit cut at the last event whose reading is ≤ 40 (Rule R). The response *names* that event, so the date chose a prefix and ordered nothing. Docked is containment. In flight is RFC 0026's `spatial_position`, whose `spatial_position_change` is the same anchored pattern, added in that slice.
  - **The 20 coins:**
    - The split writes `existence_change(S20, began, split_from S50)` plus containment changes `∅ → pouch, 20` and `50 → 30`.
    - A "partial merge back" is ADR 0044's split-then-full-merge: S5 splits off S20, then S5 `ended absorbed_into` S30.
    - So the provenance of the 20 is a lineage walk: 15 still in S20, 5 absorbed into S30. It is per stack, honestly not per coin.
- **S11: branch placement.**
  - Prime records M, study → vault, after E. M's `from` was captured from the current row.
  - **B as of E, and B now:** M ∉ history(B), so the answer is **the study**, `basis: inferred`.
  - **The thief in B:** event T is tagged B. It writes the thief's and the spellbook's participations and `containment_change(from: study (B's state), to: thief's bag)`. No clone, no new slug, no copied lore, no current-row change, because the book's home history is the trunk.
  - B-now is the bag, derived from the ledger. Prime-now and Alice's `/inventory` still show the vault. The letter and bookmark inside it need no rows: in B they are still in the book.
- **S12: the ownership ledger.**
  - **Ashfang:** `GET …/entities/{ashfang}/history` lists `ownership_change` rows in lived order. The row whose `to` is Alice has `from` Bram, at event G ("the duel of 1398 DR", a label).
  - **The bootstrap watch in v1** (young Cora is an NPC, part 1's Bridge 4):
    - old Cora → young-Cora-NPC at Z₁;
    - that NPC later travels, carrying the watch (PB12), and gives it to a younger NPC at Z₂.

    That is an unrolled chain, never contradictory, but one turn of a circle stored as a line, which Ivan's part-1 dissent names. With a one-entity self-meeting plus part 1's Bridge 3(a), the watch would be owned and carried by Cora throughout, with `origin_of = bootstrap`.
- **S13: group membership.** The Harpers learned X at G, Alice joins at J and leaves at K.
  - **As of J:** `known, basis: via_group(Harpers)`.
  - **Before J:** not known, unless she learned it herself.
  - **After K:** group access ends. The leave is recorded, and the continuity report lists the flipped answer. If the GM recorded her briefing at J as her own `learned`, she keeps X.
- **S14: existence.**
  - **The Duke:** `ended` at D, tagged Prime. D ∉ history(B), so in B he exists.
    - Kevin, Ivan and Liam record death as `ended`. If the corpse matters, it is a new entity with a `began` whose event prototype is, say, "Remains".
    - Judy's alternative: a death is a state change (lore), the corpse is still him, and only an explicit `ended` makes him stop existing.
    - Both are expressible, since the event prototype carries the meaning. Which one to use is a per-table authoring choice, not a schema one.
  - **The tavern:** `ended`. Its contents are **not** moved silently. As-of reads flag "parent ended at F", and the span compiler offers to move them to the ruins.
  - **Ashfang:** `began` 1350 and `ended` 1402, with the dates as labels. "Exists as of E?" is a key cut.
  - **Alice's potion:** drinking one of three is a quantity change, 3 → 2. Drinking the last one is `ended` at "Alice drinks" (both participate). That clears its containment, ownership and subtype rows, so it leaves her `/inventory`. The ledger still says "Alice's, until she drank it". ADR 0099's feed shows `deleted` until it gains a `consumed` kind.
- **S15: retroactive edits.**
  - **"In the vault all along since 1400"** is an explicit `order` ruling, the author's own claim, at a new event V. V's change must chain with its lived-order neighbours. A recorded 1410 move *out of the chest* contradicts it, so the write gets 409 `ledger_discontinuity`, naming that change. The retcon endpoint applies the fix as one batch (insert V, rewrite the neighbour's `from`), and the deferred checks validate the final state.
  - **A move recorded at the wrong event** is re-anchored under the lock.
  - Either way, the continuity report lists every ledger edit, every participation inside the rewritten window ("anyone who saw it in the chest in 1405"), and every as-of answer that flipped.
- **S16: drift.** A `/give` is a plain write: current state and an ADR 0099 row, with no history, no event and no lock. Containment writes **never** have to name an event. The next evented head write exposes the gap structurally, and `POST …/history/anchor` can pin it to a real event later.

### Scoring (part 2)

Final round-3 scores for the converged design (simple / flexible / pragmatic / best-practice / future-proof / innovative / fits what's built):

| Scorer | Converged design |
| --- | --- |
| Ivan | 3 / 4 / 5 / 4 / 4 / 4 / 4 |
| Judy | 3 / 4 / 4 / 4 / 4 / 4 / 4 |
| Kevin | 3 / 5 / 4 / 4 / 4 / 4 / 4 |
| Liam | 3 / 5 / 4 / 4 / 4 / 4 / 4 |
| **Median** | **3 / 4.5 / 4 / 4 / 4 / 4 / 4** |

All four score *simple* at 3. That is the honest cost of declared states, chain rules, carried contents and home histories on top of four small tables.

Where the round-1 pitches started (self-score, then the median of the other three participants' round-2 scores):

| Pitch | Shape | Self | Peers (median) |
| --- | --- | --- | --- |
| Judy, "a ledger that must balance" | `from`/`to` anchored to participations; chain, bounds and a DB **seam trigger** on the hot tables; offscreen events | 3/4/3/4/5/4/4 | 3/4/2/3/4/4/3 |
| Kevin, "mirror logs, current state stays king" | event-anchored mirrors; drift detected at read time; subject CASCADE; subtype-row removal on end | 4/4/5/4/4/3/5 | 4/3/5/3/4/3/5 |
| Ivan, "things have worldlines too" | participation anchor; `from` witness; one-worldline-one-entity counterparts; purge | 3/5/4/4/4/5/4 | 3/5/3/4/4/5/4 |
| Liam, "four ledgers, one verb" | event-anchored `into`/`out` with no `from`; the span compiler; `placed` links | 4/4/5/4/4/4/4 | 4/4/5/3/4/4/4 |

The converged design takes Ivan's anchor, Judy's `from`/`to` and home history, Kevin's end mechanics and plain-write discipline, and Liam's compiler and declared `unrecorded`.

### Designs considered and dropped (part 2)

- **Validity intervals on the relation rows** (bitemporal-style). Nobody pitched them, and all four rejected them on the grounds in PB1.
- **A generic `relation_change` table.** Rejected by all four in round 1 (PB1).
- **Deriving current state from the ledger** (event sourcing). It would put a replay on every hot read, and force the loot-bot to name an event on every `/give`, breaking S9, S16, BL1 and BL14.
- **An `event_id` anchor for objects** (Kevin, Liam). It loses a rift-carried watch in B (Ivan, Judy), and it lets a thing change at an event it wasn't part of. Both moved to the participation anchor.
- **No `from` column** (Liam, round 1). It discarded the S11 baseline the server held at write time.
- **A DB seam trigger on `containment`/`ownership`/`group_member`, plus offscreen events** (Judy, round 1). See [Drift](#drift-record-the-truth-never-fabricate-a-moment).
- **"Update the current row only if it still equals the old tip"** (Kevin, round 1, briefly adopted by Liam). It freezes the row after one off-record write.
- **"The table's now is the last-written branch, flagged `contested`"** (Kevin, round 1). It lets another timeline's fact reach a hot read.
- **Subject `CASCADE`** (Kevin) and **`RESTRICT`** (Judy, Liam). See PB6.
- **Group knowledge as memory after leaving** (Judy, Kevin). See [Groups](#groups-access-while-a-member).
- **"Things carried through a rift need no record"** (Ivan, Kevin, Liam). See PB12.
- **NULL as "uncontained" in history** (all three `from`/`to` schemas in round 1). It can't store "whereabouts unknown"; see PB2.
- **Copy-on-write counterparts in v1** (Ivan, round 1). Withdrawn; it survives only as a proposal for RFC 0026 D3 (P2-D2 below).

### Unresolved disagreements (part 2)

**P2-D1: How a date-placed participation avoids becoming lived-order evidence.** All four agree the *goal*: under the participation anchor, a pasted timeline's endpoints must not order each other by date. Otherwise "Bram acquired Ashfang before it left the vault" returns `causal`, decided by two labels, which is part 1's rejected Candidate B coming back through a foreign key (Liam's attack). They disagree on the mechanism.

- **Tied `lived_pos`** (the moderator's Bridge 5), amended two ways:
  - Judy: ties only *across* relations.
  - Kevin: a tie only where the chain rule holds in either order; otherwise assert an order or 409.
- **`event_participant.lived_claim text NOT NULL CHECK (lived_claim IN ('lived','placed'))`** (Liam). A `placed` participation makes **no lived-order claim at all**. Only `lived` participations feed the key's evidence and Kevin's never-reorder rule. `state_as_of` takes "latest at or before the cut" by key.

Liam's counter-example is decisive against the tie as written. Ashfang has two independent chains: vault-start < vault-end, and Bram-acquires < Bram-relinquishes. No single tie assignment leaves every cross pair unordered while keeping both within-chain orders, because a total preorder can't represent two incomparable chains. The moderator has checked this and agrees. Judy's and Kevin's amendments restrict *where* ties may occur, and don't escape it.

Liam's column has **not yet been reviewed by the other three**. Kevin should check it against part 1's row-check of `lived_pos` against `chronicle_key`. It is the first thing to review in part 2.

**P2-D2: Copy-on-write counterparts, as the rule for RFC 0026 D3.** Ivan proposes "a counterpart iff a worldline forks *and needs its own present*":

- it is minted lazily, on the first *present-tense* write for a subject in a non-home history, never on a ledger-only or span write;
- it gets a new slug and an `entity_prototype(counterpart IS-A origin)` link, so lore is inherited, not copied;
- contents are resolved through RFC 0026 shadows during containment walks, never cloned.

Judy adopts the rule. Kevin and Liam hold their attacks:

- subtree clones and duplicate listings in unfiltered hot lists (`/item-instances`, `owned-by`, inventory-web's board);
- a bulk import touching B minting one counterpart per subject;
- Kevin's condition: "no counterpart gets minted until someone shows the row count for a spellbook with contents".

Not part of this design. Recorded for RFC 0026's slice 7.

**P2-D3: A cold-path guarantee for the evented seam** (Judy's "minimum", round 3). This is a deferred constraint trigger on the **`*_change` tables only**, never on the hot tables. It fires only on evented writes, which already run at GM pace under the lock, and asserts at commit that:

1. a head change's `to` equals the current row;
2. a gap opens only where `from` equals the pre-write current row.

This would make the evented path DB-guaranteed rather than property-tested. It arrived in round 3, and **the others have not reviewed it**. Kevin's dissent forbids triggers on the three hot tables only, so this trigger doesn't obviously conflict with it.

**P2-D4: The first `from` of a compiled span.** Chain it from the nearest recorded neighbour, or always `unrecorded`? This is Liam's open question.

**P2-D5: Part 1's D2 gains weight.** Every change table references a participation. Whether the key is a surrogate `id` or `(event_id, entity_id)` now also decides whether the bootstrap watch can stand at one event twice (Kevin, Ivan).

### Dissents (part 2, verbatim)

> **Ivan (time-travel GM):** "History here is what I asked for: things' own lived lines, and a watch that went through a rift lived the jump. My dissent is about the present. One current row per entity is a convenience of the table, not a fact of the fiction. When the party lives in timeline B, the spellbook's *now* there is real, not a derived afterthought. I ask RFC 0026's D3 to adopt 'a counterpart iff a worldline forks and needs its own present': minted lazily on the first present-tense write in B, never on history-only writes, with contents resolved through shadows, never cloned."

<!-- -->

> **Judy (continuity guardian):** "I accepted that a loot-bot click may move a tracked thing without a story moment. The ledger then has a hole, and every as-of answer inside it says so: one value, labelled `unrecorded_window`. That is honest only while every hole is visible and only a recorded plain write can open one. If a later slice lets any write open a gap silently, lets `unrecorded` paper over a contradiction instead of an unknown, or lets current state be read as history, 'never contradictory' becomes a promise the ledger no longer keeps."

<!-- -->

> **Kevin (engineer):** "The loot-bot path is the one I get paged for. Keep it plain forever: no trigger on `containment`, `ownership` or `group_member`, no tenant lock, and no event invented by a click. Drift is a true fact about a real-world write; record it as a gap and never hide it behind fiction. Every history write that is allowed to be slow is evented, locked and chained. Every read that is allowed to be slow is an as-of read, batched and bounded by one subject's own changes. No counterpart gets minted on a write until someone shows me the row count for a spellbook with contents."

<!-- -->

> **Liam (calendar and authoring pragmatist):** "A participation claims the thing *lived* that moment, in that order. A span endpoint claims no such thing: it is an author's date, placed once. If any later slice lets a `placed` participation's `lived_pos` decide a basis stronger than `linearized`, whether by tie, default or backfill, then dates have become evidence again. That is part 1's rejected Candidate B, back through a foreign key. Keep 'unrecorded' a declared state, never a NULL. And keep paste-a-timeline free of confirmation storms."

### What each participant gave up (part 2)

| Persona | Gave up |
| --- | --- |
| Ivan | Counterparts in v1, and his `worldline_fork` 409. "Things carried through a rift need no record". "Now" as each subject's latest lived change, in favour of the home-history head. `RESTRICT`, for `NO ACTION`. His `how` column, for event prototypes. A `from` chained from the ledger, which could be false. NULL as "uncontained". A2's `order` for date placements. |
| Judy | The DB seam trigger on the hot tables. "Every current-state write must extend the ledger". Offscreen events ("fabrication", as Liam and Kevin said). `RESTRICT`. Group knowledge persisting after leaving. Date-ordered distinct `lived_pos`. NULL as the only "not contained". |
| Kevin | The `event_id` anchor. Subject `CASCADE` as erasure. "Last key wins + `contested`". "Apply only if current equals the old tip". Group knowledge as memory. Participation-only player visibility. Report-only gaps for retroactive inserts, which now chain or 409. "Rides its container" across a branch. |
| Liam | The `event_id` anchor; authors pay one participation row per change. "Rides its container". `into`/`out` without `from`. One tenant-wide present with `apply_to_now`. `RESTRICT`. Kevin's "only if old tip", adopted then dropped. Participation-gated player visibility. His `(event_id, child)` key, and `quantity` on existence. |

### Open questions (part 2)

1. **How long an `unrecorded_window` may stay open.** Should the continuity report escalate, and should there be a bulk "anchor all drift since E to event X"? (Judy)
2. **Travel-carry cost for huge trees.** A Bag of Holding or a ship with 10,000 items. Kevin's "history-bearing contents only" bounds it; measure it on a fixture. Do stacks count as units? (all four)
3. **Home history for a B-native subject.** Something first created in B: is it tagged B at birth? When else may a subject's home change: only through a retcon endpoint, or when it permanently crosses into B? (Ivan, Kevin)
4. **Display after end.** An ended item loses its `item_instance` row. Does it need a `former_kind`, and what happens to its slug? (Kevin; Judy's round 1 proposed `former_kind`)
5. **A disbanded group.** What an *ended* group means for group-knowledge access at later cuts, and whether a group acting in two branches keeps one membership ledger per history. (Kevin, Ivan)
6. **`possessions?as_of=` reverse lookups** ("everything Alice owned at E"): their index shape and cost on a 200-session fixture. (Judy)
7. **Whether players see gaps.** Should `unrecorded_window`, or a declared "lost 1402–1480", ever reach a player? Under PB8, only if the event is visible. (Ivan, Liam)
8. **`absorb` across timelines**, when the named event sits in a different timeline than the placeholder. (Liam)
9. **Bridge 3 for objects.** How a declared loop closes the watch's *ledger* chain, and what `origin_of` returns for an object. (Ivan)
10. **Position and frame history.** `spatial_position_change` and `entity_frame_change`, once RFC 0026's slices land. The same anchored pattern, one table each.

## Decision

Open. To reach one, decide these in this order:

1. **Accept the shared baseline (BL1–BL14) and the calendar layer.** Both are prerequisites whichever candidate wins. So is RFC 0026's B0 (composite tenant FKs), which is itself still undecided there.
2. **Review Ivan's A2 on its own.** A2 says no endpoint writes the key, and the key is rebuildable from evidence. Only its author has checked it. If accepted, the stored-versus-derived half of D1 goes away.
3. **D1, Candidate A or B.** Narrowed to dates as order evidence and a v1-native self-meeting. Judy proposes measuring write cost on a 200-session fixture rather than arguing it.
4. **D2, the participation's identity.** Needed before timed knowledge (sub-slice 3). Part 2 raises the stakes (P2-D5): every change table anchors on it.
5. **D4** is resolved by Part 2's PB6 (`NO ACTION` everywhere, plus `?purge=true`). Pin it with a cascade test, including a tenant purge, in sub-slice 3's ADR.
6. **Accept the part-2 baseline (PB1–PB14).** Before part-2 slice H1, review the two round-3 proposals only their authors have checked:
   - Liam's `lived_claim` column (P2-D1);
   - Judy's cold-path trigger on the `*_change` tables (P2-D3).
7. D3, Bridge 4, D5, P2-D2 (counterparts, with RFC 0026 slice 7) and P2-D4 can wait for their own slices.
8. **Review the [declared clock relations](#amendment-declared-clock-relations) amendment** before slice 5b, since it was never debated. Its three open points (changing rates, trip-relative durations, derived readings as sync points) go into that slice's ADR.

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
   - **5b, optional and its own ADR:** [declared clock relations](#amendment-declared-clock-relations).
     - `clock_relation`, `clock.directed`, and `derive_reading(uuid[], clock)` with the `derived` tag.
     - Tests: the requester's day-17 → day-20 example, both with and without an anchor; a chain X → Y → Z; a disagreeing path; and a mismatch 409.
6. **Importers.** donjon and Fantasy-Calendar, draft-first.
7. **Branches.** `timeline_divergence`, history(B), and the `travel` link kind. After RFC 0026's frames slice.
8. **Later, each its own RFC or ADR:**
   - the self-meeting (Bridge 4, with RFC 0026 D3);
   - `endpoint_anchor`;
   - declared loops (Bridge 3, deciding D3).

   Part 1's original `event_move` item is replaced by the part-2 slices below.

**Part-2 slices** (Kevin's round-3 plan). These come after part-1 slices 2–3, and each is its own ADR and milestone.

- **H1. Containment and ownership ledgers.**
  - `containment_change` and `ownership_change`, anchored to participations, with declared from/to states and the chain check.
  - `as_part_of` on the existing routes, and GM `GET …/entities/{id}/history`.
  - Tests:
    - `NO ACTION` holds, including a tenant purge;
    - `heads(ledger) = current` for subjects without drift;
    - **the loot-bot path makes zero extra queries**;
    - the split CHECKs reject a `contained` row with a NULL quantity.
  - Decides P2-D1 and P2-D3 first.
- **H2. As-of reads.** `state_as_of`, GM `/address?as_of=` and `/whereabouts?as_of=`, with the basis tags.
- **H3. Existence.** `existence_change`; end by default; subtype-row removal; merge and delete turned into end; `?purge=true` with its flip report. Amends ADR 0044.
- **H4. Groups.** `membership_change`, group-knowledge as-of access, and the roster flip report.
- **H5. Player reads.** Gated by event visibility; never return `from`.
- **H6. The span compiler and bulk import.** `placed` links (the A2 amendment), `absorb`, and "record the present". This can run in parallel with H2 or later.
- **H7. Travel carries contents** (PB12). After part-1 slice 7 (branches).
- **H8. Later.** P2-D2 counterparts with RFC 0026 D3; `spatial_position_change` and `entity_frame_change` with RFC 0026's own slices.

## Not in scope

- **Relativistic or any other physical time math.** A rate is either derived (Δ/Δ between sync points, with interpolation as a flagged hint) or **declared by the GM** as one linear relation per clock pair ([amendment](#amendment-declared-clock-relations)). It is never computed from physics.
- **Any web or bot UI** for placing events, authoring calendars, or reading the continuity report. This RFC fixes the data model and the read contracts, not the authoring surfaces.
- **Timed player-level knowledge** (`knower_player_id`). Placement, ownership, membership and existence history *are* in scope, in Part 2.
- **Belief and confidence:** "where Bram *thinks* the ring is", and how sure he is. That is authored `information` (RFC 0001's open question 1), not history. Epistemic kind and certainty are [RFC 0029](0029-epistemic-status-of-information.md)'s subject.
- **Position-in-space and frame history** (`spatial_position_change`, `entity_frame_change`). Same pattern, added with RFC 0026's own slices.
- **Declared loops, the self-meeting, and branch counterparts** (P2-D2). Shaped here, deferred to their own slices.
- **Merging or splicing two repositories' canon histories** (RFC 0024), beyond naming the question.
- **Any column on `containment`, `ownership`, `group_member`, `entity_frame`, `spatial_position` or `connection_endpoint`,** and any trigger on the first three. History lives in separate tables. Part 2 changes only ADR 0044's merge and delete *behaviour*, and only for history-bearing subjects.

## Consequences

Easier:

- "Did my character know that yet?" gets exactly one answer, with its basis, across branches, time travel, dilation and timeless planes.
- Knowledge can only be recorded at a moment the knower actually lived, and the database enforces it.
- Every place can render dates in its own calendars, including Gregorian-shaped, festival-heavy and multi-moon ones, and calendars can be imported rather than typed.
- **"Where was it, who owned it, who belonged, and did it exist, as of then" all get one answer** with a basis, per timeline, including things carried through a rift (Part 2). Every recorded change is anchored to a moment the thing itself took part in.
- **An ownership ledger, stack lineage, and "vanished from 1402 until 1480"** become ordinary data. A worldbuilder can paste a wiki timeline instead of hand-authoring events.
- **Destroyed and consumed things leave inventories without a hot query changing.** Their lore and history survive.
- A cozy single-setting story pays nothing, and neither does the loot-bot's write path.

Harder:

- **Eight new time tables, three calendar tables, and four history tables.** Each is small, but the as-of read semantics (lived past crossed with branch history) take real care to get right.
- **History-bearing subjects behave differently on delete and merge.** They end instead of vanishing, `?purge=true` is the only erasure, and a thing other ledgers name can only be ended. That is an ADR 0044 behaviour change, although subjects without history are byte-identical.
- **Drift is allowed and recorded, not prevented.** A plain write on a tracked thing opens an `unrecorded_window` that the continuity report lists until someone anchors it. That is Judy's honest cost, in her part-2 dissent.
- **Writes carry the complexity.** Re-keys under a per-tenant lock, flip reports and the continuity report all live on the write path. Their cost has to be measured, not assumed.
- **Calendars can now be wrong within a timeline.** Judy's honest cost of Bridge 1: an acknowledged inversion stays on the record rather than being refused.

Given up by the design, whichever candidate wins:

- A cycle inside the order, ever. Declared loops live beside it.
- `concurrent` as an answer. Unrelated events are ordered, and say they were only `linearized`.
- Dates deciding order, under Candidate A, and in part 2 through the back door of date-placed participations (P2-D1 decides how).
- A native self-meeting, stable loops, and a branch's own "present" row in v1.
- Per-coin provenance for stacks.

Gained:

- **One `compare` for every client.** The debate replaced three competing ordering primitives with one stored linear extension of recorded evidence, carrying a basis tag.
- **A verified donjon import path, and a bug caught before shipping.** The import mapping is based on donjon's actual code, and the moon-epoch offset bug would have passed a Greyhawk-only test.
- **A new column type, flagged openly.** The schema's first `jsonb` column is called out rather than slipped in.
- **Three defects in the moderator's own drafts, caught by participants.**
  - A drafting error in part 1's knowledge as-of rule ("intersected with" history, which would have dropped a traveller's past). Caught by Judy.
  - A three-valued-logic hole in a `CHECK` that let a `contained` history row with no quantity through. Caught by Liam.
  - A proof that a single tied `lived_pos` can't keep date-placed spans unordered. Also Liam.
