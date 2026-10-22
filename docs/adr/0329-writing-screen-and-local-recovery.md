# 0329 - Writing's first screen and local draft recovery

Status: accepted. Implements [RFC 0047](../rfcs/0047-lorenzo-writing.md) W1.

## Decision

Use the shared Astro app shell, brand classes, Authgear, API client, LorenzoScript textarea
editor and Information bundle editor. A library/repository picker leads to drafts; a new draft
is a private Scene with a designated manuscript bundle. Existing Scenes can acquire one without
converting research or descriptions implicitly. The screen keeps writing primary, with Details
and saved revisions opened on demand. No new component framework or general styling system.

Persist unsent bundle drafts, including pending image Files, in IndexedDB. Keys include the API
origin, signed-in account, tenant and manuscript. Read the current server editor snapshot before
opening a local draft: authenticate and authorize first. Keep the original server version and
write receipt with each draft. Conditional saves serialize; typing during a save stays in the
editor and schedules the next save rather than being overwritten by its response. Save failures
and storage failures remain visible. A conflict stops autosave until the author explicitly
chooses which version to continue from; preserve their local draft throughout review.

A browser close retains pending drafts; signing out clears the visible editor and in-memory
content but retains per-account drafts for that same account's next authenticated visit.
Signing in as someone else never loads them. A denied server read removes that manuscript's
local draft and shows no content. Drafts are local browser data, not an offline library or a
secret vault; the interface explains this where recovery is offered. Saved drafts are removed
only after a confirmed matching save. Navigation warns while unpersisted work remains.

Saved revision recovery is explicit: inspect the saved revision, load its text/pictures into a
local draft against the currently authorized manuscript, then save normally. No restored grants.
History deletion follows explicit Information deletion (ADR 0328), which this first screen does
not offer. Full offline browsing and collaboration remain deferred.

## Validation

Exercise recovery after reload, typing during saves, images, storage failure, conflicts, account
separation and revoked access. Run browser flows against the real API, including narrow screens,
keyboard operation and accessibility checks. Hosting stays unconfigured until the documented
Authgear client and Cloudflare Pages setup is completed.
