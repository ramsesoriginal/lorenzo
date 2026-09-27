# 0128 - Capacity: what a container or a being can take, and a GM's "Move anyway"

Status: accepted

## Context

[RFC 0030](../rfcs/0030-carrying-holding-binding-and-capacity.md) §7 decided that the API refuses a move that overloads a container or a being, and §8 that a GM can move anyway, knowingly. [ADR 0126](0126-sum-formulas.md) and [ADR 0127](0127-contents-formulas.md) made weight add up. §10 found a bug in the same area: deleting a container cascades its contents' containment rows away, so they silently leave every container and a stack among them loses its count.

## Decision

### Stats the API reads by name

Like `is_container` ([ADR 0047](0047-item-catalog-search-and-container-convention.md)), these are tenant data, nothing is seeded, and a rule applies only where its stats are defined. Each is read as resolved, formulas included ([ADR 0104](0104-computed-stats.md)):

| Stat | On | Rule |
| --- | --- | --- |
| `carry_capacity` | a container or a being | `Σ weight × quantity` of what's directly inside may not go over it |
| `containment_capacity` | a container | `Σ size × quantity` of what's directly inside may not go over it |
| `max_item_size` | a container | nothing whose `size` is over it goes in |

Something inside without a `weight` or `size` counts as 0, as in a `contents` formula.

### When it's checked

On every write that puts something somewhere:

- setting its container;
- bulk moves;
- handing it over to its new owner ([ADR 0115](0115-hand-over-on-give-and-stacks-leave-containers-into-their-owner.md)), including a stack split off to one and a container given with its contents ([ADR 0125](0125-giving-a-container-with-its-contents.md));
- creating it inside a container.

Taking something out of every container, merging stacks, and splitting a stack in place don't put anything anywhere new, so they're never checked.

### What's checked

The **target** is where it goes, and its **chain** is the target and every container above it, by containment, to the containment walk's depth cap. The API measures the chain's loads before the write, applies it inside the transaction, and measures again:

- **`carry_capacity`**, on every container in the chain: a stone put into a backpack also loads the character carrying it.
- **`containment_capacity` and `max_item_size`**, on the target only.

A write is refused only when it **makes a load grow past its limit**. That settles the cases RFC 0030 named:

- **Taking something out is never refused.** Its load goes down.
- **A container already over capacity isn't emptied.** A character whose strength was drained keeps what they carry, but nothing that adds to their load goes in until they're back under.
- **Moving within what a being carries doesn't change its load.** Taking a rope out of your backpack and into your hands leaves your carried weight the same.
- **A Bag of Holding stops the climb.** Its own weight is fixed, so what goes into it doesn't load whoever carries it.

**Races.** The chain's entity rows are locked (`SELECT … FOR UPDATE`, in id order) before the first measurement, so two concurrent moves into one bag can't both pass.

**Cost.** Nothing is measured when the tenant defines none of the three capacity stats. Otherwise a check loads the chain's contents and stats twice, with ADR 0127's loader.

### Refusal

`409 capacity-exceeded`, naming the container, the stat, the limit, and what the load would have been. The `detail` says it in words, such as "The Backpack can carry 20, and this would make it 23." In a bulk result only `detail` survives, so it carries everything a reader needs.

### Moving anyway

`override: true` skips the check. It's accepted on:

- `PUT .../container`;
- `PUT .../owner`;
- bulk-move, for the whole request;
- a bulk-assign entry;
- `POST .../item-instances`.

Only the item's GM may send it: a GM of a campaign its owner plays in, or, for an item nobody owns, any GM in the tenant. That's the GM half of [ADR 0124](0124-groups-own-things-and-moving-is-not-giving.md)'s rule. Anyone else gets `403 capacity-override-forbidden`, whether or not the move needed it.

The activity log entry for the move says it was overridden ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md)).

Slice 7 adds binding to what `override` skips.

### Deleting a container keeps its contents

Before a container item is deleted, what's directly inside it moves to where the container was:

- into the container's own container;
- or into its owner, if it had no container;
- or out of every container, if it had neither. A stack can't go there without losing its count (ADR 0115), so the delete is refused with `409 stack-needs-container` naming the stack, until it's moved out first.

Their counts are kept. This never checks capacity: what was inside was already being carried. Each thing moved out is recorded as a move in the change feed ([ADR 0099](0099-player-facing-change-feed.md)).

### inventory-web

A GM whose move is refused for capacity is asked "…Move anyway?", and a yes sends it again with `override`. This covers "Move to…", taking something out, and drag and drop, including several cards at once, where it asks once for all the refused ones.

Anyone else sees the API's message. So does a GM whose give with "Hand it over" is refused; they can give without handing over, then move it.

### loot-bot

- **`/move`** shows the API's message when a move is refused. A GM also gets a "Move anyway" button, whose intent lives in its `customId` ([ADR 0088](0088-loot-bot-give-confirmation-and-last-used-character.md)'s pattern).
- **`/move-bulk`, `/container-new`, and `/award`** show the API's message for a refusal.

### Well-known stats

`docs/reference/well-known-stats.md` lists `weight`, `size`, `carry_capacity`, `containment_capacity`, and `max_item_size` with these rules.

## Not in scope

- **Binding**, slice 7.
- **Showing loads and limits on the board**, such as "12 / 20" on a column. A client can already read the stats.
- **Capacity for beings moved around** (RFC 0030's own exclusion): moving a being isn't an item-instance write.

## Consequences

- Carrying limits are enforced where they're defined, with the tenant's own formulas, and nowhere else.
- A move can now fail with `409` where it used to succeed, and only a GM can push past it. Clients show the API's message.
- Deleting a container no longer loses what was inside, or a stack's count.
- **Contract.** `override` is a new optional field, and `capacity-exceeded`, `capacity-override-forbidden`, and the delete's `stack-needs-container` are new responses. Nothing that existed changes shape.
