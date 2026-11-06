# 0422 - Lorenzo Beings, redesigned

Status: accepted, decided with the maintainer on 2026-11-05. Part of [RFC 0050](../rfcs/0050-the-web-interface.md). The design is [docs/design/web/beings](../design/web/beings/README.md), BN1 to BN10. Revises [ADR 0282](0282-beings-sheet-shell-modes-and-sections.md), [0283](0283-beings-sheet-play-stats-and-undo.md) and [0284](0284-beings-sheet-datasheet.md) where they differ; [docs/design/beings](../design/beings/README.md) is not changed.

## Context

The being sheet was built from an earlier design with three modes (Read, Play, Edit), two layouts and a sticky bar. At a table the split between Read and Play was not obvious, and Edit was a mode that turned the page into a form.

## Decision

- **The list has rows, cards and side by side** (BN1, BN4), one switch, remembered, with the same search, filters and Mine; side by side reads many beings at once and has its own Read and Play for a skirmish.
- **Read and Play are modes; Edit is in place** (BN2). Reading is the page. A section a person may change has its edit control on the section and saves as it goes, with no page-level Save.
- **The split is plain** (BN7): the mode switch and the pinned numbers are one band that stays in view, with a line saying what each mode is for; Play tints the bar, shows a stepper on every number that can be set, reorders the page (Stats, Inventory, Notes, About, with About closed) and lets a note be added and a condition switched; Read and in-place editing are for understanding and editing. The order is visual only.
- **Steppers sit on the numbers** (BN3), with a "Change by" adjuster; each step gives the shell's Undo toast and shows its amount; History is the undo surface, thirty steps, and says who made each step (BN9). A number stays between zero and its limit; a derived number has no stepper and a "why".
- **The datasheet is a layout switch on the page** (BN4) and a third view of the list.
- **The old decisions carry over** except the mode memory (BN5): a player lands in the last mode used on the being they play. **Active conditions show in the band** (BN10).
- **Hand over** asks for a campaign and then a player; **Delete being** names what goes with it (ADR 0302) and asks for the name. A note a person may not read is absent, with no count.

## Consequences

- Edit as a mode is gone; the code of the current sheet has an Edit mode that the design replaces.
- Which stats are pinned, adjustable in play or derived is the library's Settings and is not designed here.
