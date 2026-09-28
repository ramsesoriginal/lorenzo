# 0129 - Binding: things that won't leave their owner, and a GM lifting it

Status: accepted

## Context

[RFC 0030](../rfcs/0030-carrying-holding-binding-and-capacity.md) §8 decided that items can bind to their owner: on pickup, on equip, or on being owned. It also decided that binding is derived from where an item is and who owns it, never stored, and that a GM can move a bound item anyway or lift its binding for good. [ADR 0128](0128-capacity-and-moving-anyway.md) built the checks on every move and the GM's `override` that binding plugs into.

The same section retires `is_magical` and `is_cursed`, the two named boolean columns that `v_item`, `v_item_instance`, and `ItemOut` still hardcode. No client reads them, and `binding: on_equip` is what `is_cursed` was standing in for.

## Decision

### The stat

`binding` is an `enum` stat ([ADR 0103](0103-stat-tags-enum-values-and-mandatory-groups.md)), read by name like the other well-known stats. Like them it's tenant data and nothing is seeded. It's read as resolved, so a prototype's value or a comparison formula counts ([ADR 0104](0104-computed-stats.md)).

Its vocabulary is `on_pickup`, `on_equip`, `on_own`, and `none`. Any other value binds nothing, and so does a `binding` stat that isn't an enum. `none` exists so that one instance can say "not this one" when its prototype binds, since a stored stat can't be empty.

Binding is always to the item's **owner**, and only a **being** binds: a character or another being, never a group ([ADR 0124](0124-groups-own-things-and-moving-is-not-giving.md)).

### When an item is bound

"Carries" is RFC 0030 §1's: everything contained under a being, at any depth. "Equipped" is what's contained directly by the being.

| `binding` | Bound when | Its owner… | It can't leave… |
| --- | --- | --- | --- |
| `on_own` | a being owns it | can't change | what the owner carries, once it's there |
| `on_pickup` | its owner carries it | can't change | what the owner carries; moving between the owner's own containers is fine |
| `on_equip` | its owner has it equipped | can't change | the owner, not even into the owner's own backpack |

An `on_own` item in a chest at home is bound, so it can't change hands. But it isn't carried, so it can be moved until it's picked up.

`ItemInstanceOut` gains **`bound`**: whether the item is bound right now. Every item-instance response carries it: lists, held-by, single reads, and what a write returns.

### What's refused

**Owner changes of a bound item**, of every kind:

- setting or clearing the owner;
- a bulk-assign entry;
- splitting part of a stack off to another owner.

**Moves that take a bound thing out of what binds it**:

- setting or clearing the container;
- bulk moves;
- handing something over ([ADR 0115](0115-hand-over-on-give-and-stacks-leave-containers-into-their-owner.md)).

A move checks the item moved and everything inside it, at any depth. So a backpack holding a ring bound to Brisk can't go into a chest or be handed over to Pia. The refusal names the ring. What's inside is compared before and after the write, in its transaction, the way ADR 0128 measures loads.

**Giving what's inside** ([ADR 0125](0125-giving-a-container-with-its-contents.md)) isn't refused. A bound thing inside is kept, reported with its reason like anything else that's kept, and the rest is given.

**Never checked:**

- merging stacks;
- splitting in place, or into the same owner's hands, since both halves stay where binding holds them;
- renaming;
- creating an instance;
- deleting, since a potion can be drunk;
- keeping a deleted container's contents (ADR 0128), which moves them one level out, still under whatever carried them.

**Stacks bind as a whole.** A split-off part copies the source's own `binding` value, if it has one, so lifting a stack's binding holds for both halves. (A split-off part is otherwise a fresh instance of the same prototypes.)

**Refusal:** `409 item-bound`. It carries the item (id, name), its `binding`, and its owner (id, name). The `detail` says it in words, such as "Ring of Embers is bound to Brisk (binds on equip), so it can't be taken off Brisk." In a bulk result only `detail` survives, as with capacity.

**Cost:** nothing is loaded when the tenant defines no `binding`. Otherwise, a move loads the binding of what it moves and what's inside it, and a read resolves `bound` from the stats it already loads, plus one containment walk for `on_pickup` items and one lookup of which owners are beings.

