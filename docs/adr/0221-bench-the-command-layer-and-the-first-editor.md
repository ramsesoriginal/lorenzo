# 0221 - Bench: the command layer, and the first editor on it

Status: accepted, decided with the maintainer on 2026-10-09. The first part of slice B3 of [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) (sections 2 and 7). Builds on [ADR 0210](0210-bench-app-stack-and-workbench-shell.md) and [ADR 0211](0211-bench-sign-in-and-the-repository-picker.md).

## Context

Bench showed sample entries and wrote nothing. B3 is the online-first item editor, built so that offline (B4) is later a matter of storing the outbox, not of rewriting the editor. The rest of B3 (creating entries, descriptions and notes, tags, stat values, the LIVE banner) follows in later pull requests; this one is the layer they all sit on, and the two edits that prove it: name and parents.

## Decision

- **Every change is a command** (`src/core/commands.ts`): a type and version, the entry, the field it changes with the value the person saw (`base`) next to the new one (`mine`), and a state: waiting, sending, synced, conflict or needs attention. The registry says how to read the field from the server's item, how to apply a command to it, and how to send it. Two types exist, `entry.set-name` and `entry.set-parents`; a new one is a registry entry.
- **What is on screen is the mirror with the outbox applied** (`src/core/bench.ts`). Cancelling a command that has not been sent is taking it out. Undo of one that has been sent queues its inverse, built from its base. There is no session-only undo beside it.
- **The runner sends one command at a time, in the order written.** Before each send it reads the item, and compares the field three ways (RFC 0039 section 5): the server already has mine (synced, nothing sent), still has the base (send, with `If-Match`), or has something else (**Conflict**, nothing sent). A stale `If-Match` is read and tried once more. A command that finds no connection stays waiting and the runner stops; a refusal for any other reason is **needs attention**, with what the server said. A command that is stuck holds back later commands on the same entry only, so one disputed entry does not strand the others.
- **A conflict is resolved here only by choosing**: Keep mine (sent over theirs) or Use theirs (the command is dropped). The three-way review with text and set merging is B5; parents are compared as sets here, with no element-wise merge.
- **The outbox is in memory.** It does not survive a closed tab (B4). What a person sees says so in the six words of ADR 0194: Saved on this device (no connection), Waiting to sync, Synced, Conflict, Needs attention.
- **A transport interface** (`src/core/transport.ts`) is all the layer knows of a server. The real one is built on the typed client (`src/lib/transport.ts`) and speaks `GET /entities`, `GET`, `PATCH` and `PUT .../prototypes` on items, with `If-Match` from the item's `ETag`; the sample one (`src/core/sample.ts`) is a server in memory with the same `ETag` and refusal behaviour. The page without sign-in, and the browser tests, run the whole editor on the sample one.
- **Only items are edited** in this slice. The explorer lists every entry with its kinds; a being or a bare entry is shown and says so.
- **Not in this slice**: creating entries (it needs the client-made ids of W2, or the interim rule of RFC 0039 section 6), descriptions and notes, tags, stat values, the LIVE banner, duplicating (K4), and the stat pane. W1 to W3 are not needed yet.

## Consequences

- B4 adds a store and a service worker under the same layer: the outbox is already data, and commands carry a version for upgrades.
- The sample transport is how the layer is tested end to end in CI without a server. It does not replace a run against the real API; that is the first thing to do by hand, and a browser test against `apps/api` (as inventory-web has, ADR 0114) is a later slice.
- `GET`ting an item before each write costs a request per command. It is what makes the compare and the `If-Match` possible, and it is cheap next to the write.
