# RFC: What a board shows — equipped, carried, controlled, and setting things down

Status: accepted, decided with the maintainer on 2026-09-28. Built in the four slices in [Slices](#slices), each recorded as its own ADR when it lands. It amends [ADR 0123](../adr/0123-held-by-listing-and-the-equipped-column.md)'s board, and parts of [ADR 0115](../adr/0115-hand-over-on-give-and-stacks-leave-containers-into-their-owner.md) and [ADR 0128](../adr/0128-capacity-and-moving-anyway.md).

## Context

Testing inventory-web's board after [RFC 0030](0030-carrying-holding-binding-and-capacity.md) turned up two things that looked wrong:

- A character owns a sling bag, a belt pouch, and a treasure chest, and carries only the first two. All three show under **Equipped**.
- A new, empty backpack shows under Equipped, marked as a container, but gets no column, so nothing can be dropped into it.

Both are what ADR 0123 decided:

- **"Owned, in no container" counts as carried.** ADR 0123 made it explicit: "an owned item in no container is with its owner". `held-by` puts every held item without a containment row into the holder's own group, which the board labels Equipped, and `entity_access.surroundings` walks through an item's owner the same way. So a being can't own something without carrying it, unless it's inside something outside the being.
- **Only occupied containers get a group.** "A container with nothing visible inside gets no group of its own." RFC 0030 §3 had said "each carried container gets a column".

Other decided facts this runs into:

- **Binding and capacity already read carrying by containment alone.** Both walk `containment_paths`, not `surroundings` ([ADR 0128](../adr/0128-capacity-and-moving-anyway.md), [ADR 0129](../adr/0129-binding-and-lifting-it.md)). So today an owned `on_equip` ring in no container shows under Equipped, but isn't bound and doesn't weigh on its owner.
- **A stack's count lives on its containment row** ([ADR 0041](../adr/0041-containment-quantity-and-stacking.md)). An item with no row has no count, which is why `DELETE .../container` refuses a stack with `409 StackNeedsContainerError` (ADR 0115).
- **Merging is explicit only.** [ADR 0044](../adr/0044-loot-assignment-split-merge-bulk-assign.md) left out "automatic merging of stacks that land in the same container by coincidence". A split makes a fresh instance of the same prototype; it doesn't copy the source's own stats, information, or attribution.
- **`held-by` for a character doesn't include what its groups own.** [ADR 0124](../adr/0124-groups-own-things-and-moving-is-not-giving.md) widened a player's reach through their characters' groups, but left `reachable_entity_ids`, and so `held-by`, as it was.
- **The API allows more than a board needs to show.** Anyone who reaches an item may move it (ADR 0124). On a board, a group with many containers and items would bury a character's own things under ones that aren't theirs to care about.
- **Items are shown by their owner's reach** ([ADR 0040](../adr/0040-item-instance-read-visibility.md)). Nothing yet lets a character carry something without knowing it's there.

The project is in early pre-alpha testing, so there's no existing data to migrate.

## Decision

### 1. Five words, for a being

Containment alone says where an item is. Ownership never does.

- **Equipped**: everything contained directly by the being, whoever owns it.
- **Carried**: everything Equipped, and everything inside an Equipped item, at any depth.
- **Personal**: everything the being owns itself.
- **Owned**: everything the being owns, and everything owned by a group the being is a member of.
- **Controlled**: what the being's board shows (§2).

An owned item in no container is simply not carried. It lies wherever it was set down (§5).

For a **group**, Personal and Owned are both what the group owns, and nothing is Equipped or Carried: a group carries nothing (ADR 0124).

### 2. Controlled

Here "a container" is always an item instance, never the being itself. "Its contents" are what it contains directly; a container inside another is judged on its own.

Controlled is:

- everything **Carried**, except the contents of a container that isn't Owned and holds, at any depth, nothing Personal;
- everything **Owned**;
- the contents of every **Owned** container, except those of a container that isn't Personal and holds, at any depth, nothing Owned.

Carrying something, you can look straight inside it. Once it's on the floor or in the guild house, what matters is your own things and what's with them. Putting something of yours into a container you control lets you see the rest of what's in it: a convenience, not a permission. The API still lets a caller move whatever they reach (ADR 0124); the board just doesn't show all of it.

For Pia:

- She carries Brisk's backpack. While nothing of hers is in it, its column says its contents aren't shown. Once she puts a coin in, she sees everything in it.
- Her chest stands in the guild house with Brisk's pouch inside. The pouch is shown; what's in the pouch isn't.
- The Company's chest is on the floor, holding only Brisk's things. The chest is shown, since the Company's things are Owned; its contents aren't. If it also holds a rope the Company owns, all of it is.

### 3. The controlled-by listing

`GET /tenants/{tenant_id}/item-instances/controlled-by/{entity_id}`, for a being or a group, lists its board as columns, in board order:

1. **Equipped**, always, for a being. A group has none.
2. **Not carried**, always: what's Controlled and in no container, which is always something Owned.
3. **Carried containers**: every Controlled container that's Carried.
4. **Other controlled containers**: every Controlled container that isn't.
5. **Read-only columns**: every container that isn't Controlled but directly holds something Owned, listing only what's Owned. Beings count here: a sword of Pia's that Brisk has equipped is in a "Brisk has these" column.

A container gets a column when it's a Controlled item instance that is a container (`is_container`, [ADR 0047](../adr/0047-item-catalog-search-and-container-convention.md)) or has anything in it, so an empty backpack gets one. Every Controlled item appears in the column of where it is: its container's, Equipped, or Not carried.

Each column gives:

- its kind (`equipped`, `not_carried`, `container`, or `read_only`), its container (none for Not carried), and `container_kind` as `held-by` has it;
- where it is: `path`, the containers around it nearest first, by containment alone, and `carried`;
- `contents_hidden`: whether its container directly holds anything the column doesn't list, so a client can say "Contents not shown" instead of "This container is empty".

Items keep `ItemInstanceOut`'s shape, plus `visible_to_characters` (§4). `owners` names every owner once, as in `held-by`. Access is `held-by`'s: the caller must reach the being or group, or gets `404`. Within the listing, Controlled decides what's there, not the owner's reach (ADR 0040). A player sees what their character controls, and what the character doesn't know about is §4's to hide.

### 4. `visible_to_characters`

Each item in the listing carries `visible_to_characters`: whether the being or group the listing is for knows it's there. It's always `true` for now. A later decision builds it on knowledge ([ADR 0028](../adr/0028-knowledge-and-group-membership.md)).

- A caller who isn't a GM for it never gets an item with `false`. The API leaves the item out, since anything sent to a browser can be read there, and doesn't count it towards `contents_hidden` either.
- A GM gets every item, with the flag as it is.

### 5. Setting things down

Setting something down takes it out of every container: `DELETE .../item-instances/{id}/container`, as for a single item today. It stays whose it is, and lies wherever it was put.

- **A stack becomes single items.** An item with no containment row has no count, so a stack of *n* set down becomes *n* single instances. The API keeps refusing it with `409 StackNeedsContainerError` unless the request says `?split=true`, so no existing client splits a stack by surprise. The board asks first ("Setting down Arrow ×20 leaves 20 separate arrows.") and retries with it, the way it asks before moving anyway (ADR 0128).
- **The pieces are copies.** Unlike a split, every piece copies the stack's own stats, so a `+1` or a lifted binding survives and the pieces stay identical to each other (§6). The stack's own information, notes, and slug stay with the one instance that keeps its id.
- **Binding applies** as to any move (ADR 0129): a bound item can't be set down, unless a GM moves it anyway. **Capacity never refuses it**: taking something out never is (RFC 0030 §7).
- **Setting down someone else's item** is allowed, as moving it is, and it's how you stop being responsible for it. Once it's out of everything you carry and control, it leaves your board and shows on its owner's Not carried. An unowned thing set down shows only on the GM's board of unowned things.
- **Undo.** Setting down a single item gets the board's usual Undo. Setting down a stack doesn't: undoing it would mean merging *n* instances back.

### 6. Merging what's identical

A move may say `merge_identical: true`, on `PUT .../container` and on bulk moves. After the move, anything moved into a container that already directly holds an identical instance merges into it, as `POST .../merge` does, and moved items identical to each other merge too. The response names the instance each one ended up in.

Two instances are **identical** when they have the same prototype(s), the same owner, and the same own stats, and neither has information, notes, or a slug of its own.

This revisits ADR 0044's "explicit only" just far enough: merging is still something a caller asks for, per request. inventory-web asks on every move it makes, so twenty arrows set down and picked up again become one stack again. After a move that merged, the board offers no Undo. loot-bot and other clients are unaffected until they ask.

### 7. Deleting a container that's in no container

ADR 0128 moves a deleted container's contents to where it was: into its own container, "or into its owner, if it had no container". The second half becomes: its contents are set down (§5). A stack among them needs the same `?split=true` on the delete, and inventory-web says so before deleting.

### 8. inventory-web's board

The board reads `controlled-by`: for a character, for a group, and for a GM browsing any being. The board of unowned things keeps reading `GET .../unowned`.

- **One row.** Every column sits in one horizontally scrolling row, in §3's order. Equipped and Not carried carry the brand's `glow-canonical`, the maintainer's choice, marking the two places every board has.
- **Dropping.** Onto Equipped puts an item into the being; onto Not carried sets it down; onto a container's column puts it inside. A read-only column takes no drops, and its cards open without Move to…, Equip, or Set down.
- **The item dialog.** "Remove from container" becomes two actions, **Equip** (not on a group's board) and **Set down**. Move to… offers every Controlled container, which now all have a column.
- **Columns** say where they are: "In the Backpack", "In the Guild house", "Brisk has these", "Not carried". They say "Contents not shown" when `contents_hidden`.
- **Owner marks and bound marks** stay as they are.
- **A stack set down on the board of unowned things** splits the same way, after the same question.

### 9. What stays

- **`held-by`** keeps ADR 0123's reading, owner equivalence included, and loot-bot's `/inventory` and `/inspect` keep reading it. Until the bot moves to `controlled-by`, something set down still shows there under Equipped.
- **Permissions**: who may move and who may give stays ADR 0124's.
- **Hand-over** (ADR 0115) still puts a gift into the recipient's hands, which is Equipped.
- **Bulk moves** still need a container. The board sets a selection down one item at a time.

## Slices

Each is a tested vertical slice with its own ADR and tracking issue. They are built in this order.

1. **The controlled-by listing** (§1–4): the five words, the columns, `contents_hidden`, `visible_to_characters`. API.
2. **The board on it** (§8, except setting down): one row, read-only columns, "Contents not shown", Equipped and Not carried always there.
3. **Setting things down** (§5, §7): `?split=true` and its copied pieces, Equip and Set down, dropping on Not carried, deleting a container that's in no container.
4. **Merging what's identical** (§6), with the board asking for it on every move.

## Not in scope

- **loot-bot on `controlled-by`**, and retiring `held-by`'s owner equivalence with it. A later decision.
- **Who knows what's in their pack.** `visible_to_characters` stays `true` until knowledge backs it.
- **Places.** Where something was set down isn't recorded. It's just not carried.
- **Setting down a selection in one request.** Bulk moves stay container-only.
- **Merging outside a move.** Creating, giving, and handing over don't merge.
- **Narrowing permissions.** The board shows less than the API allows, deliberately; the API isn't narrowed to match.

## Consequences

- The board, binding, and capacity agree on what's carried: containment, nothing else.
- Every board has two fixed places, Equipped and Not carried, and every container it shows is somewhere to drop, empty or not.
- A board shows what its being has a stake in, not everything its groups own.
- Setting down a large stack makes as many entities as it had units, until they're picked up and merged again.
- A player sees what their character controls even where the owner's reach would have hidden it, until `visible_to_characters` is real.
- loot-bot and inventory-web disagree about set-down things until the bot moves.
