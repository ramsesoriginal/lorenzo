# 0413 - Web states: retry, loading and the mascots

Status: accepted, decided with the maintainer on 2026-11-04. Part of [RFC 0050](../rfcs/0050-the-web-interface.md). The design is [docs/design/web](../design/web/README.md), D24 and [mascot-images.md](../design/web/mascot-images.md).

## Context

Apps show loading, failure and emptiness in different ways, and the mascots have no rule for when they appear.

## Decision

- **Retry:** a failed read retries by itself with a short backoff and says so; after it gives up, a "Try again" button stays. A write is never retried automatically.
- **Loading:** a spinner for a one-line wait only (a single field); a skeleton for everything else; a progress bar wherever the progress is known. The branded spark is for the rare branded waits (identity §17.9).
- **Mascots** appear where a whole page has nothing to show or cannot be shown (first run, a page with nothing in it, not found, no access, offline, a page-level error); never in a working page's region states and never in app chrome. Their images are listed for the illustrators, by id, with the words that sit beside each.
- **Copy** follows identity §14: clear, concise, precise, quietly playful, no over-cute speech and no apology boilerplate.
- **A hidden thing is never counted.** "No access" does not say whether the page exists, and no state says how many entries a person cannot see.

## Consequences

- The illustration list is the brief for the illustrators and grows with the apps (empty-beings, empty-map, empty-inventory, empty-social-web, empty-social-types, empty-relationships, device-connected and others).
- Every screen's six bad days are drawn in its design; the checks run them.
