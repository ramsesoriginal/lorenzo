# RFC: How should Lorenzo record what kind of claim a piece of information is, and how confidently it's held, without costing a plain note anything?

Status: proposed — Decision open

## Context

[ADR 0017](../adr/0017-information-and-payloads.md) built `information` as a deliberately narrow container: `entity_id` + `title` + a free-text `type`, with four payload kinds. It also named what it left out. [RFC 0001](0001-core-domain-data-model.md)'s fuller design gave `information` "its narrative type (a rumor, an official record, a GM note, ...), source, author, validity, and basic provenance as a field". ADR 0017 listed "source, author, validity/reliability, provenance-as-a-field" as out of scope. That deferred scope is what this RFC picks up. It was named and set aside from the first slice, so this is not new ambition.

Since then, the rest of the container has been built:

- **Visibility is settled.** [ADR 0028](../adr/0028-knowledge-and-group-membership.md) chose **authored truths**. A GM writes a rumor as one `information` row and the confirmed truth as another, and grants each one to different knowers (a character, a group, or a player) through `knowledge`, or to everyone through `is_public`. The alternative, "one truth, redacted per audience", was considered and left open on purpose. This RFC sits on top of that decision. It is about tagging what *kind* of claim a row is and how confidently it's held. It does not revisit who can see what.
- **The catalog-versus-free-text line is drawn.** [RFC 0015](0015-information-metadata-shape.md) and [ADR 0101](../adr/0101-editable-information-and-description-payloads.md) settled the same tension for `type`. A small global `information_type` catalog holds only the values the application behaves differently for (`description`, `main_picture`). GM-authored types such as `note`, `handout` or anything invented mid-session get no catalog row: "free text stays free text; registering them here would defeat the point." RFC 0015 also said tenant-scoped catalog rows stay "no" until a real client asks. Whether epistemic kind belongs on the catalog side or the free-text side of that line has to be decided explicitly.
- **Rows are editable, attributed and ordered.** ADR 0101 gave `information` `PATCH`/`DELETE` with `If-Match`, `created_by`, `order`, and an edit gate: standing over the entity, plus sight of the row or authorship of it.

What was asked for splits into two axes, and they are not the same thing:

1. **Epistemic kind**: what sort of claim this is. Fact, rumor, guess, prophecy, prediction, interpretation, memory, and whatever a setting invents (a Cyberpunk "corporate leak", a D&D "omen").
2. **Confidence**: how strongly the claim is held. This hides a sub-question: *whose* confidence? It could be the author's or GM's belief that a rumor is true. It could be a particular knower's own certainty, which may differ between two characters who heard the same rumor from different sources.

The requirement that overrides everything else: **none of this may add friction to the common case.** A plain note on an item, or a personal session diary entry, must stay exactly as effortless as it is today. There must be no mandatory epistemic field and no confidence slider in the way of someone who just wants to type a sentence.

Two unmerged proposals touch this space, and the design stays out of their way:

