# 0411 - Web widths, container queries, density and type

Status: accepted, decided with the maintainer on 2026-11-04. Part of [RFC 0050](../rfcs/0050-the-web-interface.md). The design is [docs/design/web](../design/web/README.md), D8, D20, D22 and D23. Extends identity §8.4 and §8.5.

## Context

Identity §8.5 sets one breakpoint at 720px for phones. Apps also need a tablet step, a desktop step and a large screen, and components that work in any pane; spacing changes by window and not by container; and nothing says how type or density scale.

## Decision

- **Steps, not two modes** (D20): a phone to 720px, a tablet from 721px, a desktop from 1100px, a large screen from 1700px. The shell switches at 720px. Everything below the shell adapts to the space it is given, with **container queries**. The phone design width is **430** (D8).
- **At a tablet** a list shows the list alone and the detail opens as a side sheet; **on a large screen** a third pane may appear. **Content is capped in width**, and certain content (a board, a map or a wide table, the editor's outline) may use the full width.
- **Type is a set of semantic roles** (D23), not a ladder: Display, Title, Reading, Heading, Subheading, Body, UI, Meta, Micro and Code, with sizes in rem; editorial roles are fluid between 430 and 1440 with a clamp that has a rem part so zoom works, and interface roles are fixed. Nothing is below 12px; weights are 400, 500 and 600; numbers in tables use tabular figures; sentence case; the serif is for titles, names and reading text.
- **Spacing** is the brand's 4px grid plus one step, `--space-2h` (12px on desktop), for gaps in dense groups and field labels. On a phone the tokens stay halved at 720px and below, as the brand does today.
- **Density** (D22) has three levels: Comfortable (the default, 48px rows), Compact (36px) and Dense (28px, fine pointer only). Only row height and padding change, never type size. On a phone or a coarse pointer every level is at least 44px and the control is not offered. **Appearance** holds the density setting; **saved views** are a named layout per list (columns, sort, filters, density), per person and not shared; both are remembered in the account, which needs a preferences surface in the API that does not exist yet.

## Consequences

- The brand's spacing tokens must become container-driven; the prototypes redefine them by container so the simulated width works.
- Saved views and the remembered density are a follow-up slice with an API for a person's preferences.
- The 1760px cap is decided as the upper cap (the maintainer, 2026-11-07); 1700px is the large-screen step.
