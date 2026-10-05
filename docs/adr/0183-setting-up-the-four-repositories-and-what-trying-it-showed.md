# 0183 - Setting up the four repositories, and what trying it showed

Status: proposed

The fourth and last slice of [RFC 0033](../rfcs/0033-item-repositories-common-equipment-rules-and-bridge.md) (its sections 7 and 8), tracked in [#433](https://github.com/ramsesoriginal/lorenzo/issues/433). It builds on attachments ([ADR 0172](0172-attachments-a-parent-a-bridge-adds-to-a-copy-travels-with-it.md), [0174](0174-the-cli-shows-attachments.md)), the seed's four layers ([ADR 0181](0181-the-seeds-four-layers-and-a-system-root.md)) and the importer's two passes ([ADR 0182](0182-the-importers-two-passes-neutral-and-system.md)), and it settles what [ADR 0162](0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md)'s four steps for a correction left open.

## Context

Everything RFC 0033 needs exists, one slice at a time: the API carries an attachment with a copy and with its updates, the seed has a layer for each of the four repositories, and the importer writes the two halves of an item in two passes. What no one had done is the whole of it in order, as a person would: eighteen commands to build the repositories, a table that takes the equipment, then D&D. RFC 0033 §8 also left one thing untried, whether the bridge has to publish again before a table sees a correction made further down. This slice runs it against the real API, records what it showed, and writes the walkthrough from what ran.

## Decision

### The setup is run, not only written

An end-to-end test, `apps/cli/tests/e2e/test_setup.py`, runs RFC 0033 §7's commands in the README's order (`tenant create`, `seed --layer`, `repo offer`, `apply --part`, `repo publish`) and then the table's two, so the walkthrough can't drift from the CLI. It doesn't replace the files that test each step; it says what the whole leaves: four published repositories, each holding the layers it is built from and no more, the bridge built on the other three, and its attachments.

### A correction is taken from where it was made, and nothing else has to move

Tried on 2026-10-05, with a table that took the equipment and then the bridge:

- **The equipment corrects its Purple sword and publishes once.** The table sees one *changed* row from the equipment (`repo updates <equipment> --tenant <table>`) and takes it with `--apply`. The bridge has not been asked and has nothing to say (`repo updates <bridge> --tenant <table>` exits 0). The table's sword is the same sword, with the new name, and still has the bridge's prototype as a parent. A correction to core or to the rules goes the same way, from the repository it was made in.
- **So the bridge does not have to publish again, or take anything, for a table to see a correction made below it.** The answer to RFC 0033 §8 is no. What `repo updates` shows is the repository's state now against what the tenant copied or last took, not the state at its last publish: an equipment repository that imported more and hadn't published again already showed the new items to a table. Publishing again makes `repo list` say "updated since", which is the announcement; a repository does it when it wants its subscribers to look.
- **ADR 0162's four steps are two for a table:** the repository publishes, and each table takes it from there. The repositories built on it (the bridge, the equipment, the rules) take it too when their authors want their own copies current, and a bridge has to before it writes anything that depends on it: the system pass finds an item in the bridge's *own copy* of the equipment, so equipment that grew is taken by the bridge (`repo updates <equipment> --tenant <bridge> --apply`) before `apply --part system` (otherwise every new item is held, ADR 0182).
- **A bridge that takes a correction keeps what it attached.** Its attachments are the same after as before, and a table that arrives afterwards gets the corrected item with D&D on it: a copy is made from each repository's current state, not through another's copy.

### Equipment that grows reaches a table in either order

The equipment imports more, the bridge takes it and writes its half, and both publish. A table that takes the equipment and then the bridge has the new items with D&D on them. One that takes the bridge first gets the prototypes, and each attachment **waits** (`applicable: false`, "the item it attaches to isn't here"): the command exits 2 and names them, and nothing is lost. Once the equipment's items arrive the next `repo updates <bridge>` lists the same attachments as applicable, and `--apply` attaches them. No `--actions` file is needed; "the equipment first" is the order to prefer, and not one a table can get wrong for good.

### Rebuilding the local tenants

Nothing in the API or the CLI deletes a tenant, so the local `core` and `dnd5e` that version 1 of the seed made (two layers, both halves of an item together) stay as they are. Rebuilding is **from an empty local database** (`docker compose -f infra/docker-compose.yml down -v`, up again, `alembic upgrade head` in `apps/api`) **or under other slugs**. Nothing was published or granted, so nothing is migrated (RFC 0033, decided on 2026-10-04). The README's walkthrough is the procedure and the test is its proof; running it against a person's own stack is theirs.

### The README

The CLI's README gets the walkthrough with the real command names, the three things this ADR settled (where a correction is taken, that equipment grows in either order, what a bridge must do before its pass), and what it doesn't do yet:

- **One system per tenant** until resolution knows about systems (RFC 0033 §9): two systems' prototypes on one item would break ties arbitrarily.
- **No way to take D&D back off a table.** A tenant that wants to undo the bridge detaches the prototype itself.
- **No tenant deletion**, so starting over is the rebuild above.

## Not in scope

- **A single setup command**, **a command that takes an attached repository back off a tenant**, **showing on a table's item which repository each part came from** and **system-aware resolution**: RFC 0033 puts them later.
- **Publishing anything, or granting it.** The maintainer's decision of 2026-10-04 stands: nothing is published yet, so nothing is migrated.
- **Deleting a tenant.** It would make starting over a command; it is a feature of its own.

## Consequences

- **A rename of a flag or a change of order in the setup fails a test**, not a reader.
- **The README's "four steps" for a correction is wrong and is replaced** by the two that a table needs and the one a bridge needs before its pass.
- **A table can take its repositories' updates in any order.** The cost is a second run of `repo updates` for the attachments that waited.
- **`repo updates` doesn't depend on a publish**, so a repository's work in progress is visible to the tenants it is granted to, as it already was. Publishing is how an author says "look now".

## Tests

- **End to end against the real API** (`test_setup.py`): the four repositories after the setup (published, the layers each holds, what the bridge is built on and attaches); a table that takes the equipment alone and then the bridge, with the same sword before and after; a correction made in the equipment and in the rules, taken by a table that holds the bridge too, with the bridge silent and the prototype kept; the bridge taking the correction and keeping its attachments, and a table that arrives afterwards; the equipment growing and reaching two tables, one in each order, with the waiting attachments named and then attached; and that a change is visible before the repository publishes it again and flagged after.
