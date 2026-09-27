# RFC: Carrying, holding, binding, and capacity — what a being has on it, and the rules that follow

Status: accepted, decided with the maintainer on 2026-09-26. Built in the seven slices in [Slices](#slices), each recorded as its own ADR when it lands: slice 1 as [ADR 0123](../adr/0123-held-by-listing-and-the-equipped-column.md), slice 2 as [ADR 0124](../adr/0124-groups-own-things-and-moving-is-not-giving.md), slice 3 as [ADR 0125](../adr/0125-giving-a-container-with-its-contents.md), slice 4 as [ADR 0126](../adr/0126-sum-formulas.md), slice 5 as [ADR 0127](../adr/0127-contents-formulas.md). Both apps consume it through `@lorenzo/api-client`, ADR 0122, decided alongside this RFC on its own branch.

## Context

The maintainer asked for a set of changes to items and item management:

- rename "magical" items to "special", and "cursed" to "bind on equip";
- add "bind on pickup" and "bind on own";
- give every being an "Equipped" container: what it actually has on it, with mechanical consequences for the three bindings;
- a computed stat that sums other stats, for weight, armour class, or hit points;
- carrying capacity by weight, containment capacity by size, and a rule against a backpack in a belt pouch;
- ownership by groups, not only by beings;
- showing an item's owner when it isn't the viewer's own;
- asking whether a container's contents go with it when it's given, and a way to give everything in a container at once.

Much of this touches decisions already made:

- **The bucket already exists.** [ADR 0041](../adr/0041-containment-quantity-and-stacking.md) named a per-character "Equipped" or "Carried" entity as one way to give a stack a home. [ADR 0115](../adr/0115-hand-over-on-give-and-stacks-leave-containers-into-their-owner.md) chose the character itself: an item contained directly by a character is "carried, in no container".
- **"Holds" already has a meaning.** The change feed ([ADR 0099](../adr/0099-player-facing-change-feed.md)) says a character holds an item if it owns it, contains it at any depth, or owns something that contains it at any depth.
- **Ownership is already generic.** `ownership.owner_character_id` references any entity ([ADR 0025](../adr/0025-character-being-and-ownership.md)), and no route checks what kind of entity the owner is. But nothing else treats a group as an owner. Members can't see or manage what a group owns, GMs can't reach it, and the change feed only counts characters.
- **Carrying already grants giving.** Self-service item writes ([RFC 0005](0005-item-and-item-instance-crud-api.md), [ADR 0032](../adr/0032-item-and-item-instance-crud-api.md)) are allowed for anything reachable from the caller's characters through ownership or containment, "uniformly regardless of what the write itself changes". So a player can give away another character's sword that happens to sit in their backpack.
- **Formulas stay on one entity.** [RFC 0016](0016-stats-computed-values-and-crud-api.md) and [ADR 0104](../adr/0104-computed-stats.md) excluded cross-entity aggregation ("the weight of everything in this bag") explicitly. Formulas read only the entity's own resolved stats, evaluated in pure Python.
- **The board shows ownership, not possession.** inventory-web's board and loot-bot's `/inventory` both read `GET .../item-instances/owned-by/{id}`. An item a character carries but doesn't own never appears there.
- **`is_magical`/`is_cursed` are hardcoded but unused.** They are named columns in `v_item`/`v_item_instance`'s SQL and `ItemOut`. No client reads them; both apps label tags from the tag's own name. [ADR 0047](../adr/0047-item-catalog-search-and-container-convention.md) already chose a naming convention (`is_container`) over adding to that list.
- **A bug in the same area.** Deleting a container item cascades its contents' containment rows away. They silently leave every container, and a stack among them loses its count, the loss ADR 0115 closed for `DELETE .../container` but not for this path.

## Decision

### 1. Three words: owns, carries, holds

- **Owns**: the `ownership` row. Unchanged.
- **Carries**: a being carries everything contained under it, at any depth. What's contained *directly* by the being is what it has equipped: worn, wielded, or held in hand.
- **Holds**: ADR 0099's relation, unchanged. A being or group holds what it owns, what it contains at any depth, and whatever sits inside something it owns. If my item is in a chest in Gerold's carriage, Gerold holds it (he owns the carriage) and so do I (I own the item), but only the carriage carries it.

Capacity and binding are about carrying: physical facts. Listings and boards are about holding: what a being or group has a stake in.

### 2. The being is its own Equipped container

No new entity. "Equipped" is how clients name what's contained directly by a being. ADR 0115's "carried, in no container" becomes "equipped", and ADR 0115's hand-over puts a gift into the recipient's hands, which is Equipped.

This keeps formulas that belong to the being on the being: a character's carrying capacity can read its own strength, and its armour class can sum what it wears (§6).

### 3. The held-by listing, and a board that always shows Equipped

`GET /tenants/{tenant_id}/item-instances/held-by/{entity_id}` lists everything the entity holds (§1), for a being or a group:

- grouped by direct container, like `owned-by`;
- the entity's own group first. For a being that's **Equipped**, and it's always present, even when empty;
- each group names its container and where that container is, so a client can draw nesting and say "in the Carriage";
- each item carries an `owner` summary, so a client can mark what isn't the viewer's own;
- visibility as `owned-by` ([ADR 0040](../adr/0040-item-instance-read-visibility.md)): an item whose owner the caller can't reach doesn't appear.

inventory-web's board reads it:

- **Equipped** is always the first column and always a drop target, even when empty.
- Each carried container gets a column. What's held elsewhere comes after, labelled by where it is.
- An item not owned by the board's being shows its owner ("Pia's", "the Company's").

loot-bot's `/inventory` shows the same structure in its own form.

`owned-by` stays as it is.

### 4. Groups can own things

The schema already allows any entity as owner, and no validation is added. Support is built for two kinds of owner, beings and groups:

- **Reading.** A player sees what a group owns if one of their characters is a member (the reachability walk gains "owned by a group my character belongs to"). GMs of any member's campaign see it too ([ADR 0035](../adr/0035-campaign-scoped-gm-visibility.md)).
- **Managing.** The same people manage it, under §5's split.
- **The change feed.** Members of an owning group count as holders, so they're told when the group's things change.
- **The API field** `owner_character_id` keeps its name, to avoid breaking every client. Its description says it names the owning entity.

A group isn't a being, so nothing a group owns ever binds (§8).

### 5. Moving and giving are separate permissions

This revises RFC 0005/ADR 0032's single self-or-managed check for writes to an item that has an owner:

- **Where it is** (setting or clearing its container, bulk moves, splitting a stack in place, merging stacks): anyone who holds it may, as today, and GMs.
- **Who owns it** (setting or clearing the owner, bulk-assign, splitting to a new owner, handing over, deleting it): only whoever controls the owner. That means a player whose character owns it, a player whose character is a member of the owning group, or a GM of the owner's campaigns.

An item nobody owns keeps today's rule unchanged. Loot drops and claims ([ADR 0052](../adr/0052-loot-bot-loot-drop-and-claims.md)) only ever write ownerless items, so they're unaffected.

### 6. Two new formula kinds: `sum` and `contents`

This revises RFC 0016's exclusion of cross-entity aggregation, for one kind only.

- **`sum`**: `round(Σ coefficient × stat + offset)`, over one or more stats of the same entity. It's `linear` with more than one term, so it evaluates the same way and is authored the same way (tenant-admin tier, dry-run preview, cycle-checked). Examples: `armour_class = 10 + dex_modifier + worn_ac_bonus`; `current_hp = max_hp − damage`.
- **`contents`**: `Σ stat × quantity` over the entities contained *directly* in this one, `quantity` being each containment row's stack count ([ADR 0041](../adr/0041-containment-quantity-and-stacking.md)). The stat is resolved on each child, so a child's own `contents` or `sum` formula is evaluated first. That makes a sum over nested containers fall out of two direct-children formulas, with no recursion in the formula itself.

How `contents` behaves:

- A child without the stat counts as 0. An entity with nothing in it gives 0. One unweighed torch mustn't blank a whole backpack.
- It counts everything physically inside, including items the reader can't see. Weight is a physical fact; the maintainer chose this knowingly.
- Evaluation loads the entity's containment subtree and works bottom-up. Containment cycles are allowed ([ADR 0016](../adr/0016-containment.md)), so the walk is path-guarded like `entity_access`'s. A cycle leaves the stats involved without a value, as a formula cycle does today. The existing depth cap of 50 applies.
- The write-time cycle check treats a `contents` edge as going down a level, not as an edge between stats of one entity. `weight` reading `contents_weight` reading children's `weight` is legitimate.

The weight recipe these make possible, all tenant data on prototypes:

| Where | Stat | Formula |
| --- | --- | --- |
| the base item prototype | `contents_weight` | `contents(weight)` |
| the base item prototype | `weight` | `sum(own_weight, contents_weight)` |
| a dagger | `weight` | `1` (a direct value wins over the inherited formula) |
| a Bag of Holding | `weight` | `15` (a direct value: its contents don't weigh on its carrier) |
| the base character prototype | `carried_weight` | `contents(weight)` |
| the base character prototype | `carry_capacity` | `linear(strength × 15)` |
| the base character prototype | `worn_ac_bonus` | `contents(ac_bonus)`: only what's directly on the being, meaning equipped |

So "a container's weight is its contents plus its own weight, unless it's a bag of holding" is a default defined once, as data, on the tenant's base prototype. It isn't hardcoded in the API. A system without encumbrance simply doesn't define it, and a repository ([RFC 0024](0024-repositories.md)) can ship the recipe for its tenants.

### 7. Capacity

The API reads stats by well-known name, the convention `is_container` set ([ADR 0047](../adr/0047-item-catalog-search-and-container-convention.md)): tenant-authored, nothing seeded, a rule applying only where its stats are defined.

| Stat | On | Rule |
| --- | --- | --- |
| `carry_capacity` | a container or a being | the weight of what's directly inside, `Σ weight × quantity`, may not exceed it |
| `containment_capacity` | a container | `Σ size × quantity` of what's directly inside may not exceed it |
| `max_item_size` | a container | no single item larger than this goes in |
| `weight`, `size` | the items | read as resolved, so a formula counts |

- **When it's checked.** On every write that changes where an item is: setting a container, bulk moves, handing over, creating an item inside a container.
- **What's checked.** The API applies the change inside the transaction, then evaluates the target container and every container above it. A stone put into a backpack also loads the character carrying it. A Bag of Holding stops the climb naturally, since its own weight is fixed. `containment_capacity` and `max_item_size` apply to the target only.
- **What's never refused.** Taking something out. A container that's already over capacity (the character's strength was drained) isn't emptied, and nothing more goes in until it's back under.
- **Refusal.** `409 capacity-exceeded`, naming the container, the stat, the limit, and what the load would have been.
- **Races.** The target's containment chain is locked for the check, so two concurrent moves into one bag can't both pass.
- **`size_order` isn't built.** With `size` and `containment_capacity`, a backpack already doesn't fit in a belt pouch. `max_item_size` covers "a quiver takes arrows, not a sword" on the same scale.

### 8. Binding

**The stat.** One well-known enum stat, `binding` ([ADR 0103](../adr/0103-stat-tags-enum-values-and-mandatory-groups.md)), replacing `is_cursed`. It's nullable: unset means no binding. Its vocabulary is `on_pickup`, `on_equip`, `on_own`, and `none`. `none` exists only because a stored stat can't be null (`entity_stat`'s one-value check). An instance whose prototype binds needs a real value to say "not this one".

**Binding is always to the owner:**

| `binding` | Bound when | Then the owner… | Then the item… |
| --- | --- | --- | --- |
| `on_own` | a being owns it | can't change | can't leave what the owner carries, once it's there |
| `on_pickup` | its owner carries it | can't change | can't leave what the owner carries; moving between the owner's own containers is fine |
| `on_equip` | its owner has it equipped | can't change | can't leave the owner at all, not even into the owner's own backpack: stuck while worn |

**Derived, not stored.** Whether an item is bound follows from where it is and who owns it, and a bound item can't move or change hands on its own. So it stays bound until a GM moves it or gives it away, which is the curse lifted. If it's picked up again, it binds again. `ItemInstanceOut` gains a computed `bound`, so clients show it and can disable what would be refused.

**What binding checks:**

- **Moving a container** checks what's inside it. A backpack holding a bound ring can't be put in a chest or handed over. The refusal names the ring.
- **Owner changes are all owner changes.** Setting or clearing the owner, bulk-assign, splitting to a new owner, and giving with contents (§9) all count. For §9, a bound item inside a given container keeps its owner and is reported, not a reason to refuse the rest.
- **Stacks** bind as a whole. Splitting in place keeps both halves where they are, so both stay bound.
- **Deleting** a bound item isn't an owner change or a move; a potion can be drunk.
- **Refusal.** `409 item-bound`, naming the item, its binding, and its owner.

**The GM.** A GM's write may carry `override: true` ("Move anyway"). It skips capacity and binding for that write, and the activity log records that it was overridden. The same write may also carry `lift_binding: true`, which sets that instance's own `binding` to `none`, so it won't bind again. A caller who isn't a GM for the item gets `403` for either flag.

**The named fields go.** `is_magical` and `is_cursed` leave `v_item`, `v_item_instance`, and `ItemOut`. That's a breaking change: an entry in `openapi-breaking-accepted.txt`, backed by the slice's ADR. There's no data migration. A tenant renames its own `is_magical` tag to `is_special`, and moves `is_cursed` to `binding: on_equip`. Renaming stat definitions by migration would show up as changes in every tenant that copied a repository ([ADR 0121](../adr/0121-repository-updates-and-re-sync.md)).

### 9. Giving a container, and giving what's inside

- **`with_contents: true`** on `PUT .../owner` and on a `bulk-assign` entry. Everything inside the container, at any depth, whose owner the caller controls (§5) gets the new owner too. Nothing moves. Items that can't be given, because they belong to someone else or are bound, keep their owner and are listed in the response.
- **Giving everything inside, but not the container:** a `bulk-assign` form taking `from_container_entity_id`, `owner_character_id`, and `recursive`, the shape bulk-move already has ([ADR 0065](../adr/0065-bulk-item-instance-container-move.md)). Outcomes are reported per item, never all-or-nothing ([ADR 0044](../adr/0044-loot-assignment-split-merge-bulk-assign.md)).
- **`dry_run: true`** on both reports what would happen without writing it, as a repository copy's dry run does ([ADR 0119](../adr/0119-copying-a-repository-into-a-tenant.md)). Both apps ask from it: "Also give what's inside? 5 items; 2 are Pia's and stay hers."
- **Handing a container over** ([ADR 0115](../adr/0115-hand-over-on-give-and-stacks-leave-containers-into-their-owner.md)) moves its contents with it physically, so §7 and §8 check them.

### 10. Deleting a container keeps its contents

Before a container item is deleted, its contents move to where it was: into its own container, or into its owner if it had none, keeping their counts. A single item it held that has neither stays uncontained, as before. This is a move for §8's purposes, but it's never refused for capacity: what was inside was already being carried.

### 11. loot-bot, in every slice that touches it

- `/inventory` reads held-by, with Equipped, owner marks, and bound marks.
- `/give` of a container asks about its contents, with the one-click confirmation pattern [ADR 0088](../adr/0088-loot-bot-give-confirmation-and-last-used-character.md) set.
- Giving everything in a container is available.
- Refusals show the API's own message.
- A GM gets a "Move anyway" button on a refused move.

Each slice's ADR settles the exact commands.

## Slices

Each is a tested vertical slice with its own ADR and tracking issue. They are built in this order.

1. **Held-by** (§1–3): the listing, the Equipped column, owner marks; inventory-web board and loot-bot `/inventory`.
2. **Groups and the permission split** (§4–5).
3. **Giving with contents** (§9), web and bot.
4. **`sum` formulas** (§6).
5. **`contents` formulas** (§6).
6. **Capacity** (§7), the move checks and GM override they introduce, and keeping a deleted container's contents (§10).
7. **Binding** (§8), lifting a binding, and removing the named fields.

Slices 1–3 don't depend on 4–7. A reference page, `docs/reference/well-known-stats.md`, collects every name the API reads (`is_container`, `weight`, `size`, `carry_capacity`, `containment_capacity`, `max_item_size`, `binding`) and the weight recipe, growing with slices 5 to 7.

## Not in scope

- **Stored, permanent binding** ("soulbound to Brisk even after the GM takes it"). The maintainer chose derived binding with an explicit lift.
- **Equipment slots**: one armour, two rings, a helmet. Equipped is a place, not a set of slots.
- **Non-additive rules**, like armour that sets a base AC with a capped dexterity bonus. That would need `max`/`min`/`choose` kinds, a later RFC 0016-style decision.
- **Aggregation over anything but containment**, like a party's total hit points over group members.
- **Weight or capacity for beings moved around** (a character climbing into a cart). Moves of beings aren't item-instance writes.
- **`apps/account-hub`.** None of this is in its scope.

## Consequences

- A being's board shows what it actually has, including what it carries for others and what's held elsewhere, and Equipped is always there to drop onto.
- The API now enforces game rules on moves and gives. They're opt-in per tenant, through well-known stats, and a GM can always override them, knowingly.
- Players lose one power: giving away something they merely carry. It becomes an owner's or GM's act.
- Reading a being's stats can now cost a walk of its containment subtree. That cost falls on formulas that ask for it, not on every read.
- Clients stop inferring: `bound`, `owner`, Equipped, and "what would this give" all come from the API, so loot-bot and inventory-web can't disagree about them.
- Removing `is_magical`/`is_cursed` is a breaking API change, taken once, with no client depending on it.
