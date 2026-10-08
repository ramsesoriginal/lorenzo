# 0201 - Shelf: the copy wizard

Status: accepted, decided with the maintainer on 2026-10-07. Slice S3 of [RFC 0036](../rfcs/0036-repository-tooling.md), tracked in #515. Builds on [ADR 0196](0196-shelf-the-repositories-list-and-page.md) (the list and the repository's page) and on [ADR 0194](0194-user-facing-terminology.md) (the words). Part of the v1.0 row "Publish, subscribe, update screens".

## Context

The API copies a repository into a library in a way built for being asked first: `GET .../copy-plan` says what a copy would bring and what it would clash with, and `POST .../copy` with `dry_run` does everything a copy does, every check included, and rolls it back ([ADR 0119](0119-copying-a-repository-into-a-tenant.md), [ADR 0120](0120-bridge-repositories-and-dependency-manifests.md)). The command line copies with them ([ADR 0159](0159-lorenzo-repo-commands.md)). The hub has no way to copy: Shelf's page ([ADR 0196](0196-shelf-the-repositories-list-and-page.md)) says what is inside a repository and stops there.

A copy is the one thing in this program that cannot be undone as a whole, and it is made by someone at a table with a phone, who may be looking at a hundred name clashes. So it is a flow with a check in front of it, not a button.

## Decision

### A place of its own

The wizard is part of Shelf's page, with an address like the other views: `/repositories/?tenant=<library>&repository=<id>&copy=new`, or `copy=again`. It is a plain link from the repository's page (**Copy this repository**, shown for a repository that is invited, published and not yet copied; **Copy again…** under **More** for one that is), so it can be opened, shared and gone back to. A reload starts it again at its first step: nothing is kept between visits, because nothing has been written. An address that asks for a copy the library cannot make from where it stands (a first copy of a repository it has copied, a second of one it has not, a repository it is not invited to) shows the repository's page instead.

### Four steps, one primary button each

Numbered for the steps there are: the clash step exists only when there are clashes.

