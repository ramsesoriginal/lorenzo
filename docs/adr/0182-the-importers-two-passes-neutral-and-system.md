# 0182 - The importer's two passes: neutral and system

Status: proposed (a skeleton that reserves the number; the decision is written once the importer has been read, in this same pull request)

The third slice of [RFC 0033](../rfcs/0033-item-repositories-common-equipment-rules-and-bridge.md) (its section 6), tracked in [#432](https://github.com/ramsesoriginal/lorenzo/issues/432). It builds on the seed's four layers ([ADR 0181](0181-the-seeds-four-layers-and-a-system-root.md)) and on attachments ([ADR 0172](0172-attachments-a-parent-a-bridge-adds-to-a-copy-travels-with-it.md)), and amends [ADR 0144](0144-lorenzo-import-mapping-identity-plan-apply.md) (the import's mapping, identity, plan and apply).

## Context

An MPMB sheet is D&D data, and `lorenzo apply` writes all of it into one tenant today: each item with its neutral facts (a name, a weight, its forms) and its D&D ones (a price, dice, proficiency, properties) together. RFC 0033 wants them in two repositories, the common equipment (A1) and the bridge that joins it to D&D (C), so a table can take the equipment alone and add D&D to the same items later.

## Decision

To be written. The questions it answers, from the issue:

- What the importer reads that is true anywhere, and what is D&D's.
- Which `part` each row of the built-in map has, and how a user's map says it.
- What `lorenzo apply --part neutral|system` does in each pass, how a second run of either finds what the first made, and how packs, slugs (`basic-`, and a D&D namespace for the prototypes) and `--public-catalog` work.
- What `plan`, `apply --dry-run` and the report say about the part.
