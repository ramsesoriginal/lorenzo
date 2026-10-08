# 0195 - A phone base in the brand CSS

Status: accepted, decided with the maintainer on 2026-10-07. Slice S1 of [RFC 0036](../rfcs/0036-repository-tooling.md), tracked in #502; the screens that build on it start with S2 (ADR 0196). Extends [ADR 0098](0098-branding-css-app-and-package.md) (`apps/brand` is the source, `packages/brand` its copy).

## Context

RFC 0036 makes phone layouts an acceptance criterion of every Shelf and Studio slice: a library admin checks "did the update arrive before the session" on a phone. The brand CSS had one responsive rule, the `.with-sidebar` collapse at 720px, and no rule about the size of anything a finger presses; [identity](../brand/identity.md) had no touch-target size, breakpoint or phone layout at all. Measured from the CSS, a button, a text input and a tab are about 39px tall, a header link about 29px, a chip's remove mark 16px. The page also doubled its gutter (`main`'s padding plus `.wrap`'s, 40px a side at 375px), and the header, a non-wrapping row, could not fit its lockup, its links and the theme button.

Nothing in the brand CSS needed hover to work, and `.tree`'s chevron animated regardless of `prefers-reduced-motion`.

## Decision

The base is a few additions to `apps/brand`, written into [identity §8.5](../brand/identity.md) and shown on `preview/outline.html`. They are plain CSS; `packages/brand` and the apps pick them up through the copy they already make.

- **One breakpoint, 720px**, the width at which the sidebar already stacks. A custom property cannot be used in a media query, so the number is written where it applies.
- **A token, `--target-min: 44px`**, the smallest size of anything pressed. At phone widths and for a coarse pointer (`@media (max-width: 720px), (pointer: coarse)`) buttons, text inputs, tabs, sidebar and header links, tree rows and outline nodes get that as a *minimum* height; a control already taller is untouched, and a desktop with a fine pointer keeps the sizes it has. A chip's remove mark keeps its look and gains a larger pressable area.
- **One column at phone width.** `main`'s padding drops to 16px and `main .wrap` loses its own gutter (the footer's `.wrap`, which has no `main` around it, keeps it); the header wraps; `.key-values` puts a name above its value.
- **`.outline`**, the pattern for a chain such as the repositories a repository is built on: a plain nested list, so it reads in order with a screen reader and needs no script. The rule down the left of a nested list is the edge: solid for a direct relationship, dashed (`.outline-derived`) for a derived one, as in [identity §18](../brand/identity.md). The line is never the only signal: every node carries its state in words (`.outline-state`, often a `.pill`) and, where a node cannot be read, a hint saying what to do (`.outline-hint`); the current node is a fill (`aria-current="true"`), separate from meaning. A node that cannot be read is quieter (`.outline-node--muted`), not hidden.
- **Reduced motion.** The `.tree` chevron's transition now sits behind `prefers-reduced-motion: no-preference`, as §15.4 asks.

Checked in the browser at 375px and at 1100px on the preview page: at 375px every pressable element measures 44px, nothing overflows and the key-values are one column; at 1100px buttons are still 39px, header links 29px, the key-values two columns and the header does not wrap.

## Not in scope

- **A stacked "was / now / yours" diff and a bottom action bar.** They arrive with the update inbox (S4), which needs them; §8.5 already says how a fixed bottom bar must look (a border, not a shadow, with room for the safe area).
- **A type scale, a breakpoint token or a shadow token.** None exists today and none is needed by this base.
- **Changes to how the apps load the brand CSS.** A new file would have needed entries in `packages/brand`'s `files`, `exports` and `.gitignore` and in each app's stylesheet list; the additions go into `layout.css` and `components.css`, which every app already loads.
- **A phone layout for inventory-web's board** and the other existing screens. Each is its own change; this base is what they would use.

## Consequences

- The Shelf and Studio slices can ship single-column screens with real touch targets without each inventing its own breakpoint.
- The existing screens of both apps gain larger targets and a single gutter at phone width without a change of their own. Anything that was laid out only for a wide window may now show how it behaves narrow; that is the point of the base, and each such screen is its own change.
- The 44px minimum is deliberately a minimum, so a dense desktop layout is unchanged and a coarse-pointer laptop or tablet gets the larger targets too.
- Brand rules gain a section they lacked: §8.5 is where the numbers live.
