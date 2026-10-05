# 0189 - inventory-web: unpacking a pack

Status: accepted, decided with the maintainer on 2026-10-06.

## Context

A pack is a catalog item whose public description lists what it holds ([ADR 0145](0145-pack-contents-in-the-description.md)), and the API can hand the list out as real instances ([ADR 0149](0149-giving-a-pack-from-the-api.md), `POST .../item-instances/from-pack`). Only the CLI calls that. Every screen that makes an instance, [the board's "Add an item"](0187-inventory-web-adding-an-item-to-a-board.md), `/items`' instantiate form, loot-bot's `/award`, makes the pack as one plain item with nothing in it, which is what [ADR 0186](0186-player-self-service-enforcement.md) did not change. So there are pack instances already, and more will come.

## Decision

An **Unpack…** action in the detail dialog of a pack *instance* on a board, which is also where a GM looks into any being's inventory. It acts on what exists, so it works however the pack got there.

### What it does

Asked first, then two calls the API already has, in this order:

1. **A dry run** of `from-pack` for the instance's prototype and owner, which is the question: "Unpacking *Explorer's pack* makes Backpack (Rations ×5, Torch ×2) and Rope ×2, and the pack goes. This can't be undone." Its refusal is shown as it is: not a pack, a private item inside, over capacity, self-service switched off.
2. **`from-pack`** for real, then **`DELETE`** of the instance. Contents first, so a failure of the second can only leave a pack *and* its contents, never lose the pack, and then says so: "The contents were added, but the pack itself couldn't be removed: …".

No API change. It is not atomic, which the dry run makes rare and the order makes harmless.

### What it follows from the API, and the limits that come with it

- **Standing.** Whatever `from-pack` and `DELETE` allow. A GM can. A player can when self-service is on for them and the pack and everything in it are public ([ADR 0186](0186-player-self-service-enforcement.md)); a pack a GM gave them with private things inside is refused, in the API's words.
- **Where it lands.** A being's top-level things are Equipped, a group's are owned and in no container, wherever the pack was. Capacity is measured with the pack still there, so a pack in a nearly full pair of hands can be refused until something is set down.
- **Gone with it:** the pack instance's own notes and information. No Undo: the page's banner reverses moves, and a pack has nothing to go back to.

### Which instances offer it

- A **single** instance (not a stack, which would go whole), **owned** (there is no owner to make the contents for otherwise), in a column the board lets you move from (not another being's read-only one). A disabled button says why.
- **Looks like a pack**: one of its descriptions, its own or its prototype's, holds a line of ADR 0145's list, `- 5 x [Label](slug)`. It is a guess to decide whether to offer the button, never to decide anything: the dry run is what knows, and a false positive is a clear "not a pack".

## Not in scope

- An atomic `unpack` route, which would also let the contents land where the pack was. Worth building if the above proves awkward; nothing here prevents it.
- Packs offered at the moment of adding ("add the contents instead"), and an `is_pack` field on items.
- Unpacking a stack, or from the standalone item page, which has no board.

## Consequences

- Packs are usable from a screen for the first time, by a GM or a player, with no change to the API.
- The cost of not changing it is the three limits above, each shown to the person, none hidden.
