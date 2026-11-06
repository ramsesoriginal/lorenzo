# 0423 - Lorenzo Inventory, redesigned

Status: accepted, decided with the maintainer on 2026-11-05. Part of [RFC 0050](../rfcs/0050-the-web-interface.md). The design is [docs/design/web/inventory-web](../design/web/inventory-web/README.md), IN1 to IN12. Keeps [ADR 0131](0131-the-board-on-controlled-by.md) and [0134](0134-board-refinements.md); a minimal redesign, so the board stays.

## Context

Inventory has a board the maintainer likes. The rest of the app (the pages around it, the catalog, Unsorted, the item page, the actions) was asked to be redone on the shared system.

## Decision

- **The board stays** (IN1): columns of cards, Equipped and Not carried first, then containers, then read-only columns that say who has them; a card that is not the being's own names its owner. It is Home, with Catalog and Unsorted (a GM's) as tabs.
- **The board's name is a switcher** (IN7): your characters, your groups, and for a GM a search for any being and the unowned things. The last board opened is remembered.
- **The board fills the page** (IN9), its columns as tall as the tallest and no taller than the screen; a long column scrolls inside itself and the sideways scroll sits above the status bar. **Equipped and Not carried carry a rotating gold ring** (IN10), still with reduced motion. **A column shows its weight and, with a limit, the room left** (IN8, IN11).
- **A phone shows one column at a time** (IN2), with Move to… as the way to move a card.
- **An item opens in a panel** (IN3), a sheet on a tablet, the page on a phone, with the same content. **A drag shows a ghost** and highlights its column (IN12); a column that cannot take it shows why and cannot be dropped on.
- **Actions** (IN4) are on the card and in the panel, with the shell's bulk bar and Undo toast and no separate Undo slot. Moving is not giving.
- **The catalog and item page** (IN5) write descriptions and notes in place and keep the link name, prototypes and public flag behind an explicit save bar, since they can break links.
- **The GM and author features are part of the design** (IN6): any board, a group's, the unowned board; making an item from the catalog; reassign, unassign, delete; catalog create, edit and delete with refusals in words; the Unsorted page with its matching; unpacking a pack.

## Consequences

- Error toasts stay until closed, as everywhere (D26).
- The notification bell moves to the shell's account menu.