- RFC 0027 (LorenzoScript, [PR #203](https://github.com/ramsesoriginal/lorenzo/pull/203)) adds `content_reference`, links *derived* from description text, plus backlinks that respect the source row's visibility.
- RFC 0028 (time, causal order and calendars, [PR #224](https://github.com/ramsesoriginal/lorenzo/pull/224)) makes events entities. It also gives `knowledge` a `learned | forgot` timed side table and answers "who knew what, as of when". Neither the timing of a verdict nor the history of a certainty is re-solved here.

### How this was produced

This follows the precedent of [RFC 0024](0024-repositories.md) and [RFC 0026](0026-world-model-axes-and-address.md): a structured, adversarial debate among independently researched perspectives. Each participant was committed to their own needs and no-gos and grounded in the real schema and code. The rounds were:

1. **Independent pitches.** No participant saw another's.
2. **Adversarial cross-critique**, in two halves. In 2a, each participant attacked at least one other pitch on concrete grounds. Two confrontations were forced: Maya's "open vocabulary" against Omar's "don't reinvent RFC 0015's catalog pattern", and Noah's "zero friction" against Priya's "must be genuinely queryable". In 2b, each participant defended against the attacks actually made on them, and conceded where the attack held.
3. **Convergence** on a moderator synthesis of everyone's 2b positions. Each participant accepted or amended the baseline, voted on the forks, scored the candidates, said what they had given up, and could file a verbatim dissent.
4. **Ratification (3b).** The participants ratified four bridges the moderator proposed to close the gaps that round 3 left.

| Persona | Role | Core need | No-go |
| --- | --- | --- | --- |
| Maya | GM of a prophecy-and-rumor-heavy mystery campaign | an open, extensible vocabulary of epistemic kinds, named in the setting's own words without waiting for a migration | a hardcoded enum of exactly "fact/rumor/guess/prophecy/prediction/interpretation/memory" in the schema |
| Noah | casual user: item notes, session diary | the plain-text path stays exactly as fast as today, with zero new mandatory fields | picking an epistemic status or confidence to write a note, or the simple path being harder to reach than the elaborate one |
| Omar | `apps/api` engineer | built on `information`/`payload`/`knowledge` and RFC 0015's pattern: optional, additive metadata, clean migrations, ADR 0028 not reopened | a second content system, or a design that can't name the exact table and column it extends |
| Priya | uses epistemics in play | real queries ("every rumor I've heard about the crown", "which of my guesses came true") and a claim lifecycle (confirmed, debunked, fulfilled) that never erases that the claim was once uncertain | a decorative, unqueryable tag, or "turned out true" expressible only by editing the original row |

The Decision below is left open. What converged is written up as the shared baseline and one converged design. Round 3's two candidates, and everything else that was dropped, are kept with the reasons they were dropped. Disagreements that remain are preserved as named disagreements and verbatim dissents rather than smoothed over.

#### How the debate moved

This is the short version. The sections below carry the detail.

- **Round 1.** Three of the four independently chose an open, free-text `epistemic_kind` column separate from `type`. Priya chose a fixed five-value base set (`fact/report/conjecture/prediction/recollection`), with tenant labels mapped onto it. The four answers to "whose confidence" were:
  - Noah and Priya: only the knower's.
  - Omar: a *presented* confidence on the row.
  - Maya: both, with a GM-private `credence` on `information` stripped from the response for non-GM callers.
- **Round 2a** broke several designs outright:
  - **Omar's resolver columns had a real bug**, found independently by Maya and Priya. `resolves_information_id ... ON DELETE SET NULL` combined with `CHECK (num_nonnulls(resolves_information_id, resolution) <> 1)` makes deleting the claim raise an IntegrityError. That is the exact trap ADR 0028 documents for `knowledge`.
  - **Noah's "relabel `rumor` → `debunked` via PATCH" was a spoiler by construction.** It changes the row for every viewer at once, and it erases the fact that the claim was ever uncertain.
  - **Maya's per-caller field stripping would be the first of its kind.** Omar verified that no read path strips a field by caller; the one field-nulling precedent, ADR 0099's `actor_visible`, is decided at write time. He also showed it leaks through the ETag. Noah and Priya added that it can leak through any sort or filter on it.
  - **Priya's base set failed on real settings.** Maya's counter-examples were a royal decree (a normative claim, neither true nor false), an omen (a report, a conjecture and a prediction at once), a scry result, and a Cyberpunk braindance. Omar showed the justification for the base set was circular.
- **Round 2b** was mostly concessions:
  - Omar conceded the bug and accepted a link table, provided its set of relations is closed.
  - Maya conceded Omar's typo attack: an open relation spelled `fulfills` silently never fulfils. She then withdrew GM credence entirely.
  - Noah withdrew relabel-as-lifecycle. He then verified against the code that embedding outcomes on hot reads costs a query on every item sheet, and Priya accepted that finding.
  - Priya gave up the global base, the special `fact`, the base freeze and the 1–5 scale.
  - By the end of 2b, all four answered "whose confidence" the same way.
- **Round 3** accepted the baseline unanimously, with amendments. It split 3–1 on bundling lineage into one table (Candidate A) against deferring it (Candidate B). Omar was the one for B: a single table lets a verdict supersede a lineage link unless a trigger stops it. He also found that the synthesis's `ON DELETE SET NULL (col)` supersede FK silently forks a chain.
- **Round 3b** ratified the four bridges. Splitting verdicts and lineage into two closed tables removed Omar's reason to prefer B, and he dropped it. Three of the four conditional dissents were withdrawn, their conditions met in this text. Omar's dissent stands, in amended form.

## Answers to the questions this RFC was asked

**Is epistemic kind an open, tenant-invented vocabulary (like `note`) or a fixed, code-meaningful set (like `description`)? Open, with no exceptions, and all four agree.** RFC 0015's own rule, applied honestly, decides it. A catalog row exists only for a value the application behaves differently for. Once lifecycle behaviour moves onto links, where it belongs because "fulfilled" and "refuted" are facts about how rows relate, nothing in the API branches on whether a row is a "rumor" or an "omen". So no kind gets a catalog row, not even `fact`. Making `fact` special would start encoding a canonical truth. Under ADR 0028 every row is already an authored truth, and a special `fact` is the start of the redaction model ADR 0028 left open (Omar). The behaviour the code *does* act on lives in closed CHECK sets on the link tables. Values the code acts on are closed; words the code never reads are open (Maya's 2b rule, adopted by all). Cross-synonym grouping ("every prophecy under any name") is a tenant-defined, advisory mapping from word to family. It is never a platform ontology.

This is not the "real client" RFC 0015 was waiting for. `information_type` gets no tenant rows. The optional family table (sub-slice 5) is a separate, advisory vocabulary with no foreign key, and it is built only when a client ships a family filter.

**Whose confidence? The knower's own subjective certainty, stored only on `knowledge`, and all four agree.** `knowledge` is the edge between a knower and a claim. "Mira holds the rumor at 90, Tobin at 30" is a fact about two edges, not about the row. The author's or GM's belief gets **no column**. Every way of storing it on `information` either leaks or reopens ADR 0028:

- visible to all, it spoils the rumor;
- stripped per caller, it is per-field redaction, leaks through the ETag and through sorts, and can't be read back by a player who wrote it;
- kept in a separate GM-only sub-resource, it becomes a second truth that can contradict a verdict.

A GM's belief is therefore itself an authored truth: a GM-only `information` row, linked to the claim by a verdict or a derivation. That holds whether the GM has decided or not ("leaning false, undecided"). A *presented* reliability ("the innkeeper swears it's true") is prose in the claim's own text, not a column. Nothing falls back to anything: a NULL knower confidence means "not stated". It never means "believes whatever the row says".

## Shared baseline (converged; all four accept)

- **BL1 Kind column.** `information.epistemic_kind text NULL`, with no DEFAULT and no backfill. Existing `type='rumor'` rows are not copied; that would be inventing data. It is separate from `type`: a handout can be a prophecy, and `description` is a singleton. It is optional on `InformationCreate` and `InformationUpdate`, and the API turns `""` into NULL. The one CHECK trims and bounds it (1–64 characters, no leading or trailing whitespace). The author's casing is kept for display ("Tavern Talk"). All matching (filters, family mapping, suggestions) is case-insensitive through `lower()`.
- **BL2 NULL means unclassified.** It never means "fact", "memory" or 50, and no filter matches NULL. `?epistemic_kind=fact` never returns an unclassified diary entry.
- **BL3 Open vocabulary with zero code-meaningful values.** There is no catalog row for any kind, no global base set, and no special `fact`. A kind earns a global catalog row only on the day code must behave differently for it, which is the same trigger `description` met.
- **BL4 Kind is presentation.** It is how the claim presents itself to whoever can see the row. GM truth verdicts never go in kind. An in-world resolution is never a relabel; `PATCH` on kind is for fixing mistakes.
- **BL5 Confidence belongs to the knower only.**
  - **Schema:** `knowledge.confidence smallint NULL CHECK (confidence BETWEEN 0 AND 100)`. NULL means "not stated".
  - **Never combined:** it is never COALESCEd, and there is no derived "effective" number. Each knower row (character, group or player) carries its own value.
  - **How it's set:** an optional body `{confidence}` on the existing knower `PUT`; the bodiless call is unchanged.
  - **Read back:** it must never ship write-only (see [Br4](#converged-design)).
  - **Public rumors:** a knower's confidence in a public rumor sits on an explicit knowledge row on an `is_public` row. That is already legal and changes no visibility.
  - **Why 0–100:** it is ordered, comparable across settings, and needs no second vocabulary. Display bands ("doubts / suspects / sure") are a client concern.
- **BL6 No confidence of any kind on `information`.** No author or GM credence column, no `stated_confidence`, no GM-only assessment sub-resource. A GM's belief is a GM-only row plus a link. If a number is ever wanted, it becomes a `payload_number` on that GM-only row once RFC 0015 sub-slice 4 builds number authoring.
- **BL7 Claim links are rows, append-only, and visible only when both ends are.**
  - **Structure:** closed CHECK sets (a typo 422s), many-to-many (one truth row can refute three rumors), and create/delete only, with no `PATCH`, no `If-Match` and no `updated_at`.
  - **Deletes:** both `information` FKs are `ON DELETE CASCADE`, never `SET NULL`. Deleting a row removes its links, never the other row.
  - **Twists:** ordered by an explicit supersede chain, never by `created_at` ([RFC 0028](https://github.com/ramsesoriginal/lorenzo/pull/224) BL4).
  - **Any row can be a claim**, with a kind or without one, so an unclassified diary guess can be resolved.
  - **Visibility:** a link is visible iff `can_see(one end) AND can_see(other end)`. The outcome is derived per caller and never stored.
  - **No side channels:** `information_visibility.py`'s `can_see` is unchanged, and creating a link never bumps either row's `updated_at`, so the ETag can't leak it.
- **BL8 Nothing is embedded on hot routes.** Links are read at their own endpoint. Nothing new is eager-loaded by `GET /entities/{id}`, item and instance reads, or `InformationOut`. **A query-count test enforces it:** an entity holding only plain notes issues exactly today's queries. (Noah checked the claim against the code. `Information.payloads` and `knowledge_links` are `lazy="raise_on_sql"` and loaded through fixed `selectinload` chains, `eager_load_options()` and the chain in `routers/entities.py`. Those chains can't skip unclassified rows, so embedding outcomes would cost every item sheet a round trip.)
- **BL9 Synonyms are advisory, tenant-defined and mapped after the fact.**
  - **Shape:** an optional tenant table maps a kind word to a family word, both the tenant's own: `('omen', 'foretelling')`, `('corporate leak', 'hearsay')`.
  - **Never in the way:** there is no FK from `information`, a mapping is never required before using a word, and a word can be remapped at any time. Nothing is frozen and there's no in-use 409.
  - **Querying:** `?epistemic_family=` expands on the server at query time. Unmapped words are simply absent from family queries. Until the table exists, `?epistemic_kind=` accepts a list.
  - **Who:** writes are tenant-admin only (the ADR 0103 tier; a mapping is tenant-wide). Reads of the mapping are GM or tenant-admin only, because kind names can be spoilers ("true vision", "planted evidence"). Players benefit only through server-side expansion, whose results are `can_see`-filtered anyway.
  - **Unanimity:** unanimous after round 3b; Maya moved on writes, Noah on reads.
- **BL10 List filters ride on RFC 0015 sub-slice 5.** The collection filters (`?epistemic_kind`, `?epistemic_family`, `?outcome`, `?known_by`, `?confidence_max`, `?authored_by`) and the suggestions endpoint need a SQL form of `can_see`. That is `visible_information_clause(vis) -> ColumnElement[bool]`, placed beside `can_see`, with a parity test over a fixed matrix: admin, opted-out ORGA, GM-reachable, player knower, group knower, public.
  - **It isn't a rewrite.** `resolve_information_visibility` already reduces ORGA opt-out, ADR 0035 reachability and knowers to sets, so only the final predicate exists twice (Omar).
  - **Whose prerequisite it is.** Every paginated list needs it, because filtering in Python after pagination leaks counts. It is therefore RFC 0015 sub-slice 5's prerequisite, not this RFC's. This RFC's non-list slices don't wait for it.
  - **Filters are opt-in.** They are computed only when the parameter is present.
- **BL11 Activity log ([ADR 0084](../adr/0084-activity-log-coverage-and-member-removal-notice.md)).** Edits to kind and to confidence are descriptive content, so they aren't logged, the same as titles and stat values. Creating or deleting a verdict or derivation changes what exists, so it is logged, with ids and the verdict value only.
- **BL12 Out of scope.**
  - The story time of a verdict, and certainty history. RFC 0028 answers "as of when" through the evidence row's `learned` change.
  - The redaction alternative, which ADR 0028 leaves open.
  - Source and provenance ("heard from whom") beyond lineage.
  - Change-feed entries for information, which [ADR 0099](../adr/0099-player-facing-change-feed.md) excluded.
  - Localized kind names, and per-campaign vocabularies.
- **BL13 UI order (Noah's amendment in round 3, accepted by all).** Clients show kind and confidence in a collapsed section placed *after* the content field, with no pre-selected value. A blank kind input sends nothing. loot-bot's `/note` exposes kind only as its last optional option; Discord requires optional options after required ones anyway.

## Converged design

This is round 3's Candidate A (lineage now) rebuilt on the structure of Candidate B (verdicts with no trigger), per bridge **Br1**. All four ratified it in round 3b.

### Schema

```sql
-- Sub-slice 1
ALTER TABLE information
  ADD COLUMN epistemic_kind text NULL,
  ADD CONSTRAINT information_epistemic_kind_trimmed CHECK (
    epistemic_kind IS NULL
    OR (epistemic_kind = btrim(epistemic_kind) AND length(epistemic_kind) BETWEEN 1 AND 64));

-- Sub-slice 2
ALTER TABLE knowledge
  ADD COLUMN confidence smallint NULL,
  ADD CONSTRAINT knowledge_confidence_range CHECK (confidence BETWEEN 0 AND 100);

-- Sub-slice 3
ALTER TABLE information ADD CONSTRAINT information_id_tenant_id_key UNIQUE (id, tenant_id);

CREATE TABLE information_verdict (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id               uuid NOT NULL REFERENCES tenant (id) ON DELETE CASCADE,
  claim_information_id    uuid NOT NULL,   -- the rumor / guess / prophecy
  evidence_information_id uuid NOT NULL,   -- the row that settles it
  verdict                 text NOT NULL CHECK (verdict IN ('confirms', 'refutes', 'partial', 'moot')),
  supersedes_verdict_id   uuid NULL,       -- a twist: this verdict replaces that one
  created_by              uuid NULL REFERENCES app_user (id) ON DELETE SET NULL,
  created_at              timestamptz NOT NULL DEFAULT now(),
  CHECK (claim_information_id <> evidence_information_id),
  CHECK (supersedes_verdict_id <> id),
  UNIQUE (id, claim_information_id),       -- target of the supersede FK
  UNIQUE (supersedes_verdict_id),          -- a linear chain: no forks
  FOREIGN KEY (claim_information_id, tenant_id)
    REFERENCES information (id, tenant_id) ON DELETE CASCADE,
  FOREIGN KEY (evidence_information_id, tenant_id)
    REFERENCES information (id, tenant_id) ON DELETE CASCADE,
  FOREIGN KEY (supersedes_verdict_id, claim_information_id)   -- supersede only within the same claim
    REFERENCES information_verdict (id, claim_information_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX information_verdict_one_root   -- no duplicate roots from a double click
  ON information_verdict (claim_information_id, evidence_information_id, verdict)
  WHERE supersedes_verdict_id IS NULL;

CREATE TABLE information_derivation (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL REFERENCES tenant (id) ON DELETE CASCADE,
  from_information_id uuid NOT NULL,   -- the retelling
  to_information_id   uuid NOT NULL,   -- its source
  -- note text NULL CHECK (length(note) <= 1000)   -- open: see D1
  created_by          uuid NULL REFERENCES app_user (id) ON DELETE SET NULL,
  created_at          timestamptz NOT NULL DEFAULT now(),
  CHECK (from_information_id <> to_information_id),
  UNIQUE (from_information_id, to_information_id),
  FOREIGN KEY (from_information_id, tenant_id)
    REFERENCES information (id, tenant_id) ON DELETE CASCADE,
  FOREIGN KEY (to_information_id, tenant_id)
    REFERENCES information (id, tenant_id) ON DELETE CASCADE
);
-- Both tables: indexes on tenant_id and on each information FK column, tenant_isolation
-- policy + FORCE ROW LEVEL SECURITY, mirrored in each model's __table_args__. No updated_at:
-- the rows are immutable (group_member's precedent).
```

**Why it's correct (Omar, checked against Postgres 17, which compose, CI and deploy all run):**

- **Deletes.** Deletes can't fail. The self-FK is MATCH SIMPLE, so roots with a NULL `supersedes_verdict_id` are unchecked. Cascades that reach one row by several paths are fine. Nothing is ever `SET NULL`, so the partial root index can't collide at delete time.
- **Cycles.** The chain can't cycle. Rows are immutable and can only reference rows that already exist, and the self-reference CHECK covers the one remaining case.
- **Concurrency.** Two concurrent writers superseding the same head collide on `UNIQUE (supersedes_verdict_id)`. The second gets `409 verdict_exists`, with no lock needed.
- **Tenant agreement.** The composite `(id, tenant_id)` FKs make tenant agreement structural. That is the same device RFC 0028 uses on `knowledge`, and it closes the class of gap every earlier join table names as "nothing enforces that `tenant_id` agrees". `UNIQUE (id, tenant_id)` on `information` can't fail, since `id` is already the PK. It takes a brief SHARE lock while the index builds, which is trivial at this scale; `CONCURRENTLY` isn't available inside Alembic's transaction anyway.
- **Lineage stays separate.** Verdicts and lineage are two tables, so a verdict can't supersede a derivation by construction (Omar's Fix 3). A single-table design needed a trigger for that.

A supersede FK of `ON DELETE SET NULL (supersedes_verdict_id)`, which the round-3 synthesis proposed, is syntactically valid on Postgres 15+ and still wrong. Deleting the middle link of L1←L2←L3 turns L3 into a second root and silently forks the chain (Omar).

### Semantics

**Br2, the verdict chain** (Priya's amendments merged with Omar's fixes):

- **Several roots per claim are legal.** Two authors who can't see each other's verdicts can each resolve the same claim.
- **Read.** For each chain, the head is the last verdict *the caller can see*.
  - `supersedes_verdict_id` is rendered as the nearest *visible* ancestor, or null if there is none. An id the caller can't resolve would prove that a hidden verdict exists.
  - If every visible head agrees, the claim's outcome is that verdict. If they differ, the outcome is `contested`. With no visible verdict, it is `unresolved`.
  - Nothing is ever ordered by `created_at`.
- **Write.**
  - If the caller can see a head on the claim, a new verdict must supersede it, or it gets `409 verdict_exists`.
  - Superseding needs sight of the superseded verdict (both of its ends), or it gets `404`.
- **Delete.** Only a verdict with no successor may be deleted directly. Verdicts behave as a stack: the self-FK cascades. What a caller is told when the successor is one they can't see is **open (D2)**, and so is what deleting an evidence row may cascade away (**D3**).

**Br3, who may write a verdict.** The caller must pass ADR 0101's edit gate on **both** rows (standing over the entity, plus sight of the row or authorship of it), **and** at least one of:

- (i) GM-tier sight of the claim's entity: the tenant admin/ORGA/OWNER bypass, or campaign-GM reachability. Omar notes this is cheap: `vis.is_admin or claim.entity_id in vis.gm_reachable_entity_ids` is one additive `has_gm_sight(entity_id)` method on `InformationVisibility`, and `can_see` is untouched.
- (ii) authorship of the claim row;
- (iii) the evidence row is not `is_public`.

What this allows and blocks:

- A player can't make a GM's public rumor read "refuted" to everyone by posting a public note (Noah's vandalism case).
- A player can record a private or party-granted verdict, seen only by that evidence's knowers. That is how a GM ends up seeing `contested` (Priya's case).
- **The public-flip loophole is closed** (found independently by Noah and Omar in round 3b; Maya and Priya ratified Br3 before this amendment was raised and haven't objected). A `PATCH` that sets `is_public = true` on a row that is evidence for any verdict must satisfy (i) or (ii) for each of those verdicts, or it gets `409 verdict_visibility_widening`. Only that one `PATCH` path gains a check.
- Derivations need ADR 0101's gate on both rows. Deletes use the same gate as creates.

**Br4, confidence read path and acceptance tests.**

- **The read path.** The knower `PUT` returns `InformationOut` today (`routers/information.py`). Changing it to return the knowledge row would be an oasdiff-breaking change and would break loot-bot's `addInformationKnower` (Noah and Omar both verified this). Putting confidence on `InformationOut` instead would fail Noah's one-key rule and expose per-knower data on the row. So the confidence slice ships with a narrow `GET .../information/{id}/knowers/{knower_entity_id}` returning that one row. The caller must be able to act as that knower (their own character or group) or have GM-tier sight; otherwise the answer is `404`. Full knower listing (RFC 0015 decision 11) and the `?known_by&confidence_max` filter come when they land.
- **The acceptance tests.** **Priya's four queries are sub-slice 4's acceptance tests** (see [Worked examples](#worked-examples)). The feature doesn't count as done until they pass, even if RFC 0015 sub-slice 5 has to be pulled forward to get there. Sub-slices 1 and 2, the plain-note and confidence paths, don't wait on them.

### API

All changes are additive under oasdiff.

- **`InformationCreate` / `InformationUpdate`:** optional `epistemic_kind: str | None`. Merge-patch semantics as today: omitted means unchanged, and an explicit `null` clears it.
- **`InformationOut`:** gains **one** key, flat, `epistemic_kind: str | None` (unanimous; Noah conceded his single `epistemic` object key once BL6 left nothing else to nest). Recorded rule: **any further epistemic field on `InformationOut` must first pass Noah's one-key test.**
- **`PUT /tenants/{t}/information/{id}/knowers/{knower_entity_id}`:** optional body `{confidence: int | null}`; the response is unchanged.
- **`GET /tenants/{t}/information/{id}/knowers/{knower_entity_id}`:** returns `KnowledgeOut{knower_entity_id, information_id, confidence}` (Br4).
- **`GET /tenants/{t}/information/{id}/links`:** returns `{verdicts: [...], derivations: [...]}` in both directions. It is filtered by the existing Python `can_see` on both ends, carries the chain rendering above, and includes the claim's derived `outcome` for this caller.
- **Verdicts:** `POST /tenants/{t}/information/{claim_id}/verdicts` with `{evidence_information_id, verdict, supersedes_verdict_id?}`, and `DELETE /tenants/{t}/information-verdicts/{id}`.
- **Derivations:** `POST /tenants/{t}/information/{id}/derivations` with `{to_information_id}`, and `DELETE /tenants/{t}/information-derivations/{id}`.
- **Sub-slice 4, on the collection endpoint** (RFC 0015 decision 6, widened tenant-wide where a query needs it): `?epistemic_kind=` (repeatable), `?outcome=unresolved|confirmed|refuted|partial|moot|contested`, `?known_by=`, `?confidence_min=` and `?confidence_max=`, and `?authored_by=` (reads ADR 0101's `created_by`). Plus `GET /tenants/{t}/information/epistemic-kinds`, which returns the distinct kinds over rows the caller can see, grouped by `lower()`, with one display form each.
- **Sub-slice 5:** `?epistemic_family=`, plus admin routes for the mapping table.

```sql
-- Sub-slice 5 (advisory; no FK from information)
CREATE TABLE epistemic_kind_family (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenant (id) ON DELETE CASCADE,
  kind text NOT NULL, family text NOT NULL, sort_order integer NOT NULL DEFAULT 0,
  created_by uuid NULL REFERENCES app_user (id) ON DELETE SET NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX epistemic_kind_family_kind ON epistemic_kind_family (tenant_id, lower(kind));
-- tenant_isolation + FORCE RLS
```

A word in two families (an omen that is both hearsay and a foretelling) is deferred; it would need `family text[]` or a join table.

### Worked examples

**Noah's note.** loot-bot's `/note` body stays `{title, type: "note", isPublic, content}`, byte for byte. The stored row differs from today's only in that `epistemic_kind` is NULL. The response gains `"epistemic_kind": null`. `GET /entities/{id}` issues the same queries it does today. A private note still makes the same second knower call it makes today, with no body.

**Maya's finale.** These rows are all on the same tenant.

| Row | `type` | `epistemic_kind` | Visibility |
| --- | --- | --- | --- |
| G "Gold flows from the Duke's cellar" | note | Tavern Talk | granted to Mira and Tobin |
| F "The Duke's cellar is flooded" | note | Tavern Talk | granted to Tobin |
| O "When the red star falls, the heir returns" | handout | omen | public |
| H "The heir is the stable boy" (Tobin's guess) | diary | guess | Tobin's own row |
| T "The red star fell at Midsummer; the stable boy is crowned" | note | NULL | GM-only |
| M "Leaning false, undecided" | note | NULL | GM-only |

How the finale plays out:

- **Confidence.** `knowledge` holds Mira→G at confidence 90 and Tobin→G at 30.
- **Lineage.** `information_derivation`: F derived from G (the rumor mutated). M derived from G is the GM's undecided hunch, which needs no credence column.
- **Verdicts.** `information_verdict`: T confirms O, T refutes G, T confirms H. One truth row settles three claims without being copied.
- **Before T is granted to anyone,** every player sees O, G and H as `unresolved`, and nothing in any response, count or ETag says otherwise. The GM sees `confirmed`, `refuted` and `confirmed`.
- **Granting T to Tobin** makes all three verdicts visible to him at once. Mira still sees G as unresolved.

**A double bluff.** T1 "the letter is genuine" confirms a claim C. Later, GM-only T2 "the letter was forged" refutes C, superseding T1. Later still, T3 "the forgery was planted to discredit it" confirms C, superseding T2.

- **The GM** sees the chain T1←T2←T3, and the outcome `confirmed`.
- **A player holding C, T1 and T3 but not T2** sees T3 as the head, with `supersedes_verdict_id` rendered as T1, and the outcome `confirmed`. Nothing reveals that T2 exists.
- **If a player also records their own private refutation of C** (allowed by Br3 (ii) when C is theirs, or by (iii)), the GM sees two disagreeing heads and the outcome `contested`.

**Priya's acceptance tests (sub-slice 4).** Q1–Q4 are the four queries; L1–L3 are the three lifecycle scenarios.

| # | Question | Call | Answered at |
| --- | --- | --- | --- |
| Q1 | every rumor I've heard about the crown | `GET …/entities/{crown}/information?epistemic_kind=rumor&epistemic_kind=tavern%20talk&known_by={char}` → with families: `?epistemic_family=hearsay&known_by={char}` | 4 (a list of kinds); 5 (a family) |
| Q2 | which of my guesses came true | `GET /tenants/{t}/information?epistemic_kind=guess&authored_by=me&outcome=confirmed` → `?epistemic_family=guesswork&…` | 4; 5 |
| Q3 | every unresolved prophecy in this campaign | `?epistemic_family=foretelling&outcome=unresolved`, scoped by `known_by` over the campaign's roster | 4 or 5, approximated (see below) |
| Q4 | what my character believes with low confidence | `?known_by={char}&confidence_max=30` | 4 |
| L1 | a rumor mutates | `information_derivation` | 3 |
| L2 | debunked, then re-confirmed as a double bluff | the supersede chain | 3 |
| L3 | a prophecy is fulfilled, but only some characters know | both-ends visibility | 3 |

"In this campaign" can only be approximated. RFC 0001's open question #4 ("facts": which campaign a piece of world content is in scope for) is still undesigned, and Priya accepts the approximation.

## Scoring

Round 3 scored the two candidates on the table at the time. A bundled verdicts and lineage into one table; B kept verdicts only and deferred lineage. The converged design came afterwards, in round 3b, and was not scored separately by the participants. Scores are 1–5, listed as Maya / Noah / Omar / Priya.

| Criterion | Candidate A | Candidate B |
| --- | --- | --- |
| Simple | 4 / 3 / 3 / 3 | 4 / 4 / 4 / 4 |
| Flexible | 4 / 4 / 5 / 4 | 3 / 3 / 4 / 3 |
| Pragmatic | 4 / 4 / 4 / 4 | 4 / 4 / 4 / 4 |
| Best-practice | 4 / 4 / 3 / 4 | 4 / 4 / 4 / 4 |
| Future-proof | 4 / 4 / 4 / 4 | 3 / 3 / 4 / 3 |
| Innovative | 4 / 4 / 4 / 4 | 4 / 3 / 4 / 3 |
| Fits what's built | 4 / 4 / 4 / 4 | 4 / 4 / 4 / 4 |

Reasons given:

- **Simple.** A scored lower because of its supersede FK and (in Omar's reading) the trigger needed to keep verdicts off lineage links.
- **Flexible and future-proof.** B scored lower because it doesn't model rumor mutation at all, and a later `derived_from` would land awkwardly in a table named for resolutions.
- **Fits what's built.** Both designs lose a point, for the new `UNIQUE (id, tenant_id)` on `information`, the first per-caller derived value (the outcome), and a second implementation of the visibility predicate.

**Moderator's assessment of the converged design.** This was not voted on and is offered for the reviewer:

| Criterion | Score | Why |
| --- | --- | --- |
| Simple | 4 | Sub-slices 1–2 are one nullable column each with one CHECK. Sub-slice 3 adds two small, closed, immutable tables with declarative invariants and no trigger. The chain-rendering rule is the one genuinely intricate part. |
| Flexible | 4 | Any word, in any setting, with no migration. Families are tenant words, and lineage and verdicts are both modeled. Relations are closed on purpose, and multi-family words and campaign-scoped vocabularies are deferred. |
| Pragmatic | 4 | The non-list slices ship on today's code. The list slice waits on the SQL `can_see` that every paginated list needs anyway. |
| Best-practice | 4 | Closed where the code acts and open where it doesn't. Composite tenant FKs, CASCADE and never SET NULL, append-only verdicts. Visibility stays per row. |
| Future-proof | 4 | Composes with RFC 0027 (authored links, distinct from derived `content_reference`) and RFC 0028 (verdict timing through the evidence row's `learned`). Leaves the redaction alternative open. |
| Innovative | 4 | A claim's outcome is derived per caller from what that caller can see: one rumor, several simultaneous and honest outcomes, and no new grant table. |
| Fits what's built | 4 | ADR 0028 rows, ADR 0101 gates, RFC 0015's rule and ADR 0084's log policy. It adds the first per-caller derived value and a new constraint on the busiest table. |

## Designs considered and dropped

- **A fixed enum of epistemic kinds** (a Postgres enum, a CHECK list or a code `Literal`). Maya's no-go, and nobody proposed it.
- **Priya's global base set** (`fact/report/conjecture/prediction/recollection`, with tenant labels mapped onto it and a composite FK freezing a resolved claim's base). It was dropped by Priya in round 2b.
  - Maya's settings didn't fit it: a royal decree, an omen, a scry result and a braindance each fit none of the bases or several.
  - Omar showed its code-meaningfulness was circular, and showed that `fact` restarts a canonical-truth model.
  - The `ON UPDATE RESTRICT` freeze meant a misclassified claim couldn't be fixed without deleting its history.
  - Even the fallback, `fact/claim/prediction`, fails on the decree.
- **A label-first registry** (a word must exist in a tenant table before use). It was dropped by Priya. It puts a registry between a GM and a word, and under ADR 0103's tier a non-admin GM couldn't coin "tavern talk" mid-session at all (Noah).
- **GM credence as a column on `information`, stripped per caller** (Maya, round 1). This would be the first read-time per-caller field stripping in the API.
  - It is per-field redaction, which reopens ADR 0028 (Omar).
  - Every serializer path would have to remember to strip it. ADR 0028's own addendum records three such paths leaking independently (Noah, Omar).
  - A credence-only edit bumps the ETag every player sees (Omar).
  - Any sort or filter on it is an oracle (Priya).
  - A player couldn't read back a value they wrote (Noah).
- **GM credence as a GM-only sub-resource** (`information_gm_assessment`, Maya, round 2a). It fixed the leaks but kept a second truth that can contradict a verdict. Maya withdrew it in round 2b: a GM-only row plus a link does the same job with no new visibility rule. No dissent was filed.
- **Presented or stated confidence on `information`, falling back through `COALESCE` into knower confidence** (Omar). Dropped by Omar. The COALESCE breaks "NULL means not stated": Alice would inherit the tavern keeper's 90 (Noah, Priya). A public rumor's presented reliability is prose.
- **Relabeling as lifecycle** (`PATCH rumor → debunked`, Noah). Withdrawn by Noah. It tells every viewer at once, including characters who never learned the truth, and erases the claim's history.
- **Resolution as two columns on the resolving row** (`resolves_information_id` + `resolution`, Omar). Withdrawn by Omar.
  - It had the SET NULL / CHECK delete bug.
  - It had no many-to-many, so one truth row couldn't settle three claims.
  - `supersedes` as a *value* meant a row couldn't both refute and supersede.
- **An open, two-tier relation vocabulary** (catalog relations plus free-text ones like "garbles", Maya, round 1). Withdrawn by Maya. A typo such as `fulfills` silently becomes a relation the code ignores, and the prophecy never shows as fulfilled (Omar).
- **Candidate A, one link table for verdicts and lineage.** It needed a trigger to stop a verdict from superseding a `derived_from` link. Superseded by Br1's two tables.
- **Candidate B, verdicts only with lineage deferred.** It left rumor mutation unmodeled, and mutation was a named scenario. Superseded by Br1, which ships lineage now without a trigger.
- **Outcome embedded on `InformationOut` / `EntityDetailOut`.** Dropped by Priya after Noah's code check (BL8).
- **An `epistemic` wrapper object on `InformationOut`, omitted when null.** Dropped by Noah. It is a new "omitted key" convention in an API where every field is present, and it wraps a single value.
- **The knower `PUT` returning the knowledge row.** It is an oasdiff break for existing clients (Br4).
- **Visibility-filtered suggestions in sub-slice 1.** Maya wanted it early to stop drift, but it needs the SQL `can_see` or a Python scan of every row. With case-insensitive matching (BL1), only spelling drift remains, so it ships with the list filters instead (unanimous).

## Unresolved disagreements

- **D1: a free-text `note` on links.** Everyone agrees verdict reasoning belongs in the evidence row's own text. The question is lineage flavor ("garbled in the retelling at the Rusty Anchor").
  - **For a note on `information_derivation` only:** Noah and Priya, both of whom moved there from "no note" in round 3b. It would be `note text NULL CHECK (length(note) <= 1000)`, immutable, never filtered, never logged, and documented as "visible to anyone who can see both rows".
    - **Their reasoning:** in the retelling's own text, lineage prose reaches every hearer of the retelling. On the link, it reaches only those who know both versions (Maya's round-3 argument).
  - **Omar accepted a note on links generally in round 3,** because with many-to-many one shared row can't carry a per-claim explanation. He did not restate a position on the narrower version.
  - **Maya, who proposed the note, dropped it from both tables in round 3b.**
    - **Her reasoning:** Priya's leak holds for lineage too. A GM's "this is the planted lie" reaches every player who holds both ends, so her own argument only moved the leak to a different audience. GM-only flavor belongs in a GM-only row linked by a derivation, which is editable and has its own visibility.
  - **The column is additive, so it can be added later without a break.**
- **D2: deleting a verdict whose successor the caller can't see.** It is settled that only a verdict with no successor is deleted directly, and that the self-FK cascades. What happens when a caller asks to delete a head they can see that has a hidden successor is open:
  - **Maya:** one generic `409 verdict_not_deletable`, with no id and no count, whether the successor is visible or hidden, so the response reveals nothing either way.
  - **Noah:** `404`, following the API's existing "not found" for "exists, but not for you".
  - **Priya:** re-root the hidden successors. `UPDATE supersedes_verdict_id = NULL` in the same transaction, then return `204`. Several roots are legal now and `contested` is defined, so re-rooting no longer leaves the outcome undefined, which was Omar's objection to SET NULL. It also means a player can never destroy a GM's hidden verdict by deleting their own.
  - **Omar** accepts leaving this to the implementing ADR, but only if it is decided before sub-slice 3 is built.
- **D3: deleting an evidence row that would cascade away verdicts the caller can't see.** A player deletes their own private note. A GM had built a hidden verdict chain on the player's verdict that used that note as evidence.
  - **Omar's default:** an `information` DELETE that would cascade away verdicts the caller can't see is refused.
  - **Priya:** deleting evidence is an authoring deletion, and it cascades.
  - **Constraint:** a refusal must not itself reveal the hidden verdicts, which ties D3 to D2's answer.
  - **Omar's condition applies here too:** decide before sub-slice 3.

## Dissents (verbatim, as each participant asked them to be preserved)

**Omar (standing; amended in round 3b):**

> "The implementing ADR must decide the two open delete questions before sub-slice 3 is built. They are the successor the caller can't see, and hidden verdicts cascaded away by deleting an evidence row. It must also keep verdict writes protected against public-flip loopholes. No epistemic word, whether kind, family or relation, may ever gain behaviour except through a closed CHECK or a global catalog row added by migration."

**Priya (withdrawn in round 3b, on the condition that Br4's acceptance-test wording and Br2's chain rules appear in this RFC's text, which they do above; it revives if either is removed):**

> "Sub-slices 1–3 alone deliver exactly what I called my no-go: a kind nobody can filter, and verdicts nobody can query. Q1–Q4 are the reason this RFC exists. They should be written into the RFC as sub-slice 4's acceptance tests, and the feature should not count as done until they pass, even if RFC 0015 sub-slice 5 has to be pulled forward to get there. Also: a claim's outcome must never expose a hidden verdict through its chain, and two heads that can't see each other must answer `contested`, not pick a winner silently."

**Noah (withdrawn in round 3b, on the condition that BL13, the query-count test and Br3's verdict-authorship and public-flip rules are adopted; it revives if any is dropped):**

> "Z1–Z8 are acceptance tests, not aspirations. A plain note or diary entry must cost exactly today's request, response keys, queries and UI steps. Anything that fails one of them, including a UI that shows a kind picker before the text box, or a verdict link any player can hang on someone else's claim, is not a detail to fix later. It breaks the one promise this RFC made to the people who never asked for epistemics."

Noah's Z1–Z8 are his round-1 acceptance criteria:

- **Z1:** nullable columns, no DEFAULT.
- **Z2:** no new required request fields.
- **Z3:** at most one new response key for a plain note.
- **Z4:** NULL is never a value.
- **Z5:** no extra round trips.
- **Z6:** text first, extras collapsed, nothing pre-selected.
- **Z7:** no new read cost for plain notes.
- **Z8:** no new activity-log noise.

**Maya (conditional; applies only if lineage is deferred, which the converged design does not do):**

> "Deferring `derived_from` leaves rumor mutation, the defining mechanic of rumor-heavy and mystery play, with no representation at all. A GM can record that a rumor was false but not that the flood story grew out of the gold story. Mutation then ends up as prose in the retelling's own text, and that text is visible to every hearer, so the design leaks the very lineage it declined to model. Lineage costs one CHECK value in the same table; defer it and the table's name and routes lock it out later."

## What each participant gave up

- **Maya.**
  - GM credence, twice: first as a per-caller-stripped column, then as a GM-only sub-resource. A GM's hunch is now a GM-only row plus a link.
  - Her two-tier open relation vocabulary, which became closed CHECKs after Omar's `fulfills` typo; "garbles" and "misremembers" now live in text.
  - "No CHECK" on kind, in exchange for trim-only plus case-insensitive matching.
  - Her early suggestions endpoint, her proposed link `note`, and GM write access to family mappings.
- **Noah.**
  - "Nothing new needed" for lifecycle. His relabel was a spoiler, and resolution now costs two tables and five routes.
  - "No grouping until a client asks." He accepted an advisory family table and multi-value filters.
  - His own lowercase-storage rule and his single `epistemic` response key.
  - Write-only confidence as a mere sequencing detail. A read path now ships in the same slice.
  - A visibility-filtered, player-readable family mapping.
- **Omar.**
  - Confidence on `information` in any form: `stated_confidence`, then the COALESCE inheritance.
  - "No new table." His resolver columns had a real delete bug and no many-to-many. He accepted two new RLS tables plus a new constraint on the hottest table.
  - A strict "a debate isn't a client." A family mapping is now fully specified.
  - Lowercase-by-CHECK.
  - His preference for deferring lineage.
- **Priya.**
  - A global, code-meaningful base. "Every prophecy" now means whatever that tenant mapped.
  - Status on the row. Her queries all wait for RFC 0015 sub-slice 5 and a SQL `can_see`.
  - The base freeze and a special `fact`. "Can't be erased" shrank to "resolving never edits the claim": deletes still cascade and evidence text stays editable.
  - Her labels-first registry and 1–5 scale.
  - Her `information_resolution` naming, in favour of `information_verdict` plus `information_derivation`.

## Open questions (found while drafting, not debated)

The moderator raised these from the code after round 3b. They are for the reviewer and the implementing ADRs, not positions of any participant.

- **O1: who may set a knower's confidence.** The knower `PUT` authorizes against the *information's* entity, not the knower (`routers/information.py`, `add_information_knower`, via `authorize_information_edit`).
  - **The effect:** a player can't set their own character's certainty about a GM's rumor on the Duke, since they have no standing over the Duke. Only the GM tier can.
  - **Why it matters:** in round 1 Maya left this open and leaned towards letting players set it. Q4 ("what my character believes with low confidence") is most useful if they can.
  - **A natural rule, mirroring Br4's read gate:** a confidence-only update to an *existing* knower row needs "may act as that knower" or GM-tier sight. Creating a knower row keeps today's gate. Decide in sub-slice 2's ADR.
- **O2: players' verdicts are bounded by ADR 0038's standing rule.** Creating or editing information needs self-or-managed standing over its entity, and so does Br3's gate. So a player can resolve only claims on entities they have standing over, such as their own character's diary guesses.
  - **The consequence:** Priya's "a player privately confirms the GM's rumor, and the GM sees `contested`" works only when the rumor is on the player's own entity.
  - **Probably right:** a player's belief about someone else's rumor is exactly what `knowledge.confidence` is for, and verdicts stay authorial.
  - **Still to state:** the implementing ADR should say this explicitly.
- **O3: cycles in lineage.** Nothing stops "A derived from B derived from A". Reads aren't harmed, since each derivation is one hop. The ADR should decide whether to leave it, as `group_member`'s bipartite shape does, or reject it with a cycle trigger, as `entity_prototype` does.
- **O4: a one-call convenience.** In round 1 Priya proposed inline evidence (`POST .../verdicts` creating the evidence row in the same transaction), so that resolving is a single call. It wasn't revisited.

## Decision

Open. Before an ADR can accept this, the reviewer needs to settle:

1. Whether to adopt the converged design: the baseline BL1–BL13, the schema above, and Br1–Br4 including the public-flip rule.
2. D1: whether there is a lineage `note`, and where.
3. D2 and D3: delete policy for hidden successors and hidden cascades. Per Omar's dissent, these must be settled before sub-slice 3.
4. O1 and O2: confidence write authorization, and stating the bound on players' verdicts.

## Proposed sub-slices (once decided)

1. **Kind.**
   - `information.epistemic_kind` with its CHECK, on `InformationCreate`, `InformationUpdate` and `InformationOut`.
   - **Tests:** an omitted field reads back as NULL; existing rows are unchanged; `PATCH null` clears it; CHECK boundaries (blank, padded, 65 characters); no `audit_log` row on edit.
   - **The BL8 query-count test** (an entity with only plain notes issues today's queries).
   - **The Z2 replay test:** loot-bot's current `/note` body returns 201.
2. **Confidence.**
   - `knowledge.confidence`, the optional knower `PUT` body, and the narrow own-knower `GET` (Br4). O1 is decided first.
   - **Tests:** the bodiless `PUT` is unchanged; confidence is never COALESCEd; a public row with an explicit knowledge row carries it.
3. **Verdicts and lineage.**
   - `UNIQUE (id, tenant_id)` on `information`, `information_verdict`, `information_derivation`, the `/links`, verdict and derivation routes, the activity-log entries, and the public-flip check.
   - D2 and D3 are decided first.
   - **Tests:** every chain rule in Br2 (hidden mid-chain link, `contested`, `409 verdict_exists`, concurrent supersede); every Br3 branch; no ETag change on the claim or evidence when a link is created; the cascade behaviour.
4. **Filters.** These come after RFC 0015 sub-slice 5 and its `visible_information_clause` parity test, or with them, pulling that slice forward if needed.
   - `?epistemic_kind` (repeatable), `?outcome`, `?known_by`, `?confidence_min` and `?confidence_max`, and `?authored_by`, plus the `(tenant_id, lower(epistemic_kind)) WHERE epistemic_kind IS NOT NULL` index and the suggestions endpoint.
   - **Acceptance:** Q1–Q4 pass using kind lists.
5. **Families.** `epistemic_kind_family` and `?epistemic_family=`, built when a client ships a family filter or picker. **Acceptance:** Q1–Q3 re-run with families.

## Not in scope

- **Timing and history.** When in the story a verdict happened, and how a knower's certainty changed over time, belong to RFC 0028: the evidence row's `learned` change, and a future timed side table anchored to participations. `created_at` on the new tables is audit only.
- **Visibility itself.** The redaction alternative (RFC 0001 open question #1 / ADR 0028) stays open, and nothing here forecloses it.
- **Provenance.** Source and provenance as fields ("who told you this") go beyond lineage. RFC 0015's unbuilt `payload_entity`, or RFC 0028's participations, may answer them better.
- **Change feed and notifications.** Change-feed entries or notifications for kinds, confidence or verdicts are excluded, following ADR 0099.
- **Vocabulary scope.** Per-campaign vocabularies, localized kind names, and words in more than one family are all out.
- **Scope of world content.** Campaign scoping of world content (RFC 0001 open question #4, "facts") is out, which is why Q3's "in this campaign" is approximated.

## Consequences

- **For a plain note, the only observable change is one new response key** (`epistemic_kind: null`). The request, stored columns other than that NULL, the queries issued and the UI order stay as they are. Tests pin this.
- **`information` gains another unique constraint,** `(id, tenant_id)`, as the target of composite tenant FKs. It sits beside the singleton partial index and `UNIQUE (entity_id, "order")`, and costs an index build on the busiest table.
- **The visibility predicate will exist twice,** in Python (`can_see`) and in SQL (`visible_information_clause`), once RFC 0015 sub-slice 5 lands. A parity test is the only thing keeping them honest. That is the same "two independently maintained facts" risk RFC 0015 already named for the singleton list.
- **Outcome is the API's first value derived per caller from other rows' visibility.** Two players can legitimately receive different outcomes for the same claim. That is the point, and it needs documenting for client authors, so that a client never caches outcomes across users.
- **Vocabulary drift is possible by design.** "Rumor" and "rumour" remain two words until someone maps them to one family. Case and whitespace can't drift. Spelling can.
- **Deleting information now removes verdicts and derivations too.** Deleting an `information` row cascades to every verdict and derivation touching it, and, through the supersede FK, to every verdict stacked on those. D2 and D3 decide how much of that a caller who can't see it may trigger.
- **No epistemic word can gain behaviour without a migration.** Kinds and families stay inert text. Only the closed verdict CHECK carries behaviour, so a new outcome needs a migration and a release, as it should.
