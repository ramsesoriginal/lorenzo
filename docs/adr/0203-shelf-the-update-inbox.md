# 0203 - Shelf: the update inbox

Status: accepted, decided with the maintainer on 2026-10-07. Slice S4 of [RFC 0036](../rfcs/0036-repository-tooling.md), tracked in #520. Builds on [ADR 0196](0196-shelf-the-repositories-list-and-page.md) (the list and the page), [ADR 0201](0201-shelf-the-copy-wizard.md) (the wizard, whose clash cards it reuses) and [ADR 0197](0197-names-in-update-diffs.md) (names in the diff, which it reads). Part of the v1.0 row "Publish, subscribe, update screens".

## Context

A copy never changes by itself ([ADR 0119](0119-copying-a-repository-into-a-tenant.md)). When the repository's author corrects a stat or adds an entry, the library finds out from the API's updates ([ADR 0121](0121-repository-updates-and-re-sync.md)): `GET .../updates` compares three versions of every copied row (what was copied, what the repository has now, what the library has) and `POST .../updates` applies the rows named. The command line does all of it ([ADR 0159](0159-lorenzo-repo-commands.md)). The hub says only "Update announced", from `published_at`, and that what changed "is not shown here yet" ([ADR 0196](0196-shelf-the-repositories-list-and-page.md)).

An update is the second thing in this program that changes a library, and unlike a copy it changes things the library has already used and may have edited. So the screen has to say what changed in words, keep apart what the library changed too, and never apply anything it was not told to.

## Decision

### Two screens, both plain links

- **The inbox**, `/repositories/?tenant=<library>&updates=1`: a row for each repository the library has copied, from a **Check for updates** link on the list. Each row is checked and says, in words, what it found: "4 changed, 12 new, 1 removed upstream, 1 conflict, 2 parents added or removed", or "Up to date". The rows with the most to do come first. A copy whose repository is no longer offered or not published is listed as such and not checked. A check reads a whole repository ([ADR 0121](0121-repository-updates-and-re-sync.md): fine at today's sizes, unmeasured at large ones), so the inbox checks three at a time and each row fills in as its answer comes; **the list of repositories itself asks for nothing**, which keeps what the scale spike ([RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) R2) is to decide undecided: a badge for a whole library is a later step.
- **A repository's updates**, `&repository=<id>&updates=1`, from a row of the inbox or from **Check for updates** on the repository's page (shown for a copy that is still offered and published). An address for a repository the library has not copied, or can no longer be updated from, shows the repository's page instead.

### What the page says

At the top, once: the counts in words; that **descriptions and notes, where things are held and who owns them are copied once and never updated** ([ADR 0121](0121-repository-updates-and-re-sync.md)), so a fixed typo there does not arrive; that **nothing is applied until you apply it**; and that **applying an update changes what your players see**. Then the rows, in groups, each with its count:

- **Conflicts**: rows with a field the library changed too.
- **Changed**: rows the library has no edit in.
- **New**: rows the repository has and the library does not.
- **Removed upstream**: rows the repository dropped. The library's copy stays; the only action is **Detach**, which stops the comparison ([ADR 0121](0121-repository-updates-and-re-sync.md)).
- **Parents added by the repository** and **parents the repository took off**: the attachments of [ADR 0172](0172-attachments-a-parent-a-bridge-adds-to-a-copy-travels-with-it.md), said as a sentence ("“Dagger” would inherit from “Weapon”") since the interface has no noun for them, each with **Add this parent** or **Detach**, and, when one end is not here yet, why it cannot be added.

A group shows 25 rows and a **Show more** for the rest. Rows the library deleted itself are listed folded away, with nothing to do.

### A changed field in words

Each field has its label and its values stacked, never side by side, so the same layout serves a phone: **Was** (what it was when the library last updated), **Now** (what the repository has) and, where the library changed it too, **Yours**. A set (what an entry inherits from, its stat groups, a stat's choices) shows what was **Added** and **Removed**. Labels are the product's: *Name*, *Link name*, *Inherits from*, *Stat groups*, *In the public catalog*, *Stat: Strength*, *Formula: Armour class*, with a formula read as words ("Strength × 0.5 − 5, rounded down"). A change to a stat's value type is shown and **cannot be applied** (every value would have to be converted); the page says so and offers no button for a row with nothing else in it.

**Names come from the API, never from an id** ([ADR 0197](0197-names-in-update-diffs.md)): every id a diff mentions is in the response's `names`, and one it has no name for is said as what it was ("an entry that is gone"). The client does no lookups of its own, so a row about something deleted upstream, or deleted in the library, reads correctly. A page test holds that no id and no `local:` marker reaches the text.

### What each button does

- **Apply** takes every clean field of a row. A conflict must be named, and the page asks per field: **Keep yours** or **Take the update, and replace yours**. Apply waits until each conflict has an answer, and says so beside the button.
- **Add to your library** copies a new row. A new row that clashes with a name is the same card as in the copy wizard (**Keep both**, **Use the existing one**, **Leave it out**, with what each costs, the recommendation marked, nothing chosen for anyone, a new name checked before it is sent: one component, shared with [ADR 0201](0201-shelf-the-copy-wizard.md)).
- **Skip** puts a row aside for now, out of what apply all clean takes, with an **Undo**. It is not an API action: the row is offered again next time.
- **Apply all clean** takes every changed row with no conflict and every new row with no name clash, and **never** a conflict, a name clash, a removal or a parent added: each of those needs its own decision. It is checked first, as a copy is: the API's own rolled-back apply is shown as a receipt ("Would apply 14 changes, add 12 new. Nothing has changed yet.") with **Apply now** and **Cancel**, and the sentence before it says what it will take and what it leaves.
- After any apply, the page says what was done in words and lists what **could not be applied** and why ("it is offered again next time", [ADR 0121](0121-repository-updates-and-re-sync.md)), and reads the updates again, since what is left is the repository's to say.

### How it is built

The decisions are plain functions with unit tests (`lib/updates.ts`): a field in words, a formula in words, the groups and counts, which rows apply all clean takes, the actions as the API takes them, and the receipt and the "could not be applied" sentences. The DOM is `updatesView.ts` and `inbox.ts` with markup in the same component; the clash card moved out of the wizard into `clash.ts` for both. `getUpdates` and `applyUpdates` in `lib/repositories.ts` are the only API additions on the client. No new API: this slice consumes A1 (`names`) and everything else as it is.

## Not in scope

- **Release marks** ("part of release 1.3" or "edited since"), which [RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) provides; until then the page shows what the API returns.
- **A notification that opens the inbox.** Notifications carry no link yet; "Check its updates" in the text says what to do.
- **A badge for a whole library**, and a count in the list of repositories, which wait on the scale spike.
- **Stopping updates** from a repository, which is the Owner's and its own slice.
- **Text comparison** of descriptions and notes.

## Consequences

- A library can see what a repository changed, in words, and take it row by row or all the clean ones at once, without losing an edit it did not choose to lose: every conflict is named, and a bulk apply cannot take one.
- The inbox opens a repository per row, so a library with many copies pays one check each when it opens the inbox, a few at a time. The list of repositories stays cheap.
- Edits a repository's author makes show in a check before they publish ([ADR 0183](0183-setting-up-the-four-repositories-and-what-trying-it-showed.md): reads are live), so a library can have updates for a repository the list still calls Copied. The repository's page offers the check for both states.
- The page depends on [ADR 0197](0197-names-in-update-diffs.md): against an API without `names` it would say "an entry that is gone" for every id.