1. **Check first.** The limits of a copy are the first thing said, as sentences: it cannot be undone as a whole (the library can remove what it copied piece by piece, or copy again and replace it); a library works with one game system at a time for now, and a game system that has been copied cannot be taken out again ([ADR 0183](0183-setting-up-the-four-repositories-and-what-trying-it-showed.md)); notes the repository marks GM only are copied along and stay GM only, players never see them ([ADR 0119](0119-copying-a-repository-into-a-tenant.md)); and nothing is shared afterwards except updates, which never arrive by themselves. Then what it brings, in counts, one line for the repository and each repository it is built on that the library has not copied; and how many names clash. The plan is asked fresh, not from the hub's cache: what it shows decides a copy.
2. **Name clashes.** One card for each, in words (“Your library already has a stat called “Weight”.”), with the glossary's three choices: **Keep both**, **Use the existing one**, **Leave it out** (the API's rename, merge and skip). What each costs is said next to it: leaving out a stat group leaves out its stats and every value and formula that uses them; a new link name leaves the copied text's links pointing at the library's own entry ([ADR 0119](0119-copying-a-repository-into-a-tenant.md)). Keep both asks for the new name, starting from one that shows where the copy came from, and a name is checked before it is sent (not empty, different from the one it clashes with, a link name in the link-name grammar). **The recommended choice is marked and none is chosen for anyone**: a stat group or a stat of the same name is nearly always the same thing, so Use the existing one is recommended where the API allows it (not across value types) and Keep both for a link name; Leave it out is never the recommendation. **Do what is recommended for all** chooses them at once. Going on waits until every clash is settled, with "3 of 7 settled" in words beside the button.
3. **Review.** The check-first copy, made and rolled back, shown as a receipt: "Would add 309 entries, 2 stat groups and 12 stats, use 2 existing stats, keep both of 1. Nothing has changed yet.", what it leaves out and why, and the full list by repository folded away. A choice can uncover another clash (merging a stat group makes its stats meet the library's own); the API reports it then, and the wizard returns to step 2 with the new clash added and a sentence saying so, keeping every choice already made.
4. **Done.** The same receipt in the past tense, and a link to the repository, which now reads Copied.

### Copying again

For a repository the library has copied, step 1 first asks what happens to the copy it has: **Keep it as your own, and copy again beside it** (the API's `keep`: the earlier copy's rows stay as the library's own, unlinked) or **Replace it** (`purge`). Choosing Replace asks the API how much of the library's own work a purge would also remove, with a check-first copy, and says it in words before anything is pressed ("It also removes 1 stat you added to a copied group, 2 formulas of yours"). If the names clash so that it cannot say yet, it says the count is given at the review. The clashes of Keep it come from the API's refusal, since no plan beforehand can show the rows an earlier copy left behind, so the wizard takes them from the `409` and goes on from there. The plan is not asked: for a repository already copied it counts nothing.

### What a refusal looks like

A copy the API refuses is explained where it arises, never as a status line: a repository it is built on that is not offered or not published (named, with whom to ask, and no button to press); a copy made already; a formula loop from a merge (with what to do: go back and choose Keep both for a stat that was merged); a choice that cannot work (shown at the clashes step, with the API's words). Anything else is shown as the API worded it.

### How it is built

The decisions are plain functions with unit tests (`lib/copyWizard.ts`): the limits, a clash in words, the explanation and recommendation for each choice, whether a choice can be sent, the choices as the API's `resolutions`, the receipt, what a purge also removes, and a refusal read from the API's problem body. The DOM is `components/RepositoriesPanel/wizard.ts` and markup in the same component. No new API: `copyRepository` in `lib/repositories.ts` is the only addition, and a write empties the hub's cache like any other. Focus moves to the step's heading when the step changes, and the buttons are disabled while the API is asked, so a double press asks once.

### Phone

One column, every control the brand's 44px target, one card per clash at the width of the screen, checked at 375px in a real browser for every step. The heavy case, a copy with many clashes, works on a phone and is designed for a desk.

### Tests

Unit tests for `lib/copyWizard.ts` and for the addresses; browser tests against the real API and a fake Authgear: a copy end to end with nothing written before the last button; clashes with the recommendations; each of the three choices and a bad name; a repository built on one the library cannot copy, which goes on once it can; copying again with Replace (the count of what it also removes) and with Keep; the address of a copy that cannot be made; and 375px. They run in the hub's CI suite ([ADR 0196](0196-shelf-the-repositories-list-and-page.md)).

## Not in scope

- **Partial copy, bundles and per-kind filters.** A copy is all of a repository and what it is built on ([RFC 0036](../rfcs/0036-repository-tooling.md)).
- **Undoing a copy.** There is none; it is named as a limit.
- **The entry behind a link-name clash.** The API reports the link name and the entry's id, not its name; the card says which link name clashes, and the entry is the one the repository's page lists with that name.
- **Who may copy.** Shelf is for a library's Owners and Organizers; the matrix for the Author role is [RFC 0040](../rfcs/0040-authors-and-invites.md)'s.
- **A system tag.** Whether the wizard warns or blocks for a second game system is decided with [RFC 0038](../rfcs/0038-public-repositories-and-discovery.md)'s profile; until then the limit is a sentence.
- **Updates.** The inbox is S4.

## Consequences

- Every copy a person makes in the hub is looked at first, in counts and in words, and what they chose is what they get, because the receipt is the API's own rolled-back copy and not an estimate.
- The counts in step 1 are the plan's, which leaves out a name that clashes until it is resolved, so with clashes the page says they are not counted yet and the review counts everything. A repository whose plan counts nothing (a repository it is built on is not offered) is not counted at all, and the wizard says why.
- The sentence about GM-only notes is true before and after campaign GMs can read what a copy brings (RFC 0036 A4): it says only who never sees them.
- A choice that needs the library's own data to be valid (a name that is not yet taken) is checked by the API at the review; the wizard checks only what it can know.
