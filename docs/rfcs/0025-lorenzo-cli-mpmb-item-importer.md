# RFC: Lorenzo CLI — an MPMB standard-item importer, with prototype/stat generation and instantiation bundles

Status: accepted, decided with the maintainer on 2026-09-29. Where the [Cross-persona review](#cross-persona-review) at the end and the sections above disagree, the review wins. It is built in the slices listed under its [Status](#status), each recorded as its own ADR when it lands.

> **Reviewed 2026-09-29** by four personas (a homebrew worldbuilder, the implementing coder, a tenant creator, an author) — see [Cross-persona review](#cross-persona-review). The review resolves both open seams named below (§2's JS host, §7's reconciliation) and the Python client question, amends §3, §4, §5, §6, and §7, and leaves a short list of checks to make while building, each with a fallback.

## Context

[docs/brand/identity.md](../brand/identity.md) already names "Lorenzo CLI" as an anticipated member of the product family, and [docs/domain/repositories.md](../domain/repositories.md) flags bulk repository-content authoring as an explicit, undesigned future problem. Neither has ever been scoped into real work. Separately, a structured brainstorm on speculative apps proposed a general-purpose CLI for bulk import/export and scriptable CRUD, deliberately generic ("markdown, LaTeX, plain text... other simple CRUD operations, so it can be used by scripts and other tools like Claude Code").

This RFC gives that idea its first concrete, bounded slice, driven by a real target format: [MPMB's Character Record Sheet](https://github.com/morepurplemorebetter/MPMBs-Character-Record-Sheet)'s "additional content syntax" — a mature, community-standard way of authoring D&D 5e homebrew content (weapons, armor, gear, tools, ammunition, packs, feats, spells, magic items, class/subclass features, races, creatures, companions), read directly from the source repository rather than assumed. Two things about the actual format matter for scope:

- **It is executable JavaScript, not a neutral data format.** Files like `WeaponsList["longsword"] = { name: "Longsword", type: "Martial", ... }` are meant to be evaluated inside Adobe Acrobat's own scripting engine, embedded in the PDF sheet itself — not parsed as JSON.
- **Content splits cleanly into a portable half and a non-portable half.** Name, source citation, flavor text, and static numeric values (a weapon's damage die, armor's AC, an item's weight) translate directly into Lorenzo's entity/component model. A large minority of attributes — particularly on feats, spells, magic items, and class features — are literal embedded calculation formulas that call back into the PDF's own form fields (`event.value = Math.max(1, What('Wis Mod'));`), or level-indexed (1–20) arrays assuming D&D 5e's specific level structure, or placement instructions for a literal one-page PDF layout ("Limited Features section"). None of that has a home in Lorenzo today, and translating it meaningfully would need RFC 0016's still-proposed computed-stat mechanism to exist first, at minimum.

Given that split, this RFC deliberately scopes to **standard items only** — weapons, armor, adventuring gear/equipment, adventuring packs, tools, and ammunition (`WeaponsList`, `ArmourList`, `GearList`, `PacksList`, `ToolsList`, `AmmoList`) — the mechanically simplest, most regular corner of the format, and the one that exercises Lorenzo's prototype/stat/containment model well without needing any new domain capability. Feats, spells, magic items, class/subclass features, races, creatures, and companion templates are named as explicit, deferred future work (see [Not in Scope](#not-in-scope)), not attempted here.

## Decision

### 1. A new app: `apps/cli`

Python, matching `apps/api`'s own language and able to share a generated API client with it; `rich` for terminal output, per the tool's own explicit stack choice going into this RFC. Named `apps/cli`, not `apps/lorenzo-cli` — every existing app (`api`, `loot-bot`, `inventory-web`, `account-hub`) already omits the redundant "lorenzo" prefix, since that's implicit in the repo itself; "Lorenzo CLI" is the brand's name for the *product*, not a directory-naming instruction. Per [docs/guides/adding-an-app.md](../guides/adding-an-app.md), this RFC is the scope-confirmation step; actual scaffolding (`mise.toml`, workspace registration, Dependabot, release-please, pre-commit hooks) is real, mechanical work deferred to implementation, not designed here.

The importer described below is this app's first real feature, not its only planned one — the same "other simple CRUD operations... usable by scripts and tools like Claude Code" scope from the original brainstorm still applies to whatever comes after it.

### 2. The import pipeline: evaluate → map → review → commit

MPMB's syntax being executable JS, not JSON, means actually running it is a real, necessary step — not something a text parser can shortcut:

- **Evaluate**, not parse. Each source file runs inside a small, sandboxed JS host (Node itself, invoked as a subprocess, or an embedded JS VM) seeded with just enough of the runtime surface these files assume: plain objects for `WeaponsList`/`ArmourList`/`GearList`/`PacksList`/`ToolsList`/`AmmoList` that the files' own assignments populate, and no-op stand-ins for `RequiredSheetVersion()` and similar sheet-only calls. This is the same technique the sheet itself uses — evaluating the file inside a JS host — not a bespoke parser fighting arbitrary JS syntax.
- **Map**: a per-list, per-field translation table turns each recognized attribute into a concrete Lorenzo write — an entity, its prototype edges (§3), its stats (§4), its information. Fields with no Lorenzo meaning (`regExpSearch`, `defaultExcluded`, `iFileName`, `RequiredSheetVersion`, `nameAlt`) are dropped. Fields needing real judgment (§4's price extraction, §5's container detection) are named, explicit steps — never a silent default standing in for a decision nobody actually made.
- **Review, before anything is written.** The CLI produces a full preview of every entity it's about to create, its chosen prototype parents, its stats, and any extracted values (especially price, per §4) — confirmed before anything commits. This is the "import/cleanup process" this whole idea was proposed with from the start; nothing here writes silently.
- **Commit**: once confirmed, ordinary, already-existing `apps/api` writes — create item, set prototypes, set stats, create information. No new `apps/api` surface is required for this half of the RFC.

> *Amended by the review: the JS host is an embedded V8 in a token-free worker process, not Node ([R1](#r1-the-js-host-embedded-v8-in-a-token-free-worker)); the pipeline gains a non-interactive `plan`/`apply` contract ([R6](#r6-a-non-interactive-contract)); and three small, optional `apps/api` additions are made rather than worked around ([R11](#r11-small-appsapi-additions)), none of them a new capability.*

### 3. A curated prototype taxonomy, derived mechanically from the source's own categorical fields

Verified directly against the source syntax, not assumed: weapons carry a real `type` field (`"Simple"`, `"Martial"`, `"Natural"`, ...) and an `ability` field; armor and tools have D&D 5e's own equally standard categories (light/medium/heavy/shield; artisan's tools/gaming sets/musical instruments). The importer builds a small, fixed set of category prototypes **once** — `Weapon` → `Simple Weapon`/`Martial Weapon`, independently `Melee Weapon`/`Ranged Weapon` (so a longbow inherits from *both* `Martial Weapon` and `Ranged Weapon` — genuinely a two-parent case, exactly what Lorenzo's existing multiple prototype inheritance is for); `Armor` → `Light`/`Medium`/`Heavy`/`Shield`; `Tool` → its own standard subcategories; `Container` → `Backpack` and similar (§5).

Mapping a source `type` value to a specific category prototype is a plain, deterministic lookup table, not fuzzy matching — reviewable and predictable. A `type` value the table doesn't recognize is surfaced to the person running the import (§2's review step), not guessed at. New prototypes are ordinary data (per [RFC 0001](0001-core-domain-data-model.md): "new prototypes... are data changes, not schema migrations"), so extending the taxonomy later, if a source list needs a category this RFC didn't anticipate, costs nothing structurally.

> *Amended by the review, which found the source fields don't say what this section assumed: a weapon's `type` is a **proficiency** category (an open vocabulary), not melee/ranged, and an armour `type` is `light`/`medium`/`heavy` only. The lookup table is now a user-extensible data file ([R5](#r5-the-mapping-one-toml-file-over-a-built-in-seed)) and the taxonomy is layered ([R8](#r8-the-taxonomy-a-system-neutral-core-and-a-dnd5e--layer)).*

### 4. Stats: weight maps directly; price needs a real extraction step, named as one

Weight is a clean, already-numeric field in the source data, mapping directly onto the "weight" concept `v_item` was designed to expose from the start (RFC 0001). Price does **not** map directly — verified directly, it's embedded in a human-readable display string meant for a dropdown menu (`infoname: "Bullets, Purple (10) [5 sp]"`; a pack's `name: "Purple pack (10 gp)"`), not a structured field. Extracting it needs a small, per-list regex step (the bracket/parenthesis-plus-denomination pattern is consistent across the lists checked). Any item where extraction fails or produces something that doesn't look like a real price is surfaced in the review step (§2), not silently zeroed or skipped — this is exactly the kind of gap a real cleanup pass exists to catch.

> *Amended by the review: the stats this section maps are widened, and weight is written to `own_weight`, not `weight` ([R9](#r9-the-stats-twelve-definitions-frozen-once-copied)).*

### 5. Containers: a curated seed list, reinforced by a real signal already in the source data

Standalone gear has no explicit "is this a container" field, so recognizing one starts from a small, curated, human-reviewed name list (Backpack, Pouch, Sack, Quiver, Case, ...). But `PacksList`'s own `items` array carries a genuine, documented convention beyond a flat list: an entry ending in `", with:"` is the source format's own way of saying "this is a container, and everything listed after it goes inside it" — confirmed directly in the syntax's own comments, down to "it is advisable to add any container at the top." The importer uses this as real signal, not just confirmation: a pack's contents become actual `Containment` rows against the container entity, not just descriptive text (§6). Either mechanism missing a case is softened by Lorenzo's own existing `is_container` fallback (ADR 0066: also true if the entity actually contains something) — real containment data from §6 makes a container self-evident even if the curated name list didn't catch it, so the two reinforce each other rather than either needing to be exhaustive alone.

Quantities of identical contents (`["Rations, days of", 5, 2]` — 5 units) map to `Containment.quantity` (ADR 0041) — one stack, not five identical rows. This is the deliberate default for anything sold "per unit" generally, including rope (see §7), specifically because it preserves Lorenzo's already-working split/merge (ADR 0041/0044) for free — a player handing a friend part of a stack is an ordinary, already-built action. A bespoke numeric stat (e.g., a "length" value) is possible instead wherever splitting genuinely never matters for a given item, but it gives up that free capability, since split/merge operates on `Containment.quantity`, not on arbitrary stat values — a per-item judgment call for whoever maintains the mapping table, not a global rule.

### 6. Bundles: preparing pre-populated container instances — a CLI-only concept, not a new `apps/api` capability

A **bundle** is import-time metadata, parsed directly from a `PacksList` entry's own `", with:"`-delimited structure (§5): which prototype is the container, and which other prototypes (with what quantities) go inside it once instantiated. This is held entirely as data the CLI itself keeps — a plain table of `container prototype → [(content prototype, quantity), ...]` — **not** a new domain concept `apps/api` needs to understand.

"Instantiate a bundle" (a GM granting an "Explorer's Pack") is client-side orchestration over calls that already exist today: instantiate the container prototype into a new instance, instantiate each content prototype into new instances, set each one's container to the first. No new `apps/api` endpoint. This deliberately stops short of a more general, appealing idea — a prototype defining its own instantiation-time contents as a first-class, cross-client `apps/api` feature, so any client (not just this CLI) could offer "instantiate with contents" for anything, not just what this importer happened to bring in — which is real, new domain-model work and is named, not designed, in [Not in Scope](#not-in-scope).

> *Amended by the review: a bundle held only in the CLI's own table would not travel with a repository copy, so a pack's contents are also written into the tenant as an `information` entry on the pack item ([R7](#r7-bundles-are-data-in-the-tenant)). Instantiation is still client-side orchestration, and there is still no new `apps/api` capability.*

### 7. Idempotency: re-running the importer must not duplicate a catalog

Worth naming explicitly rather than discovering it the hard way: a source list's own object key (`WeaponsList["longsword"]`) is the stable identity to track, not the display name, since a name can be edited without changing the key. The importer needs some way to answer "did I already create this one" on a second run against the same tenant. The direction that fits without requiring anything new in `apps/api`: record the source key as a plain stat/tag on each entity the importer creates, and keep a local run-manifest mapping source keys to entity ids for fast lookups, reconciling against the tag if the manifest and the tenant ever disagree (a second machine, a shared tenant two people import into). Whether an efficient stat-value lookup already exists on the `apps/api` side to make the reconciliation path cheap is worth confirming during implementation rather than assumed here — flagged, not resolved.

> *Resolved by the review: identity is an entity slug, checked in batches through the existing `entities/resolve`, and the source-key tag is dropped ([R4](#r4-identity-the-entity-slug-not-a-tag-and-not-a-manifest)).*

## Not in scope

- **Feats, spells, magic items, class/subclass features, races, creatures, and companion templates.** The deliberate "second moment" this RFC's own scoping is built around. These lean heavily on the non-portable half of the format described in Context — embedded calculation formulas, level-indexed arrays, choice/extrachoice mechanics — and at least the computed/calculated pieces have no honest translation until [RFC 0016](0016-stats-computed-values-and-crud-api.md)'s computed-stat mechanism exists. Worth revisiting this RFC's own mapping-table approach once that lands, not before.
- **`SourceList` as a first-class imported concept.** Source citations flatten into a simple stat/tag for v1; modeling sources as their own entities (so "everything from the Sword Coast Adventurer's Guide" becomes a real, queryable grouping) is a reasonable later step, not designed here.
- **A general, cross-client "any prototype can define its own instantiation-time contents" capability** (§6's bigger sibling). Genuinely appealing, and connects naturally to both RFC 0018's `entity_template` and RFC 0024's repositories — but real, new `apps/api` domain work needing its own scoping conversation, not something this RFC's CLI-only bundle mechanism should be mistaken for.
- **Publishing imported content as an actual repository** (RFC 0024). A natural next step once this importer produces a clean catalog and prototype tree — create a repository-tenant, subscribe others to it — but a separate, later action this RFC doesn't perform itself. The review kept this boundary where it was, and added an [output contract](#r10-the-publishing-boundary-stays-with-an-output-contract) so the importer's output doesn't make the later step harder, and a named follow-up, `lorenzo repo offer`.
- **Two-way sync** ("keep this file synced with Lorenzo," from the original CLI brainstorm). This RFC is one-shot import only. Sync is a materially harder, separate problem — drift detection and conflict resolution — not attempted here.
- **App scaffolding mechanics** (`mise.toml`, workspace registration, Dependabot, release-please, a deploy workflow) per [docs/guides/adding-an-app.md](../guides/adding-an-app.md). Real, but mechanical, and deferred to actual implementation.

## Consequences

- This importer becomes the first real consumer of a Python client for `apps/api` — worth building as this CLI's own internal library (mirroring `apps/loot-bot`'s already-proven generated-TypeScript-client pattern) rather than assuming one exists.
- A successful run's byproduct — a real prototype taxonomy plus a populated catalog under it — is a natural candidate to become actual repository content (RFC 0024) later, **but only if it was imported into a `repository` tenant**: a tenant's `kind` is fixed at creation ([ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md)), so content imported into a play tenant can never be published. The first draft of this RFC said "without this RFC having designed for that explicitly", which the review found to be wrong; [R3](#r3-the-target-an-existing-repository-tenant-by-default) and [R10](#r10-the-publishing-boundary-stays-with-an-output-contract) design for it.
- Running the importer needs whatever write access `apps/api` already requires for catalog authorship in a tenant (ordinary `Membership`) — no new permission concept.
- MPMB's own syntax will keep evolving (new sheet versions, new attributes) independently of this importer's own mapping table, and homebrew authors will keep writing content this table hasn't seen — the mapping table is an ongoing maintenance cost, not a one-time build, and should be treated that way from the start.

## Cross-persona review

Reviewed 2026-09-29, before this turns into a plan or ADRs. Four personas each argued from their own needs and no-gos, in three rounds: independent pitches, an adversarial cross-critique (with two forced confrontations), then a convergence vote on a draft of the amendments below. Every proposal was scored against simple, flexible, pragmatic, best-practice, future-proof, and innovative, plus a seventh: does it fit what this RFC already decided. Settled parts were only reopened with a concrete reason.

| Persona | Speaks for | No-go |
| --- | --- | --- |
| Quiril | A worldbuilder importing his own homebrew MPMB sources | The only way to add a category is to fork the CLI |
| Rasmus | The coder building the Python CLI | Starting with the JS host or the API client hand-waved, or writing a bespoke JS parser |
| Silva | A tenant creator seeding new tenants | An importer that only writes into one existing tenant by hand, with no path to "run once, offer to every new tenant" |
| Tonja | An author building a world on the item hierarchy | A taxonomy so shaped around D&D 5e that another system starts over |

The personas were model-played positions, not user research. Claims about `apps/api` were checked against the code and ADRs by the personas and spot-checked again by the moderator (`ItemCreate` has no `slug`; the generic stat `PUT` passes `acquire_group=False`; stat groups and definitions have no `PATCH`/`DELETE`; `TenantOut.kind` is readable). The experiments reported under R1 and R2 were run once by the coder persona against the six upstream syntax templates. They are not reproducible from this repository yet, which is why R1 requires a spike.

### What the source files showed that this RFC had wrong

Reading the upstream `weapons.js`, `armor.js`, `packs.js`, `tools.js`, `gear.js`, and `ammo.js` templates (not this RFC's summary of them) changed four assumptions:

- **A weapon's `type` is a proficiency category** (`Simple`, `Martial`, `Natural`, `Cantrip`, `Spell`, `AlwaysProf`, `Improvised Weapons`, or *any string the author defines*). Melee versus ranged comes from a separate, optional `list` and the free-text `range`. §3's "Melee Weapon / Ranged Weapon" axis is derived from those, not from `type`. Armour `type` is `light`/`medium`/`heavy` only, and is absent for natural armour and spells; a shield is not a `type`.
- **Some `type` values aren't items at all** (`Natural`, `Cantrip`, `Spell`, `AlwaysProf`), so the table needs a `skip` disposition, or the real lists drown the review step.
- **The files hold `RegExp` literals and repeat keys** (`regExpSearch: /…/i`, `alternatives: ["…", /…/i]`; the templates give `source`, `ac`, and `useSpellMod` twice as alternatives). Only evaluating them, as §2 says, yields the sheet's own reading, and JSON can't carry a `RegExp`. This confirms §2's "evaluate, don't parse".
- **Pack `items` are display-name strings** (`["Hempen rope, feet of", 50, 0.2]`), not keys into `GearList`, so linking a pack's contents to catalog items needs a name-resolution step.

### R1. The JS host: embedded V8 in a token-free worker

Decided (resolves §2's open seam). Source files are evaluated by an embedded V8 (the PyPI package **`mini-racer`**; not the stale `py-mini-racer`, whose last release is from 2021) inside a disposable worker subprocess that never holds a credential:

- The worker is spawned **before login**, has a wall-clock kill and a memory cap (64 MB was tested), and returns **tagged JSON only**: a `RegExp` becomes `{"$re": [source, flags]}`, a function becomes `{"$fn": text}` and is **never called**, and `SourceList` is returned too.
- All files of a run evaluate in **one ordered context**, since a homebrew `source: ["HB", 0]` refers to entries defined earlier.
- A `ReferenceError` on an unknown sheet-only call is handled by seeding a recording stub and re-running in a fresh context, bounded and reported. `Math.random` and `Date` are neutralised so output is deterministic.
- The engine sits behind a one-function protocol, so it is replaceable, with a golden-corpus conformance test.

**Platform: Linux, including WSL, is the supported target; native Windows is optional and untested.** That drops the Windows execution spike. The worker is started as a plain subprocess (`python -m lorenzo_cli.evalworker`, JSON over stdin/stdout), not through `multiprocessing`, which avoids fork-versus-spawn entirely (forking a process with asyncio threads is unsafe); on Linux `RLIMIT_CPU` is a backstop, while `RLIMIT_AS` is not set because V8 reserves address space.

**Why this is the best-practice, future-proof choice.** The security boundary is the *process* (no credential, killed on a wall-clock timeout, JSON-only output), not the engine, so the engine can be the one with the fewest moving parts. `mini-racer` 0.14.1 (released 2026-02-01, last upstream commit the same day) ships `py3-none` wheels: tied to no Python minor version, so a Python upgrade never breaks the install. The wheels cover `manylinux_2_27` on x86_64 and aarch64, `musllinux`, macOS, and Windows, and bundle V8, so no Node or system library is needed on a GM's machine. MPMB's files are ordinary ECMAScript and the engine sits behind a one-function protocol with a golden-corpus test, so it can be replaced. If `mini-racer` is ever abandoned, `pythonmonkey` (SpiderMonkey, 1.3.2 released 2026-06; per-Python-version wheels, so less attractive as the default) is the named second engine; a Node subprocess would be a third, for machines that have it.

Rejected: a Node subprocess as the default (Node isn't on a GM's `PATH`, and `vm` isn't a security boundary); `quickjs` (last release 2023); `js2py` (no wheels, ES5, unmaintained, and reported to have a sandbox-escape CVE, which was not checked); `dukpy` (ES5.1 only); any bespoke JS parser.

**Spike before coding:** (i) evaluate the sheet's own SRD scripts, not just the six templates, in one ordered context, recording every stubbed name, entry counts per list, wall time, peak heap (is 64 MB enough?), and every `$fn` value on an item, and set the stub-retry bound from that data; (ii) settle what happens when code chains on a stubbed call's result (`X("a").b`). The earlier concerns about `aarch64` and musl wheels were checked against PyPI and are closed.

### R2. The Python client: generated models, a thin hand-written transport

Decided. `datamodel-code-generator` produces pydantic models from `apps/api`'s OpenAPI document (219 classes, byte-identical across runs); a hand-written layer of roughly 200 lines wraps `httpx`; an `OPS = {operationId: (method, path, request, response)}` table is checked against the dumped schema by a test, giving the path-level safety ADR 0122's TypeScript client has. It lives in `apps/cli`; a shared `packages/api-client-py` waits for a second Python consumer.

- **Drift.** A `check-schema` task dumps the schema, regenerates, and runs `git diff --exit-code`, wired into the existing client-drift CI job. Note `apps/api/openapi.json` is git-ignored: the task dumps it first with `apps/api/scripts/dump_openapi_schema.py` (no database needed), as `packages/api-client`'s own check does.
- **Errors.** One error type carrying status and the `application/problem+json` body, as in ADR 0122. `401`: refresh once. `412`: re-read and re-plan. `409` slug conflict means "exists". `422` on a stat value's type is surfaced as a mapping error naming the definition. Retry only `GET`/`PUT`/`DELETE`, never `POST` (there is no idempotency key).
- **Rejected:** `openapi-python-client` (it silently dropped `ComputedStatOut` and two endpoints while reporting success), a hand-written model layer (a second implementation that drifts), importing `lorenzo_api.schemas` (couples the CLI to server internals, against ADR 0122's "a narrower view"), and a TypeScript CLI on `@lorenzo/api-client` (it would put Node on the GM's machine and give up R1's worker). The TypeScript option was proposed by one persona and withdrawn.
- **Auth.** There is no CLI client in Authgear today, so one has to be registered: a *public* native client using the authorization code flow with PKCE (`openid offline_access`, for a refresh token). Per Authgear's documentation as read by the review (not independently verified):
  - **No device authorization grant.** There is no documentation page for it, only an open 2023 feature request (`authgear-server#3184`), so it is treated as unsupported.
  - **Loopback with a fixed port works today.** `apps/api/scripts/get_dev_token.py` already uses the registered `http://127.0.0.1:8765/callback`; the CLI registers a fixed port and a fallback or two. Arbitrary loopback ports were requested (`#5692`) and a related change was closed on 2026-09-11 as included elsewhere; whether that has shipped to Cloud is unverified.
  - **Headless without a device flow.** `login --no-browser` prints the authorization URL; the user opens it on any machine and pastes back the redirected URL, whose `code=` the CLI exchanges. That covers WSL and SSH.
  - **Storage and scripts.** Tokens live in a `0600` file under `$XDG_CONFIG_HOME/lorenzo/` (headless WSL has no Secret Service); the `keyring` package is an optional extra. `LORENZO_TOKEN` / `--token-stdin` serve scripts.
  - **Not verified:** the portal's secret-less "native" application type, and refresh-token lifetime and rotation.

  `get_dev_token.py` can't be reused as is: it uses a confidential client with a secret. **Unattended use is out of scope** (decided with the maintainer): the CLI is run by a person, with their own token. For the record, Authgear's M2M tokens (client credentials) carry a `client_id_…` subject, not a user and not the `tenant-creator` role, so a future unattended `repo offer` would need its own `apps/api` ADR to accept them. Development doesn't wait on the client registration: `LORENZO_TOKEN` fed from `get_dev_token.py` unblocks coding.

### R3. The target: an existing repository tenant by default

Decided (amends the RFC's silence about which tenant is written to). The importer writes into an **existing** tenant named on the command line and reads its `kind`. It refuses a `play` tenant unless `--allow-play-tenant` is given, and that path is documented as **non-publishable**, because `kind` is immutable ([ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md)). The repository tenant is created beforehand, by someone with the `tenant-creator` role, through `POST /tenants` with `kind: repository`; the importer has no `--create-if-missing`. The plan header records the target's `kind` and whether it is **published**; importing into a published repository is allowed but flagged, since subscribers' `/updates` will show the changes.

### R4. Identity: the entity slug, not a tag and not a manifest

Decided (resolves §7's open seam). A tag is a `bool` stat and can't hold a key; a `text` stat definition would ship into every subscriber and collide on first copy ([ADR 0119](../adr/0119-copying-a-repository-into-a-tenant.md)), and is re-diffed on every sync. The natural key already exists: the entity slug ([ADR 0107](../adr/0107-entity-slugs-and-batch-resolve.md)), unique per tenant, copied, and compared on sync.

- **Slug.** `<namespace>-<list>-<slugified key>`, for example `basic-weapons-longsword`, within the slug grammar (`[A-Za-z0-9][A-Za-z0-9_-]*`, at most 100 characters; the readable part is truncated to fit). `<list>` is the MPMB list (`weapons`, `armour`, `gear`, `tools`, `ammo`, `packs`), so an item slug never has the shape of a taxonomy slug (bare, or `dnd5e-…`). The namespace keeps a bare `longsword` from colliding with a subscriber's own slugs.
- **The namespace is declared, not derived.** It is set in the mapping file, per input file or source set (`[namespaces]`), and defaults to `basic`. It is deliberately **not** computed from an item's own `source` field: `source` is citation data that changes (a reprint appends a second entry, a page number is corrected, and homebrew is always `["HB", 0]`), and identity must be a pure function of the input. Two homebrew authors sharing a repository declare distinct namespaces, and adopting an existing entity on a `resolve` hit requires matching prototype parents, otherwise it is a conflict. A namespace is a commitment, since renaming a slug doesn't rewrite `[[old-slug]]` text: the plan prints each namespace at first import, and a later run that would move an item to a different namespace reports "moved from A to B" instead of silently creating a second entity.
- **Where the source goes.** The item's citation is stored in a `sourcebook` **text stat** (for example `SRD 204; E 7, S 115`), never in the slug. It is a single seed definition (R9), so it ships once with the taxonomy rather than once per item, and it can be corrected later without touching identity.
- **Collisions.** When two raw keys in one run slugify identically, only the colliding members take a `sha256(list + raw key)[:6]` suffix. A member that already resolves in the tenant keeps its slug and only the newcomer takes the suffix. A slug held by a non-import entity, or refused with `409` on `PUT`, also takes the suffix. **`plan` records the final slug per key and `apply` executes the plan; it never recomputes it.**
- **Later file wins.** When two source files in one run define the same list key, the later one wins, as in the sheet. The plan reports the override and plans one entity, so a homebrew file that redefines an SRD key doesn't look like a collision.
- **Existence.** `GET .../entities/resolve` takes up to 100 slugs per call. The local run-manifest is a **disposable cache**, never the authority; the importer holds no per-machine truth, so a second machine or a CI runner behaves the same.
- **Creating.** `POST /items` gains an optional `slug`, mirroring `ItemInstanceCreate` (see [R11](#r11-small-appsapi-additions)), so create-and-name is atomic and a repeated `POST` for the same key is a clean `409` meaning "already imported". Against an API without the field, the importer falls back to create, then `PUT` the slug; if a run is interrupted between the two, the next run adopts only an item with **no slug, an exact name match, and the same prototype set**, found through `list_items?q=` and filtered client-side, and only when exactly one candidate matches; otherwise it goes to the review queue.

### R5. The mapping: one TOML file over a built-in seed

Decided (answers §3's "surfaced, not guessed" and the Consequences' "an ongoing maintenance cost"). The mapping is **data** with a documented schema, not a Python dict:

- **One project file** (`schema = 1`, TOML) overlays a **built-in seed in the same format**. Two layers, exact case-insensitive match, no fuzzy or regex keys. There is no tenant-alias layer: there is no list-typed stat and no stat-value filter, and an alias stat would ship into every copy. The tenant stays the source of truth for *what a category is*; the file only says *which source string points at which slug*.
- **Namespaces.** A `[namespaces]` table maps each input file or source set to the slug namespace of R4 (default `basic`); renaming one is a data change that `--reconcile` reports as slug changes.
- **Two separate sections** for weapon `type` (proficiency) and weapon `list`/`range` (reach); the second may be empty. Armour and tools have their own sections.
- **A disposition per value:** `map` (to an existing prototype), `create-under` (mint a prototype under a named **axis**), `attach-form-only` (attach to the base form prototype only and mark the item uncategorised), `skip` (not an item), or `fail`. A value resolved by an explicit disposition counts as resolved.
- **Axes, not free parents.** An entry names an axis (`form`, `proficiency`, or `tier`) and the CLI resolves the axis root by slug. It refuses a `dnd5e-` slug under a non-`dnd5e` axis and a bare core slug under a rules-layer axis; any other prefix (a homebrew `hb-`, say) is allowed.
- **Attributes.** A row for an attribute the seed has never seen may select only an **existing, parameterised transform**: store as an `int`/`text`/`bool` stat or a tag, `drop`, `denomination_sum`, `regex_extract`, `keyword_flag`, or `first_of`. There is no expression language and no plugin system. A brand-new *kind* of extraction is a code change; a new category, value, currency, or attribute is a row.
- **Prices** use `denomination_sum`: it sums every amount-and-unit pair in the display string, accepts thousands separators, and reads units from a `currencies` table in the same file, so `2 gp 5 sp`, `1,000 gp`, and a homebrew `3 marks` need no code.
- **Untrusted patterns.** Because homebrew strings run through these patterns inside the process that holds the token, `regex_extract` input is capped (about 300 characters), patterns are validated at load, and every regex row must carry inline `examples` (input to expected output) that run at load.
- **Teaching.** When the review step meets an unknown value it groups them, so each is asked once, and offers the dispositions above. Accepted rows apply in the same run and are written to a **`proposed.map.toml`** snippet; the input file is **never rewritten** mid-run, so a plan stays a pure function of its inputs. In interactive mode, after a successful `apply`, the CLI offers to append the snippet to the project file.
- **Determinism.** The plan header carries `{builtin_version, user_map_sha256}`. A run with a changed map reports "N items would change parents" and re-parents only with `--reconcile`; the default is create-only.

### R6. A non-interactive contract

Decided. `plan` emits deterministic JSON; `apply` executes it, and `apply --yes` never prompts. Exit codes: `0` nothing to do, `2` changes pending, `1` something unresolved. `--strict` never prompts and prints JSON of every unresolved *value* and unmapped *attribute*, each with the file and key that hit it and a ready-to-paste row; unmapped attributes are reported once per attribute name with an item count, not once per item. Everything unresolved goes to `review-queue.json`, fail-closed, never guessed. `plan`'s JSON carries the target tenant id, `kind`, `published` state, and counts, so a script has something to chain on. A re-run with nothing to change exits `0`, and `apply --yes` is safe to run unattended, repeatedly.

### R7. Bundles are data in the tenant

Decided (amends §6's "CLI-only" choice, the one settled decision the review reopened, for one concrete reason: a copy carries only tenant data, so a CLI-side table would leave every copying tenant, and loot-bot and inventory-web, with a pack that has no contents).

- A pack's contents are written into the **pack item's public description** (decided with the maintainer for v1), as a strict list, one line per entry, nested to show containment: `- 5 x [Rations, days of](basic-gear-rations-days-of)`. It is an ordinary LorenzoScript description, so it renders as a bullet list with clickable links in existing screens. Slugs are the machine keys. Pack `items` are display names, so the importer resolves each to a slug and puts the unresolved ones in the review queue.
- The description is written in a **second pass**, after every item it names exists. It is written at the **first import**, because information is copy-once and not re-synced ([ADR 0121](../adr/0121-repository-updates-and-re-sync.md)): a first release that omits it means earlier copies never get it.
- **Instantiation stays client-side.** Read the description (`GET /entities/{id}` returns each payload's `content`), create the container instance, then create each child with `container_entity_id` and its `quantity` (R11). This is orchestration over routes that exist or are added by R11.
- The CLI parses the list with a strict Python line grammar, not with `packages/lorenzoscript`, which is TypeScript. A description can also hold prose, so the parser reads only lines that match the grammar and ignores the rest, and a GM editing the description later can't break instantiation by adding a sentence. **Check, at implementation:** that the server leaves the description's `content` untouched on write ([ADR 0105](../adr/0105-lorenzoscript-entity-references-and-resolver.md)). If it doesn't, the fallback is a separate information entry, **never a CLI-only table**.

**The intuitive model, and why it isn't v1.** The natural picture is a pack that *is* a Backpack item with its contents as real items inside it. That is the right long-term home, as a first-class "a prototype defines its instantiation-time contents" capability (already named in [Not in scope](#not-in-scope)). It isn't buildable on today's API without new surface or catalog clutter: containment is written only through item-instance routes, so no route puts a *catalog* item in a container; `Containment`'s primary key is the child, so the same "Rations" can't sit in two packs and each pack would need its own clone ("Explorer's Pack: Rations"), which pollutes catalog search and ADR 0073's "what is built on Rations" lookup; and nothing instantiates a container's contents when the container is granted, so a client would walk the contents anyway. The information list avoids all of that, gives a free "which packs contain Rations" lookup through `GET /entities/{id}/backlinks`, and moving to real items later is mechanical: parse the list into containment rows.

Rejected: template `item_instance` rows marked with a tag. Ownerless instances are visible to every tenant participant and are listed by `GET /item-instances` and `GET /item-instances/unowned`, which inventory-web's board and loot-bot's `/drop` read as real unclaimed loot. Also rejected: shared catalog children, since `Containment`'s primary key is the child (one parent per child); and `entity_template` ([RFC 0018](0018-entity-template.md)), which has no contents concept.

### R8. The taxonomy: a system-neutral core and a `dnd5e-` layer

Decided (amends §3; keeps every node §3 named). Every node is an ordinary `Item` created through `POST /items` with `in_public_catalog=false`, so the re-parent tools of ADR 0073 work on it, and moving an edge later is one call.

```text
CORE (bare slugs; nothing 5e-specific)
physical-object     carries the weight recipe (R9)
├─ weapon
│  ├─ melee-weapon
│  └─ ranged-weapon
├─ armor
│  └─ shield
├─ tool
├─ container        is_container = true, inherited
├─ ammunition
└─ gear

DND5E (slugs prefixed dnd5e-, parentless mixins under one abstract root per axis)
dnd5e-weapon-proficiency   ├─ dnd5e-simple  ├─ dnd5e-martial  └─ dnd5e-improvised
dnd5e-armor-tier           ├─ dnd5e-light-armor  ├─ dnd5e-medium-armor  └─ dnd5e-heavy-armor
dnd5e-tool-proficiency     ├─ dnd5e-artisans-tools  ├─ dnd5e-gaming-set  └─ dnd5e-musical-instrument
```

A longbow is `ranged-weapon` + `dnd5e-martial`; a dagger (or any thrown weapon) is `melee-weapon` + `ranged-weapon` + `dnd5e-simple`; chain mail is `armor` + `dnd5e-heavy-armor`; a shield is `shield` alone (from a curated name list, since no `type` says it). Melee versus ranged comes from `list`/`range`, and a missing `list` is a review item.

- **Why Simple/Martial are prototypes, not tags or an enum.** The vocabulary is open (any string); growing an enum is an administrator's act and removing a used value returns `409`; enum and `bool` stats can't be comparison operands; and a prototype can carry information and defaults and be found by ancestry. The cost is that nothing stops an item being both Simple and Martial. The review step is the guard.
- **One tenant, both layers, for v1**, separated by slug prefix and by a `layer` key on every seed node and definition. Splitting the `dnd5e-` layer into its own repository would make it a bridge ([ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md)): items such as a longbow inherit from both layers and so must be authored in the bridge; the core repository must be published and copied first; each subscribing tenant needs two grants (copying the bridge brings core in one call); and a correction to core is republish, re-sync the bridge, republish the bridge, then subscribers sync. That is `repo offer` built early, which is why it isn't v1. **The layout has to be decided before the first publish or grant**, not before the first import, because splitting later costs more with each subscriber. A Warhammer table copies the core and adds its own layer; a sibling d20 system merges the dice stats. The maintainer's decision is to **assume the split works**: that a copy of the bridge keeps a homebrew category minted under an axis root that lives in the core repository. It hasn't been tested against ADR 0120's manifest rules, so it is the first thing to try when the split is made.
- **All three axis roots ship in v1**, so `create-under` always has a root to resolve and each axis can be enumerated.
- **Deferred without a later re-parent cost:** `body-armor` and `firearm`, the `prop_*` property tags (finesse, light, reach, thrown, versatile: keyword-matched from `description` and so fragile; a later opt-in row), `armor_dex_cap`, `strength_required`, the stealth tag, `ability`, `armor_formula` (an `ac` of `"10+Wis"` has no honest formula home, since a computed stat reads the entity's own stats, not the wearer's), and `size`. Custom weapon or tool types are **not** deferred: they are minted through R5's `create-under`, as a plain `POST /items` under an axis root.
- **Cost accepted:** about 20 nodes and 12 stat definitions must be bootstrapped before the first import, against §3's handful. The seed ships as data inside the CLI, an idempotent `seed` step prints what it will create, and it is find-or-create by slug and definition name.

### R9. The stats: twelve definitions, frozen once copied

Decided (amends §4, which mapped only weight and price and so dropped what makes a weapon a weapon):

| Group | Definitions | Layer |
| --- | --- | --- |
| `physical` | `own_weight` (float), `weight` (float), `contents_weight` (float), `range_normal` (int), `range_long` (int) | core |
| `economic` | `price` (int, in copper) | core |
| `destroyable` | `armor` (int) | core |
| `tags` | `is_container` (bool) | core |
| `sourcebook` | `sourcebook` (text): the item's citation, such as `SRD 204; E 7, S 115` | core |
| `damaging` | `damage_dice_count` (int), `damage_die` (int), `damage_type` (text) | dnd5e |

Every seed node (R8) and definition carries a `layer` key in the seed data, so the `dnd5e` layer can later become its own repository as a filter rather than a rewrite. The `damage_*` definitions are assigned to `dnd5e` **now**, because a definition can't be moved later. The core layer creates all five conventional groups (`physical`, `economic`, `destroyable`, `damaging`, `tags`) even where empty, so two system layers never collide on creating the same group.

- **Weight goes to `own_weight`, always.** [`well-known-stats.md`](../reference/well-known-stats.md) puts `weight = sum(own_weight, contents_weight)` on the base prototype, and a direct value beats an inherited formula. Writing MPMB's `weight` into `weight` would silently stop every imported backpack counting its contents. `contents_weight = contents(weight)` and `weight = sum(own_weight, contents_weight)` are computed stats on `physical-object`, not stored values; the bootstrap creates the recipe if the tenant lacks it.
- **Weight is `float`** (MPMB has `0.05` and `0.2`; scaling to integer centipounds would lock in a unit nobody can read). The bootstrap checks `value_type` and fails naming a definition already present with the wrong type. It also shows an attribute row's `value_type` in the review whenever a row creates a definition.
- **Frozen.** Stat groups and definitions have no `PATCH` or `DELETE`, and a changed `value_type` "is shown but can't be applied" on a re-sync (ADR 0121). The names and types above are therefore chosen once, and a subscriber's own same-named stat merges only if the types match; otherwise a rename is forced (ADR 0119), which the copy plan shows beforehand.
- **The importer acquires stat groups itself.** The generic entity-stat `PUT` doesn't add the stat's group to the entity (only the tag routes do), so grouped displays would omit imported stats otherwise. A fresh tenant has no default stat groups.
- **Known limit, and its fix.** `ItemOut.weight` is `int | null`, so a float weight reads `null` there and in `physical_stats`; the full value is in `GET /entities/{id}`'s `stats`, which is where the importer verifies until the named columns are fixed (R11).
- **Price** stays the named, fallible step of §4; a failed extraction goes to the review queue.

### R10. The publishing boundary stays, with an output contract

Decided. "Publish as a repository" stays exactly where §"Not in scope" put it: this RFC builds no `repo offer`, no `--sync`, and no tenant-creation hook. What the personas agreed had to move *now* is what becomes costly to change after the first import or first copy, so the RFC commits to an **output contract**:

1. A `repository`-kind target by default (R3), because `kind` is immutable.
2. Namespaced slug identity (R4), because slugs are baked into copies and a rename doesn't rewrite `[[old-slug]]` text.
3. Bundle data written into the tenant at first import (R7), because information is copy-once.
4. Neutral stat names and frozen value types (R9).
5. Machine-readable `plan`/`apply` output and a repeatable, non-prompting `apply --yes` (R6).

`lorenzo repo offer` is **reserved as the named follow-up** and needs its own RFC. Its steps are all existing API calls: grant the target (`PUT /tenants/{repo}/subscribers/{tenant}`, as the repository's owner), copy (as a member of the target), treat `409 repository-already-copied` as success, and optionally apply only clean updates. The realistic caller is the tenant creator, who owns both the repository and the target tenant and runs `offer` right after creating it, so a person's own token is enough. Unattended use is out of scope (R2). If the `dnd5e-` layer is split into its own repository (R8), `offer` also becomes a prerequisite of publishing at all, since a subscriber then needs two grants.

### R11. Small `apps/api` additions

Decided with the maintainer: the gaps the review found in `apps/api` are fixed rather than worked around. They are additive and optional, none is a new capability, and each is scoped and recorded as its own ADR when built (§2's and §6's "no new `apps/api` capability" still holds: bundles and the import pipeline need no new *capability*, only these ergonomics).

- **`ItemCreate.slug`** (optional, mirroring `ItemInstanceCreate`): create-and-name in one transaction, and a repeated `POST` for the same key is a clean `409` (R4).
- **`ItemInstanceCreate.quantity`** (optional, default 1): a stack of five rations is one create, not five creates plus merges (R7). It goes through the same capacity checks (ADR 0128) as any other create into a container.
- **Float-capable named columns**: `ItemOut.weight`, and the other named `int | null` columns where a stat is genuinely fractional, so a float weight reads correctly there and in `physical_stats` (R9).

Until they land, the importer uses the fallbacks named in R4, R7, and R9, so none of them blocks starting.

### Refinements after the owner's review

The repository owner read the amended draft, proposed changes, and decided the points it left open. The personas answered the proposals before they were folded into R1 to R11:

- **Slug namespace from the source (R4).** Proposed as `<source>-<list>-<key>`. Three personas preferred a declared namespace over one computed from an item's own `source`, and the coder dissented on the derived form outright, because `source` is mutable, polymorphic, and constant (`HB`) for all homebrew. Decided: `<namespace>-<list>-<key>`, namespace declared per input file in the mapping file (default `basic`), with the item's citation kept in a `sourcebook` text stat. This keeps "everything from this book" readable in the slug without tying identity to a field that changes.
- **Linux/WSL as the target (R1, R2).** Accepted by all. It removes the Windows spike, makes the worker a plain subprocess, and makes a `0600` credentials file the primary token store.
- **Bundles as real items (R7).** Proposed as a Backpack containing real child items. All four personas kept a list for v1 and named real items as the eventual home. The owner conceded, and decided the list lives in the pack's own description. The reasons are recorded under R7.
- **The `dnd5e-` layer as its own repository (R8, R9).** One tenant is the v1 default, every seed node and definition is tagged with its layer, and `damage_*` is assigned to `dnd5e` now, so the split stays a filter. The owner leans toward splitting eventually and decided to assume it works; the deadline is before the first publish or grant.
- **The JS host (R1).** The owner asked for the best-practice, most future-proof choice. R1 records the evidence and keeps `mini-racer` behind the engine protocol.
- **Auth (R2).** Unattended use is out of scope.
- **API gaps (R11).** To be fixed in `apps/api`, not worked around.
- **Auth (R2).** The owner asked whether a temporary loopback server or a device-authorization flow would work. Per Authgear's documentation, only the loopback flow is supported; device flow is not, so "headless" becomes a paste-the-redirect flow.

### How the two forced confrontations came out

- **Extensible mapping versus "an ongoing maintenance cost".** The coder's first position (rows are data, new transforms are code) left the homebrew author stuck on invented currencies, new attributes, and prices in formats the maintainers hadn't seen. The author's first position (three layers, including an alias stat on the prototypes) spread one concept over three places and made a plan depend on tenant state. They met at R5: two layers, every routine gap a data row, a small closed set of parameterised transforms, and teaching that emits rather than mutates. The maintenance cost doesn't disappear, but a new category, value, currency, or attribute is no longer a code change; only a new kind of extraction is.
- **"Automate across tenants now" versus deferring publishing.** The tenant creator argued the Consequences line was false as written, and she was right (R3). She also proposed building `offer`, `--sync`, and bundles as template instances; the first two are deferred, the third was withdrawn after she checked the code (R7). The boundary holds; the output contract is the cheap part that couldn't wait.

### What each persona gave up

- **Quiril:** the tenant-alias layer and `--teach-tenant`; the three-layer resolution (now two); an interactive picker as anything but a convenience; fuzzy or regex mapping keys; and his dispositions writing straight to his file.
- **Rasmus:** the `source_key` stat and the manifest as authority; free-form transforms in the map; a shared client package; and bundles kept only in the CLI. He also takes on the JS-host spike and an 82 MB dependency. (`ItemCreate.slug`, which he asked for, was later adopted: R11.)
- **Silva:** her TypeScript CLI; bundles as template instances; `--create-if-missing`, `repo offer`, `--sync`, and a tenant-creation hook *now*; the `source_key` stat; YAML for the config.
- **Tonja:** the two-repository default; per-layer stat groups; exclusivity between Simple and Martial; readable float weights in `ItemOut.weight`; a fast first import (about 20 nodes and 12 stat definitions first). One caveat she named and accepted: `damage_dice_count`, `damage_die`, and `damage_type` are dice-system names in the shared `damaging` group, inert but permanent for a tenant that never uses them.

### Unresolved

What remains is implementation-time checking, not open design. Each item has a fallback already written into the section it belongs to:

- **The JS-host checks** (R1): the sheet's own SRD scripts through the worker (entry counts, stubbed names, peak heap against the 64 MB cap, `$fn` values), and what a chained call on a stub does.
- **The description check** (R7): that the server leaves a pack description's `content` untouched on write. If it doesn't, the list moves to a separate information entry.
- **Authgear** (R2): registering the public CLI client and its fixed loopback port, and checking whether arbitrary loopback ports, a secret-less native application type, and the refresh-token lifetime behave as the documentation reads. WSL2 browser launch and localhost forwarding are untested; `login --no-browser` is the fallback. This blocks shipping `login`, not development.
- **The `dnd5e` split** (R8): decided to be assumed workable, and undecided as to *when*. The deadline is before the first publish or grant, and its first check is the axis-root copy path through ADR 0120's manifest rules.
- **The three `apps/api` additions** (R11) each need their own ADR when built.
- **When the deferred `prop_*` tags earn an opt-in row** waits for a second game system or a real need.

Out of scope on purpose: unattended use and its machine credential (R2), `repo offer` and `--sync` (R10), and real child items for bundles, which wait for "instantiate with contents" as a designed `apps/api` capability (R7).

### Status

Moved from `proposed` to `accepted`, decided with the maintainer on 2026-09-29. Every persona signed the ten amendments (Quiril, Rasmus, and Silva after small wording changes, Tonja after two corrections to how her taxonomy was transcribed), and the maintainer then decided each point the review left open: the bundle list, the JS host, unattended use, the `sourcebook` stat, the `dnd5e` layer, and the `apps/api` gaps. What is left in [Unresolved](#unresolved) is checked while building, and each item has its fallback written down. It is built in slices, each recorded as its own ADR when it lands, with a tracking Issue per slice under [ADR 0070](../adr/0070-planning-milestones-issues-and-a-deferred-roadmap.md):

1. **The `apps/cli` app** and its stack: scaffolding per [docs/guides/adding-an-app.md](../guides/adding-an-app.md), the Python client, and auth (R2). Built: [ADR 0137](../adr/0137-lorenzo-cli-app-python-client-and-auth.md).
2. **The JS host**: the worker, its protocol, and the golden corpus (R1). Built: [ADR 0138](../adr/0138-lorenzo-cli-js-host.md), with the spike's results.
3. **The `apps/api` additions** (R11). Built: [ADR 0139](../adr/0139-name-an-item-when-it-is-created.md), [0140](../adr/0140-a-stack-when-an-item-instance-is-created.md), [0141](../adr/0141-fractional-weights-in-the-named-columns.md), and, a fourth the review had missed, [0142](../adr/0142-acquiring-a-stat-group-on-the-generic-stat-put.md).
4. **The mapping file and identity**: the seed format, dispositions, namespaces, slugs, and the `plan`/`apply` contract (R4, R5, R6). Built: [ADR 0144](../adr/0144-lorenzo-import-mapping-identity-plan-apply.md).
5. **The taxonomy and stat seed** (R3, R8, R9). Built: [ADR 0143](../adr/0143-lorenzo-seed-taxonomy-and-stats.md).
6. **Packs** (R7). Built: [ADR 0145](../adr/0145-pack-contents-in-the-description.md).

An ADR number was claimed for a slice when its work started, as [AGENTS.md](../../AGENTS.md) describes. Building it against the sheet's real data confirmed the design and refined it in places, all recorded in those ADRs (for example: evaluation needs the sheet's base data first, a pack counts in the units of its name, and stat-group acquisition needed a fourth `apps/api` addition).
