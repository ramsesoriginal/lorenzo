# 0409 - The web interface principles

Status: accepted, decided with the maintainer on 2026-11-04. Part of [RFC 0050](../rfcs/0050-the-web-interface.md). The design is [docs/design/web](../design/web/README.md), D7 to D11.

## Context

Lorenzo has several web apps built at different times, each with its own look for the same jobs. The maintainer asked for a design for all of them at once, on clickable prototypes, and for rules a screen can be tested against.

## Decision

- **Ten principles, each with a test a screen can fail:** the first minute needs no manual; honest state in words and an icon; neutral first, with colour as state and never the only signal; a keyboard path for everything, with hover as decoration only; a phone as a first-class width, designed and checked at 430; power added and never required; the same job looks the same in every app; setting-free words; every screen draws its bad days (empty, loading, error, conflict, partial permission, offline); modern CSS and motion that orients, each behind `@supports` with a static fallback and removed by reduced motion.
- **Chrome is a hybrid** (D5): page structure is quiet, with a hairline and space and no boxes; a bordered card is for a thing that is an object (a person, a note, an entry).
- **A control has a visible edge** (D6) at a contrast of at least 3 to 1 against its surface (WCAG 2.1, 1.4.11), through a new token, `--border-control`.
- **Visibility in a table** (D10): everyone is plain text; every other audience is the neutral badge with an icon and a word.
- **Selection** (D11) stays `--surface-selected`; **toolbar icon buttons** (D15) have no edge; **effects** (D9) serve orientation, with parallax and the canonical glow on home and empty-state pages only, unless a design says otherwise.
- **Fixed from the brand:** token roles and names, the three typefaces, Archive Blue for action, gold as punctuation, neutral visibility, the icon atlas, the voice of identity §14 and accessibility (§15).

## Consequences

- A screen is reviewed against ten tests, not taste. Each app design in this set records which of them it needed to bend.
- `--border-control` and the other new tokens are not in `apps/brand` yet; they are a follow-up listed in [the design's follow-ups](../design/web/follow-ups.md), and the prototypes carry them in `proposed-tokens.css`.
- Nothing here changes an API.
