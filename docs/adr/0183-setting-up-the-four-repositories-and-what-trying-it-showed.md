# 0183 - Setting up the four repositories, and what trying it showed

Status: proposed

The fourth and last slice of [RFC 0033](../rfcs/0033-item-repositories-common-equipment-rules-and-bridge.md) (its sections 7 and 8), tracked in [#433](https://github.com/ramsesoriginal/lorenzo/issues/433). It builds on attachments ([ADR 0172](0172-attachments-a-parent-a-bridge-adds-to-a-copy-travels-with-it.md), [0174](0174-the-cli-shows-attachments.md)), the seed's four layers ([ADR 0181](0181-the-seeds-four-layers-and-a-system-root.md)) and the importer's two passes ([ADR 0182](0182-the-importers-two-passes-neutral-and-system.md)), and it settles what [ADR 0162](0162-the-dnd5e-layer-is-its-own-repository-a-bridge-over-core.md)'s four steps for a correction left open.

## Context

Everything RFC 0033 needs exists, one slice at a time: the API carries an attachment with a copy and with its updates, the seed has a layer for each of the four repositories, and the importer writes the two halves of an item in two passes. What no one has done is the whole of it, in order, as a person would: eighteen commands to build the repositories, then a table that takes the equipment, then D&D. RFC 0033 §8 also leaves one thing untried: whether the bridge has to publish again before a table sees a correction made further down.

## Decision

*(To be written when the trial is done: it is recorded here before this ADR is accepted.)*

- **The setup is run, not only written.** An end-to-end test runs RFC 0033 §7's commands against the real API in the README's order, so the walkthrough can't drift from the CLI.
- **What a correction does at each level, and whether a bridge must publish again,** as the trial shows it.
- **Rebuilding the local tenants.** There is no command that deletes a tenant, so the old `core` and `dnd5e` (version 1 of the seed, both halves of an item together) are left behind, or the local database is emptied.
- **The README** describes the four repositories with the real command names, and says what it doesn't do: one system per tenant until resolution knows about systems ([RFC 0033](../rfcs/0033-item-repositories-common-equipment-rules-and-bridge.md) §9) and no way to take D&D back off a table.

## Not in scope

- **A single setup command**, **a command that takes an attached repository back off a tenant**, **showing on a table's item which repository each part came from** and **system-aware resolution**: RFC 0033 §"Slices" puts them later.
- **Publishing anything, or granting it.** The maintainer's decision of 2026-10-04 stands: nothing is published yet, so nothing is migrated.
