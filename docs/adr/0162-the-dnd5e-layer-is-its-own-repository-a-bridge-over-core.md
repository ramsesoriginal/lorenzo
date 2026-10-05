# 0162 - The D&D 5e layer is its own repository, a bridge over core

Status: accepted

Decides the question [RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md) R8 left open, with the maintainer, on 2026-10-03. Amends R8's "one tenant, both layers, for v1". Builds on [ADR 0120](0120-bridge-repositories-and-dependency-manifests.md), [ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md) and [ADR 0159](0159-lorenzo-repo-commands.md); [ADR 0163](0163-lorenzo-repo-offer-offers-what-a-bridge-builds-on.md) is its other half.

## Context

R8 split the seed into a system-neutral **core** (`weapon`, `armor`, `container`, the weight recipe, the stat definitions) and a **`dnd5e`** layer (the proficiency and tier categories, the dice stats), tagged every entry with its layer, and shipped both into one repository tenant for v1. It said the layout "has to be decided before the first publish or grant", because splitting later costs more with each subscriber, and that the owner leaned toward splitting and decided to assume it works. The assumption was named and not tested: that a copy of the bridge keeps a homebrew category minted under an axis root that lives in the core repository.

[ADR 0159](0159-lorenzo-repo-commands.md) made publishing and granting reachable from a terminal, so the decision came due. The maintainer's answer is to split.

## Decision

**Two repositories, not one.**

- **Core**: the system-neutral taxonomy, the stat groups and definitions, and the weight recipe. Seeded with `--layer core`. A Warhammer table, or a sibling d20 system, builds on it without carrying D&D.
- **D&D 5e**: a repository that has **copied core** and seeded `--layer dnd5e` on top of its copy. Per ADR 0120 that is what makes it a bridge: no new kind or flag, just a repository with a copy of another. The imported items live here, because a longbow is `ranged-weapon` (core) and `dnd5e-martial` (D&D), and an entity can only be authored where both parents exist.

```bash
lorenzo tenant create "Core" --slug core
lorenzo seed --tenant core --layer core --yes
lorenzo repo publish --tenant core

lorenzo tenant create "D&D 5e" --slug dnd5e
lorenzo repo grant dnd5e --tenant core
lorenzo repo copy core --tenant dnd5e --yes
lorenzo seed --tenant dnd5e --layer dnd5e --yes
lorenzo apply --tenant dnd5e --base ... --yes          # the SRD, parented in both layers
lorenzo repo publish --tenant dnd5e
```

The seed needs no change to allow this. It finds nodes and definitions by slug and name, so the copy of core in the bridge satisfies the D&D layer's needs exactly as a seeded core would, and `--layer dnd5e` on an empty tenant still says to bring core first.

**A table takes both.** A tenant drawing on the bridge needs a grant on each repository in its manifest, since grants aren't transitive (ADR 0120), and one `copy` of the bridge brings core in first. `lorenzo repo offer` does the granting for the person who owns both ([ADR 0163](0163-lorenzo-repo-offer-offers-what-a-bridge-builds-on.md)).

**A correction to core travels in four steps**, which is the cost R8 named:

1. core publishes again;
2. the bridge takes it: `lorenzo repo updates core --tenant dnd5e --apply`;
3. the bridge publishes again;
4. each table takes it on core's own route: `lorenzo repo updates core --tenant <table> --apply`.

*(Addendum, 2026-10-05: [ADR 0183](0183-setting-up-the-four-repositories-and-what-trying-it-showed.md) tried it. Steps 1 and 4 are what a table needs: `repo updates` reads core as it is, so a table sees a correction before the bridge has taken it or published again. Steps 2 and 3 are the bridge keeping its own copy current, which it does when its author wants to, and before it writes anything that depends on the correction.)*

**What did not change.** The seed's data and its `layer` tags, the `dnd5e-` slug rule, item slugs (`basic-weapons-longsword`) and namespaces, and `lorenzo seed`'s default. Without `--layer` it still seeds both layers into one tenant, which is fine for a table's own use and for trying things; it now says so, and says to seed the layers into separate repositories if they are to be published. Making `--layer` mandatory would break every existing invocation of a pre-1.0 command for no gain to someone who isn't publishing, so it is left as a choice to make once the split is the habit. *(Addendum, 2026-10-04: [ADR 0166](0166-a-bare-seed-refuses-to-add-a-layer-to-a-tenant-that-holds-another.md): that default no longer adds a layer to a tenant that holds a different one.)*

### The assumption, tried

R8's assumption holds. `tests/e2e/test_split.py` builds core, a bridge over it with the D&D layer and imported weapons, and a table's tenant, against the real API. A weapon type mapped with `create-under` on the `form` axis mints a category under core's `physical-object` (`tests/e2e/fixtures/legendary-form.map.toml`). After the table copies the bridge, that category is there with the table's own copy of `physical-object` as its parent, the same entity core's copy produced, not a second one and not a dangling reference. The weapons parented in both layers keep both parents. The other checks in that file cover the two-grants plan and a correction to core reaching the bridge and then the table.

## Not in scope

- **Moving content that was already published.** Nothing was, which is why now was the time.
- **A command that builds the pair.** The sequence above is nine commands, each already built. If it is run often enough to want one, that is a small follow-up.
- **A third repository, for items only.** Items inheriting from both layers could live in a repository of their own that copies core and D&D, but R8's cost accounting (two grants, one bridge) is the reason it isn't.
- **Splitting `dnd5e` further** (an SRD repository, a homebrew one). Another bridge over the same bridge is possible with ADR 0120 as it stands, and not needed yet.

## Consequences

- Core is the thing every system layer rests on, so its names and types are as frozen as the seed already made them ([ADR 0143](0143-lorenzo-seed-taxonomy-and-stats.md)), and now for every bridge as well.
- A bridge's own edits to its copies of core don't reach subscribers (ADR 0120): to make a core entity behave differently under D&D, the bridge authors a new entity that inherits from it. The importer already works that way, parenting items under core's forms and D&D's categories rather than editing either.
- A new table needs two grants and one copy, or one `offer`; a correction to core is four steps rather than one. Both are the price of keeping D&D out of a repository that isn't D&D's.
- RFC 0025's R8 and its Unresolved list now point here for the layout, and ADR 0143's "assumed, not tested" has been tested.
