# 0144 - `lorenzo plan` and `lorenzo apply`: the mapping file, identity, and the non-interactive contract

Status: accepted

Slice 4 of [RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md) (R4, R5, R6). Builds on [ADR 0138](0138-lorenzo-cli-js-host.md) (evaluation), [ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md) (the taxonomy and stats it writes into), and the `apps/api` additions of [ADR 0139](0139-name-an-item-when-it-is-created.md) to [ADR 0142](0142-acquiring-a-stat-group-on-the-generic-stat-put.md).

## Context

This is the importer itself: turn what the JavaScript host read into items in a tenant, safely enough to run again, unattended, and against homebrew nobody has seen. RFC 0025 decided the shape: a mapping that is data, a slug as identity, a `plan` that changes nothing and an `apply` that carries it out. Building it against the sheet's real data (236 entries in the SRD's six lists) settled the details this ADR records.

## Decision

### The pipeline

`plan` and `apply` evaluate the files (`--base` first, then the content files), map every entry to a *draft* (name, parents, stats, description, and anything that needs deciding), look at the tenant, and work out a status per item. `plan` prints or writes that and stops. `apply` does the same and then writes. They share one code path, so what `plan` says is what `apply` does.

A draft is a pure function of the entry and the mapping. It reads nothing from a tenant, so the same inputs give the same plan.

### The mapping file

One `schema = 1` TOML file overlays a built-in one of the same format (`importer/builtin_map.toml`), row by row. It is validated when loaded (dispositions, slug grammar, transforms and their parameters, regular expressions and their examples), so a wrong map fails before anything else happens. The plan header carries `{builtin_version, user_map_sha256}`.

