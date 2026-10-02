# RFC: Giving a pack from the API — instantiate with contents

Status: accepted, decided with the maintainer on 2026-10-02. Built in the two slices in [Slices](#slices), each recorded as its own ADR when it lands. Amends [ADR 0145](../adr/0145-pack-contents-in-the-description.md)'s "handing a pack out", and builds what [RFC 0025](0025-lorenzo-cli-mpmb-item-importer.md) R7 named as waiting: "instantiate with contents" as a designed `apps/api` capability. Tracked under the v1.0 row "pack-give" ([issue #376](https://github.com/ramsesoriginal/lorenzo/issues/376)).

## Context

A pack is a catalog item whose public description holds a strict list of what's in it ([ADR 0145](../adr/0145-pack-contents-in-the-description.md)):

```text
This pack contains:

- 1 x [Backpack](basic-gear-backpack)
  - 5 x [Rations, days of](basic-gear-rations-days-of)
  - 2 x [Torch](basic-gear-torch)
```

`lorenzo pack give` hands one out. It reads that list, then calls `POST .../item-instances` once per line. What's wrong with that, now that the rest of the system has moved on:

- **Nothing is atomic.** A pack of twelve lines is twelve requests. A failure on the ninth (capacity, [ADR 0128](../adr/0128-capacity-and-moving-anyway.md)) leaves a backpack with half its contents, owned by someone.
- **Only the CLI can do it.** ADR 0145 said so on purpose ("any client can do the same from the same text"). loot-bot and the web apps would each have to carry a parser and the same sequence of calls.
- **It misses what a being now is.** ADR 0123 made a being its own Equipped container and ADR 0124 let a group own things. The CLI's `--owner` sets an owner but, without `--into`, puts nothing in the being's hands, and it knows nothing of the difference between a being and a group.
- **R7 said this was the plan.** The list in the description was chosen for v1; the capability itself was deferred "as a designed `apps/api` capability".

Other decided facts this builds on:

- **A stack's count lives on its containment row** ([ADR 0041](../adr/0041-containment-quantity-and-stacking.md), [0140](../adr/0140-a-stack-when-an-item-instance-is-created.md)), so a stack needs a container. A group carries nothing, so a stack can't sit in it.
- **Equipped is containment directly in the being** ([ADR 0123](../adr/0123-held-by-listing-and-the-equipped-column.md), [RFC 0031](0031-equipped-carried-controlled-and-setting-things-down.md) §1).
- **Dry runs do all of it and roll it back** ([ADR 0121](../adr/0121-repository-updates-and-re-sync.md), [0125](../adr/0125-giving-a-container-with-its-contents.md)).
- **Every pack entry is an item.** The importer already makes a plain item for an entry the sheet has no gear entry for ([ADR 0146](../adr/0146-a-richer-item-taxonomy-and-keeping-what-the-sheet-says.md)). Only a `"text"` row in `[pack_items]` still leaves a line without a link.

## Decision

### 1. One route

`POST /tenants/{tenant_id}/item-instances/from-pack`, with a body of `pack_id` (an item), `owner_entity_id`, and `override` (default `false`), and `?dry_run=true`. It sits beside `bulk-assign` and `bulk-move` as another collection-level write, and is to a pack what `POST /item-instances` is to one item.

### 2. The description stays the source

The list in the pack's description is read by the API itself.

- **A Python parser** in `apps/api`, held to the grammar the CLI's `packs.py` already uses: `- N x [Label](slug)`, two spaces per level, at most three levels, everything else ignored. ADR 0110 set the precedent of a second implementation held to shared examples; here both parsers read one fixtures file, so they can't drift.
- **Only the pack's public description is read.** Not whatever a caller happens to be cleared to see: the answer must not depend on who asks, and GM-only prose must not be parsed as a list.
- **A slug resolves to an item of the same tenant**, through `entity_slug`. A pack with no list, a slug that isn't there, or one that names something that isn't a base item is refused with a problem that names what's wrong (`422`).
- **A line without a link refuses the whole call**, naming the lines. Every entry is an item (ADR 0146), so a line like that means a pack that isn't finished.

### 3. The recipe model

The pack item is not instantiated. Its list is the recipe, as ADR 0145 has it.

- **A line with lines under it is a container**, made once per unit: `2 x Backpack` with rations under it is two backpacks, each holding that much.
- **A line with nothing under it is one stack** of its quantity, inside its parent.
- A line goes inside the nearest line above it that is one level up. Its quantity is per unit of what it's inside: `2 x Backpack` over `5 x Rations` is two backpacks of five.

### 4. The owner

`owner_entity_id` is a being (a `Being` row) or a group (a bare entity named by `group_member` rows, found as the group routes find one). Anything else is `422`.

- **A being.** Each top-level thing is owned by it and **contained directly in it**: Equipped. Top-level stacks are stacks in the being.
- **A group.** Each top-level thing is owned by it and in no container, since a group carries nothing ([ADR 0124](../adr/0124-groups-own-things-and-moving-is-not-giving.md)). With no container to hold a count, a top-level stack of *n* is *n* single instances, at most 50 of one line as the CLI guards today.
- **Either way**, what's inside a container is owned by the same owner and contained in that container.

### 5. Authorization

The caller must be allowed to create an instance for that owner: ADR 0032's self-or-managed rule, `_authorize_create_instance` as it is today, once for the whole pack. `override` is a GM's alone, refused up front whether or not the pack would have needed it (`403 override-forbidden`, [ADR 0129](../adr/0129-binding-and-lifting-it.md)). Nothing new.

### 6. All or nothing, with capacity

One transaction. Anything that fails, fails the whole call and nothing exists.

- **Capacity is checked as creation inside something is checked** (ADR 0128): for a being, the being and everything it's inside are measured before and after for the top-level things; each new container is measured for what goes into it. A group's top level has no target, so only the new containers are.
- **A pack that would overfill something is refused** with `409 capacity-exceeded`, naming the container.
- **`override`** (GM only) skips capacity, as for any create. Binding never refuses a create, so it has nothing to skip.
- The being's chain is locked by its capacity check, as for any create, which keeps two packs into one being in order.
- **A limit on the total instances one call creates**, set in the ADR, so a pack list is bounded whatever it holds.

### 7. Dry run

`?dry_run=true` does all of it, checks included, rolls it back, and answers exactly as a real call would, with `dry_run: true`. The ids in it name nothing.

### 8. The answer

`201` for a real call, `200` for a dry run: the pack, the owner, and the created instances as a tree (each an `ItemInstanceOut`, with what's inside it under `children`). Nothing is "skipped": a line either becomes something or refuses the call.

### 9. What's recorded

- **Activity log** ([ADR 0084](../adr/0084-activity-log-coverage-and-member-removal-notice.md)): one `item_instance.created` per instance, as `POST /item-instances` writes, with the pack's id in `detail`. Bulk writes elsewhere record one summary entry; here the count of instances is bounded and each is a thing that now exists, which is what the log is for.
- **Change feed** ([ADR 0099](../adr/0099-player-facing-change-feed.md)): one call to `record_change` for everything created, so each holder is told what they received.

### 10. The CLI

`lorenzo pack give` becomes a thin client of §1.

- **`--owner` is required**, a being or a group, by id or slug. A pack with no one to hold it isn't a thing the API creates.
- **`--into` goes.** The API puts things in the being; there is nowhere else to put them. This is a breaking change to a pre-1.0 command and is released as one.
- **`--dry-run`** becomes `?dry_run=true`. Its output is the API's answer, rendered.
- **The importer makes sure every line links.** The built-in map already answers its seven gaps with `"item"`; what's left is the `"text"` disposition a map of your own can still choose. It stops being valid in `[pack_items]`, with an error that says to use `"item"`, and the importer no longer has a "no item" outcome for a pack entry. What it writes is therefore always a list in which every line links. A pack it wrote earlier with a line that doesn't is not rewritten (a description is written once, [ADR 0121](../adr/0121-repository-updates-and-re-sync.md)): the API's refusal names the lines, and editing the description fixes it.
- **The CLI's own give code goes**: `importer/give.py`, its container/stack orchestration, and its `MAX_LOOSE` guard. The list *writer* in `packs.py` stays, and so does its parser, as the CLI's half of §2's shared fixtures: what the importer writes is then proven to parse the way the API will read it.

## Slices

Each is a tested vertical slice with its own ADR and tracking issue. They are built in this order.

1. **The API** (§1–9): the parser and its fixtures, the route, the owner rules, capacity, dry run, activity and change feed. Regenerates the schema in `packages/api-client` and in `apps/cli`.
2. **The CLI** (§10): `pack give` on the route, the importer's `"text"` retirement, the end-to-end test against the real API.

## Not in scope

- **A pack as real data** — a table of pack entries, or child items under the pack. Both were weighed and set aside (below). The route's contract doesn't depend on where the list lives, so replacing the source later changes nothing for a caller.
- **loot-bot's `/give-pack` and a button in the web apps.** Both become possible; neither is part of this.
- **Packs inside packs.** A line that links to an item that is itself a pack is one instance of that item, not expanded.
- **Merging into stacks the owner already holds.** Creating doesn't merge ([RFC 0031](0031-equipped-carried-controlled-and-setting-things-down.md) §6); a caller who wants it asks for it afterwards.
- **Naming the instances after their line's label.** An instance takes its item's name, as any create does.
- **Giving across tenants.** The pack, its items, and the owner are one tenant's.

## Alternatives considered

- **A table of pack entries.** The clean model: pack, item, quantity, nesting. It is a new tenant table with row-level security, same-tenant keys, a place in `repository_access`, and copy and re-sync support ([ADR 0119](../adr/0119-copying-a-repository-into-a-tenant.md), [0121](../adr/0121-repository-updates-and-re-sync.md)), and the importer changes with it. Too large for what's asked, and nothing in the route forces it.
- **A pack that is a container of real child items.** ADR 0145 already rejected it: a child has one parent, so the same Rations can't be in two packs. It would need a template child per pack, inheriting from the item, and whether a repository copy carries item-to-item containment would need checking first.
- **Skipping lines that don't link.** The CLI does. With all-or-nothing, a half-given pack is the very thing this removes.

## Consequences

- A pack is handed out in one transaction by any client, and a failure leaves nothing behind.
- A pack's meaning stays a convention in prose, as ADR 0145 accepted: a careless edit can stop a line parsing, and now the API refuses the pack rather than a client skipping the line.
- There are two parsers, in two languages, held to one set of examples.
- ADR 0145's "needs no `apps/api` capability" no longer holds for handing out, and that section is marked superseded when ADR for slice 1 lands. How a pack is written and resolved is unchanged.
- `lorenzo pack give` loses `--into` and gains a required `--owner`.
- A pack imported with a map of its own that used `"text"`, or written by hand with a plain line, refuses until its description is edited, with the lines named. The built-in map has no such line, so the SRD's packs are unaffected.