### Moving anyway, and lifting a binding

**`override: true`** now skips binding as well as capacity, for the item the write names. It's accepted where ADR 0128 put it. `DELETE .../owner` and `DELETE .../container` now take it too, as `?override=true`, since binding can refuse both. A GM splitting a bound stack off to someone else uses a bulk-assign entry, which takes `override`.

What's given along with a container is still given one thing at a time: a bound thing inside is kept, even with `override`.

**`lift_binding: true`** sets the item's own `binding` to `none` before the write's checks. So the item won't bind again, and the write isn't refused for binding. Capacity still applies unless `override` is sent too. It's accepted wherever `override` is, except `POST .../item-instances`, since a new instance has nothing to lift. It's refused with:

- `422 binding-not-liftable` when the tenant's `binding` has no `none` value, or when the item holds its own formula for `binding` (ADR 0104: a value or a formula, not both);
- nothing at all when the tenant defines no `binding`: it's a no-op.

**Who may:** only the item's GM may send either flag, as ADR 0128 set for `override`. Anyone else gets `403`. That problem type is renamed from `capacity-override-forbidden` to **`override-forbidden`**, since it now covers binding and lifting too. It shipped one slice ago and both clients change with it.

The activity log entry says "overridden" or "binding lifted" ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md)).

### `is_magical` and `is_cursed` go

They leave `v_item`, `v_item_instance`, `ItemOut`, and `ItemInstanceOut`. That's a breaking change to the API contract, listed in `openapi-breaking-accepted.txt`. No client reads them.

There's no data migration. A tenant's own `is_magical` and `is_cursed` stat definitions stay theirs, still shown in `tags` like any other tag. A tenant that wants the RFC's names renames `is_magical` to `is_special` and moves `is_cursed` to `binding: on_equip` itself. Renaming by migration would show up as a change in every tenant that copied a repository ([ADR 0121](0121-repository-updates-and-re-sync.md)).

### inventory-web

- A bound item shows a **Bound** mark on its board card and its detail.
- **Give…** is disabled for a bound item, unless the viewer is a GM.
- A GM whose move or give is refused, for capacity or binding, is asked "…Move anyway?" or "…Give anyway?". For binding, a yes is followed by "Lift its binding too, so it won't bind again?", and the write is sent again with `override`, plus `lift_binding` on a second yes. This covers the board's "Move to…", taking something out, dragging one card, and giving all or part of a stack, and the item page's reassign and unassign.
- Dragging several cards asks once for all the refused ones, with `override` only.
- Anyone else sees the API's message.

### loot-bot

- **`/inventory` and `/inspect`** mark a bound item "(bound)".
- **`/move`**: a GM's "Move anyway" button (ADR 0128) is offered for binding too. For binding, a second button, "Move and lift binding", sends `lift_binding` as well. Both keep their intent in the `customId` ([ADR 0088](0088-loot-bot-give-confirmation-and-last-used-character.md)'s pattern).
- **`/give`, `/give-bulk`, `/give-contents`, `/reassign`, `/drop`'s take and apply-claims, and `/undo`** show the API's message for a refusal.

### Well-known stats

`docs/reference/well-known-stats.md` lists `binding` and its rules.

## Not in scope

- **Stored, permanent binding** (RFC 0030's own exclusion).
- **A GM "anyway" in loot-bot beyond `/move`.** A GM gives a bound item away on inventory-web, or lifts its binding with `/move`'s button first.
- **Who may set stats.** Setting `binding` directly is a stat write, open to whoever may edit the item's stats ([ADR 0037](0037-effective-stat-resolution.md)'s tier), as `weight` is. Whether players should edit the stats the API enforces is a separate question.

## Consequences

- Binding is enforced where a tenant defines it, derived from where things are and who owns them, so nothing has to be kept in sync.
- A give or a move can now fail with `409 item-bound`, and only a GM can push past it or lift it. Clients show the API's message and mark what's bound.
- **Contract.** `bound`, `lift_binding`, the DELETEs' `?override`, `item-bound`, and `binding-not-liftable` are additions. Removing `is_magical`/`is_cursed` is a break, and renaming `capacity-override-forbidden` changes a response a client may read. Both are taken once, here.