- **Classification** (`[classify.<list>.<attribute>]`) maps a value to parents. Matching is exact and case-insensitive; there are no fuzzy or regex keys. A row is a list of parent slugs, or a disposition: `map`, `skip` (not an item: a bare hand, a cantrip, how the sheet works out AC), `attach-form-only` (only the list's form; the item is marked uncategorised), `create-under` (mint a category under an axis root), or `fail`. `replace_form` drops the list's own form (a bundle of ammunition is ammunition, not gear). A `"*"` row answers every other value.
- **Axes, not free parents.** `create-under` names an axis (`form`, `proficiency`, `tier`), and the list says which root that is. The loader refuses a `dnd5e-` slug under the form axis, a bare slug under a game system's axis (a category there says whose it is: `hb-…`), and any slug the seed already uses.
- **Attributes** (`[attributes.<list>]`) name what each MPMB attribute becomes: a transform, or a table with parameters. The set of transforms is closed. Plain: `drop`, `name`, `sourcebook`, `description`, `own_weight`, `damage`, `range`, `armor`, `classify`, `name_and_price`, `pack_contents`. Parameterised: `int`, `float`, `text`, `bool`, `denomination_sum`, `regex_extract`, `keyword_flag`, `first_of`. There is no expression language and no plugin system; a new *kind* of extraction is a code change, and a new category, currency or attribute is a row. A rule may write a stat the tenant lacks by naming its `group`; the plan lists the definition it would create.
- **Prices** are sums of amounts of known currencies (`[currencies]`, in copper) in the last bracketed or parenthesised group of a display string: `[25 gp]`, `(16 gp)`, `[2 gp 5 sp]`, `[1,000 gp]`. A group that isn't made of known currencies (`(20)`, `(10 feet)`) isn't a price, and a plural is the same currency (`3 marks` needs only `mark`). A miss holds the item and says which groups it saw.
- **`regex_extract`** is capped at 300 characters of input, its pattern is validated at load, and its inline `examples` run at load and must pass.
- **Name rules** (`[[name_rule]]`) add parents from a curated list of name prefixes: `backpack`, `pouch`, `quiver`… give `container`, and `shield` gives `shield`. The project's rules come first.
- **Namespaces** (`[namespaces]`) map an input file's name to the slug namespace of its items, default `basic`.

### What the SRD's real shapes decided

- **The name** of a gear or tool is its `infoname` without the price (`Acid (vial)`), of armour and ammunition its `invName` when it has one (`Padded armor`), and of a pack its `name` without the price. The later `name` rule in the map's order wins.
- **Weight** is the weight of one times `amount` when the entry is a bundle (20 arrows at 0.05, 50 feet of rope at 0.2), and is written to `own_weight` as a float (R9).
- **Reach** comes from `range` as well as `list`: `Melee` is melee, a distance (`60 ft`, `150/600 ft`) is ranged and gives `range_normal` and `range_long`, and `Melee, 20/60 ft` is both, so a dagger is `melee-weapon` + `ranged-weapon` without a special case. A weapon that comes out as neither and has no `list` row that settles it is held.
- **Parents are reduced:** one that another parent already implies is dropped (`weapon`, once `melee-weapon` is there), and a tier stays alongside its form, because a tier is a parentless mixin.
- **Not everything is an item.** Of the SRD's 236 entries, 15 are skipped by the built-in map: the bare hand, the spell attack, the cantrips, and the two ways the sheet works out AC.

The built-in map imports the whole SRD (221 items) with nothing held for review and no attribute left unexplained.

### Identity

- **The slug** is `<namespace>-<list>-<slugified key>` (`basic-weapons-longsword`), a pure function of the input: the namespace is declared, not derived from an item's own `source`, which changes.
- **Collisions.** When two keys in one run slugify alike, every member takes `-` and the first six hex digits of `sha256(list + key)`, so which came first can't matter. A slug the tenant holds for something that isn't an item also makes ours take the suffix. `plan` records the final slug per key and `apply` never recomputes it.
- **Later file wins,** as in the sheet, and the plan reports each entry a later file replaced (this needed the JS host to report overrides, added here).
- **Existence** is `GET …/entities/resolve`, in batches of 100. The tenant is the authority.
- **The run manifest** is a disposable cache under `$XDG_STATE_HOME`, used only to notice that an item's namespace has changed: the plan then says "moved from A to B", holds it, and `--accept-moves` creates the new slug. Losing the manifest loses that warning and nothing else.

### The plan

Each item has a status: `create`; `complete` (it exists but an earlier run stopped part-way); `exists`; `held` (something needs deciding); `moved`; or `skipped`. An existing item is complete if it has `sourcebook`, which `apply` writes last, so a run that died in the middle is finished by the next one and never mistaken for done. Creating uses `POST /items` with the slug, so a repeated create is a `409` that means "already there".

The plan is JSON (`--json`, `--output`) with a header (map versions and hash, seed version, the tenant's id, kind and whether it is published, counts), the items, new categories and definitions, overrides, stubbed sheet names, files that stopped part-way, problems, and unmapped attributes. Two plans of the same inputs are the same document.

A tenant that hasn't been seeded is a *problem* (`lorenzo seed` first), listed once; nothing is written.

### The non-interactive contract

- **Exit codes:** `0` nothing to do, `2` changes pending, `1` something unresolved. Unresolved is: a held or moved item, a problem, a source file that stopped part-way, and under `--strict` an attribute no rule mentions. `apply` exits `0` when everything it should do is done and nothing is left, `1` otherwise, and `2` never.
- **`apply --yes`** never asks and can run unattended, repeatedly. Without `--yes` and without a terminal it refuses. It writes what is resolved and holds back the rest.
- **What needs a decision** goes to `review-queue.json` (value, reach, price, name, move, and unmapped attribute, each with a ready-to-paste row), and the rows to `proposed.map.toml`. Nothing unresolved is guessed and the map file is never edited.
- **`--teach`,** at a terminal, asks about each unknown value once (attach, map, create a category, skip, fail, or leave), uses the answer in the same run, keeps the rows, and after a successful import offers to append them to the map. It appends only if the result is still valid TOML, and otherwise says where to paste.
- **`--reconcile`** counts, and applies, changed parents (`PUT …/prototypes` with `If-Match`); by default a changed map only reports "N items would change parents".
  - *Addendum, 2026-10-04: one change needs no flag, [ADR 0165](0165-a-description-is-titled-with-its-items-name.md): a description the importer titled "Description" is retitled with its item's name, as a `complete` item in the plan.*
- **`--public-catalog`** lets players list the imported items; by default they are not.

### Writing

For each item: create it (parents, slug), write its stats with `acquire_group` (ADR 0142), its description as a public `description` information entry, and `sourcebook` last. One item failing is reported and does not stop the others.

## Consequences

- Slugs are baked into copies and `[[slug]]` links, and a rename doesn't rewrite them. The namespace is therefore a commitment; the plan prints it, and a change is a "moved", not a quiet duplicate.
- Importing the SRD itself means giving the sheet's data files as `--base` (they are GPL-3.0 and are not shipped). Homebrew that patches SRD entries needs them too.
- Reading the tenant costs one `GET` per already-imported item, and writing about three to six calls per new one; nothing is parallel yet. The SRD takes a couple of minutes against a local API.
- A pack's contents are written into its description in a second pass, after the items they name; that is [ADR 0145](0145-pack-contents-in-the-description.md).
- The built-in map is a maintained artefact. MPMB will add attributes and homebrew will invent more; the answer is a row, and the cost is that someone keeps the built-in one current.
- `plan` and `apply` write `review-queue.json` and `proposed.map.toml` in the working directory (or where `--review-queue` and `--proposed-map` say) when there is something to decide, and leave an older copy alone when there isn't.
