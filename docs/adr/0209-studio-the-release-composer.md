# 0209 - Studio: the release composer

Status: accepted, decided with the maintainer on 2026-10-08. Slice T4 of [RFC 0036](../rfcs/0036-repository-tooling.md), tracked in #530. Builds on [ADR 0206](0206-studio-the-guarded-publish-dialog.md) (the publish dialog, whose body it replaces), [ADR 0207](0207-the-release-ledger.md) and [ADR 0208](0208-the-release-digest-and-the-breaking-change-detector.md) (what the API now says about a release), and [ADR 0203](0203-shelf-the-update-inbox.md) (the inbox it marks).

## Context

A publish used to be a timestamp and a message. [ADR 0207](0207-the-release-ledger.md) made it a release (a label, notes, a breaking flag) and [ADR 0208](0208-the-release-digest-and-the-breaking-change-detector.md) gave it a digest, a detector of what would break a library that already copied the repository, a preview of what a publish would release, and a `state` on every row a library is offered: part of the latest release, or edited since it. The hub used none of it: the publish dialog said only who would be told, and the update inbox took every clean row alike.

[RFC 0037](../rfcs/0037-releases-and-public-snapshots.md) sets the wording rule for all of it: what the interface says about a release is what was checked, in these words and no stronger.

## Decision

### The composer is the publish dialog's body

**Publish…** and **Publish a new release…** (a published repository's second, third and later publish) open the dialog of [ADR 0206](0206-studio-the-guarded-publish-dialog.md), which still says who will be told, what a library can do after, that reads are live and that GM-only notes travel, and now holds a release's own fields. Unpublish is as it was.

- **Label**: free text ("1.3", "Spring errata"), never parsed as a version. Left empty it is the release's number, which the field says ("Left empty, it is 2").
- **Notes**: free text.
- **"This release is breaking"**: the author's own flag, whatever the detector found.
- **What this release contains**, read from the API's preview (`GET .../release-preview`, which writes nothing) when the dialog opens: whether the repository matches the latest release or how many rows differ, a line for each kind with what was added, changed and removed, the names of what is new and what is removed (the first eight, and how many more), and, as a hint, how many descriptions were written or edited since the release. Beside it, always: **text edits are not tracked** (descriptions, notes and pictures are copied once, and updates do not carry them).
- **What it breaks**, where the detector found anything, in the API's own sentences ("“Troll” was removed. Libraries that copied it can only keep their copy, detached."), with a box to say **"I understand that these changes break libraries that already copied this repository, and publish them anyway."** The release cannot be made until it is ticked, and the publish carries `acknowledge_breaking`. If the API finds more than the preview did (the repository changed meanwhile), its refusal's rows replace the list and the box is cleared: the author is never publishing something they were not shown.
- A label already used in the repository, in any case, is refused in the API's words, in the dialog, which stays open.

### Words for matches and edited since

On the Overview, under the state: **"Matches release 1.3."**, or **"Edited since release 1.3: 4 rows differ."**, or that there is no release yet, or that the latest was made before releases could be compared. Never "stable", "frozen", "final" or "released" as a promise about the content, and always, beside it, that text edits are not tracked, with the description hint where there is one ("12 descriptions written or edited since release 1.3. This is a hint: a deleted description leaves no trace."), since the count cannot see a deletion.

### Releases, a tab

Newest first: label, whether it is **Breaking**, "Release 3, 2026-10-08" and by whom (named only where the person has a name: an id is not shown as one), its notes, a line for each kind it changed, and for a breaking one, folded, what it breaks. An **Owner** can **change a release's label and notes**, and nothing else of it: the number, the flag, the digest and what it held never change ([ADR 0207](0207-the-release-ledger.md)).

### In the update inbox

- Every changed and new row says what it is against the library's latest release: **In release 1.3** or **Edited since release 1.3**; and, from the releases the library has not taken, **Breaking in release 1.3: …** with the API's sentence for it. The page says which release is the latest.
- **Apply all clean takes only released rows that break nothing**, never an attachment, a conflict, a name clash, a removal, a row edited since the release or one a release called breaking (RFC 0037 §2). Rows from before releases existed carry no state and are taken as they were. The sentence before it says what it will take and what it leaves, in words, and the button is not there when nothing is left to take.
- **A row a release called breaking is applied only after its notes are read**: the button asks first with each note and says that the library takes the change as the repository made it, then sends `confirm`. The API refuses the same action without it (`update-needs-confirmation`), so the page and the API agree. Detaching is exempt, as in the API.

### Who is on which release

An Owner's **Libraries using it** says which release each library is on ("on release 1.2"). A library's page for a repository says **which release it last took and which is the latest**, in words, and never says "up to date": that is said only when its update list is empty.

### Tabs keep what was chosen

Six tabs do not fit a phone's width in one row; the brand's tab row wraps ([ADR 0205](0205-studio-libraries-using-it-and-built-on.md)). A person who chose a tab while its panel was still loading found themselves on the first one when it finished: a tabbed view now remembers the chosen tab while its panel is empty, and shows it when it fills.

## Not in scope

- **Release documents, the read switch, retention and rollback** (RFC 0037 R5 to R8), and everything about public repositories ([RFC 0038](../rfcs/0038-public-repositories-and-discovery.md)). "Make release current" waits on them.
- **Notes for the release that say what changed, written for the author.** The composer shows what the API found; it does not draft the notes.
- **Release marks on a removed row of the inbox**, which the API gives and the page does not yet show; a removal's only action, detach, is exempt from confirmation.

## Consequences

- A publish says something: a label, notes, what changed, whether it breaks, and who is on which release. A breaking change cannot be published by accident, and one cannot be applied by accident either.
- The inbox's bulk button takes less than it did: rows edited since the release wait for the author's next release or for a choice. For a repository that never made a release it behaves as before.
- The dialog is longer; it scrolls inside itself, and is checked at 375px.
