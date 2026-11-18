# Lorenzo Writing

A quiet writing surface for library and repository Authors. Start with a standalone Scene,
an unassigned Chapter or a Book. Books create their first Edition automatically. Write
LorenzoScript and ordered pictures, nest Chapters in an outline, interleave them with prose,
and read the composition continuously. Another Edition independently copies the manuscript.
Descriptions and notes stay separate. See [RFC 0047](../../docs/rfcs/0047-lorenzo-writing.md) and ADRs 0327–0329, 0341–0348, 0374 and 0378–0382.

The outline offers explicit up/down ordering and placing unassigned Chapters; removing a Chapter
from an outline keeps its text and subchapters. Edition copying starts private, without copying
notes or history. All editing retains conditional autosave, per-account browser recovery and
saved prose revisions. Personal length goals, session goals and timers, reviewed name/date
suggestions and manuscript repository updates are available; their details appear below.

Scene reuse creates a separate telling each time. A shared telling reads the Scene manuscript;
Make independent copies its current prose and pictures before editing. Viewpoints and world
references are explicit choices in Details, with no inferred Events or sharing. Character
biographies are private Being entries intended for writing, without campaign or inventory powers.

Authors can open Review and reviewers for an Edition, add an existing signed-in account by
email, and share its review address. The grant covers only that Edition's manuscript tree and
pictures. Reviewers read and write their own LorenzoScript notes, visible only to them and
Authors. Revocation closes subsequent reads and clears an open review at its next revalidation
(within 30 seconds, or on returning to the page). Reviews do not grant library membership,
source Scene access, research, editing or saved history. Grants and review notes are excluded
from repository copies and releases. Review notes use explicit Save; they are not stored offline.

## Moving writing

The outline's **Move** action finds an Edition or Chapter by title, chooses a position,
promotes a nested entry one level, or makes it unassigned. A Chapter moves with its subtree;
a Scene telling keeps its identity and shared or independent manuscript. Text, pictures and
notes are preserved. Moves check the entry and both outlines, reject cycles and refuse to add
reviewers implicitly. A retry acknowledges the original operation without applying it twice.
Operational move receipts and structural checkpoints are excluded from repository copies.

This is RFC 0047 W5a ([ADR 0344](../../docs/adr/0344-atomic-manuscript-moves.md)).
The optional **Extract a Chapter** action moves a consecutive range of complete text blocks,
pictures and child entries into a new Chapter at the same position (W5b,
[ADR 0345](../../docs/adr/0345-extract-outline-into-chapter.md)). It preserves payload identities,
LorenzoScript, audiences and notes, with a saved manuscript revision and structural checkpoint.
**Split text** divides a saved text block at a safe section boundary (W5c,
[ADR 0346](../../docs/adr/0346-safe-paragraph-splits.md)). Place the cursor at the section
that should begin the second block, choose it and confirm. Both parts keep their wording,
locale and audience; either can then be extracted into a Chapter. A saved revision retains
the original text. The first part keeps its payload identity; the second receives a new one.

The parser-aware splitter ([ADR 0347](../../docs/adr/0347-syntax-aware-manuscript-splits.md))
accepts boundaries between complete lists, quotations, tables, code, display math and class
blocks, as well as distinct headings. It keeps footnote dependencies and potentially colliding
heading anchors together. Texts with contents directives, abbreviations or local fragment links
still stay whole. Place the cursor after a blank line at the start of the next section;
an unsafe boundary is refused without moving the cursor's choice.

**Join with previous** combines adjacent sibling Chapters ([ADR 0348](../../docs/adr/0348-chapter-joins-and-guarded-redirects.md)).
Text blocks, pictures and children keep their identities and wording. The former Chapter keeps
its notes and history, with a link to its section in the destination when that section is still
available to the reader. Matching sharing and current versions are required. Old unsent text
can be copied from a read-only recovery view. **Join into parent** ([ADR 0374](../../docs/adr/0374-join-chapter-into-parent.md)) removes a
Chapter heading from the outline and puts its text, pictures and children in its place,
preserving the reading order. The parent may be a Chapter or Edition; the old Chapter keeps
the same guarded link, notes and history as a sibling join.

**Extract a Scene** ([ADR 0378](../../docs/adr/0378-extract-writing-into-a-scene.md)) moves
consecutive text blocks and pictures into a reusable Scene, leaving a shared telling in their
place. It preserves payload identities, wording, pictures and sharing; notes stay at the source.
Selections containing Chapters or tellings are refused. Use the Scene elsewhere to share edits,
or **Make independent** on a telling to write a separate version.

**Carriers** ([ADR 0379](../../docs/adr/0379-carriers-and-ordered-coverage.md)) can stand alone
with their own writing. In Outline, **Carrier form** selects ordinary prototype parents, and
**Covered writing** includes whole Editions, Chapters, Scenes or tellings, or a single text/picture
block. References can cross Books and interleave with direct prose. Source edits remain visible;
removing coverage leaves the source intact. Coverage grants no access and is not physical containment.

**Chapter numbering** ([ADR 0380](../../docs/adr/0380-chapter-numbering.md)) is optional and
separate from titles. Open Numbering in an Edition's outline (or an unassigned Chapter tree)
to choose each level's format, start and parent restart behavior. Chapter controls can override
a number, leave a Chapter unnumbered, restart or end a sequence. Outlines, continuous reading
and Book reviews show the resulting labels. Moving Chapters recalculates them; copies retain
the settings. Hidden Chapters do not leave numbering gaps.

**Structural contents and special Chapters** ([ADR 0381](../../docs/adr/0381-structural-contents-and-special-chapters.md))
use the closed Contents control in Outline. An Edition or standalone Chapter tree chooses its
list, depth and a text template with `{title}` and optional `{number}`. Each Chapter can be
included or excluded independently; included descendants remain listed. Contents Chapters place
the generated list before their authored prose. Index and Glossary Chapters stay authored
LorenzoScript. Reading and Book review links respect the reader's access. These lists do not
combine headings inside separate texts, and do not generate indexes, glossaries or page numbers.

**Link to an entity** ([ADR 0396](../../docs/adr/0396-reviewed-manuscript-links.md)) lets an author
select one name in manuscript prose, find accessible entries and choose by link name. The
label keeps the exact selected wording. Undo, autosave and saved backlinks use the ordinary
LorenzoScript editing path.

**Suggested Being references** ([ADR 0395](../../docs/adr/0395-reviewed-being-references.md))
appear in Details when editing a Scene. Choose **Check names** to scan the current prose for
accessible Beings. Choose a unique match to add a private Scene reference. The review flags
names shared by several Beings and asks for a fresh scan when the draft or references change.

**Writing session goals** ([ADR 0394](../../docs/adr/0394-personal-net-new-writing-session-goals.md))
count net editing changes after Start, including unsaved work. Deletions subtract; structure
changes, loaded revisions and other authors' versions add no credit. Progress follows this
browser tab across entries and reload, separately for each account and library. Finish retains
the result until you explicitly start a new session. This is drafting progress, not saved activity.

**Writing timer** ([ADR 0393](../../docs/adr/0393-personal-writing-timer.md)) lives inside
Word count in Write. Choose minutes, start, pause, resume or reset. It survives reload and
entry navigation within this browser tab, separately for each account and library, and
quietly shows when time has elapsed. Closing the tab ends its recovery lifetime.

**Personal word targets** ([ADR 0383](../../docs/adr/0383-personal-manuscript-length-goals.md))
are available inside Word count. Each Author keeps separate targets for direct draft prose and
assembled reading, with live remaining-word progress. Targets belong to the account and are
excluded from Edition duplication and repository content.

**Word count** ([ADR 0382](../../docs/adr/0382-manuscript-word-counts.md)) measures the current
direct prose in Write, including unsaved edits. In Read or a Book review, open Word count to
measure the assembled manuscript, highlight a displayed passage or choose text blocks. Repeated
Carrier references count on every appearance. Referenced footnote prose counts once per block.
Generated navigation, code, math, notes and structural titles contribute no words.

## Run and verify

- `mise run //apps/writing:dev` — port 4327.
- `mise run //apps/writing:lint`, `:test`, `:build` — normal app checks.
- `mise run //apps/writing:test-e2e` — real API, isolated Postgres database, fake Authgear.
  Set `E2E_BROWSER_CHANNEL=msedge` to use installed Edge locally.

The app is in the web shell ([ADR 0494](../../docs/adr/0494-writing-moves-into-the-web-shell.md)), and uses the shared brand, app shell, API client, LorenzoScript editor and Information
bundle editor. No app-specific CSS. `PUBLIC_API_BASE_URL`, `PUBLIC_AUTHGEAR_ENDPOINT`,
`PUBLIC_AUTHGEAR_CLIENT_ID` and optional `PUBLIC_BRANDING_CSS_URL` configure the build.

Unsent drafts (including image Files) live in IndexedDB, separately by API/account/library/
manuscript and editor session. They survive closing a tab. Local drafts are opened only after
the server authorizes the current editor; signing out clears the visible page, not that account's
pending recovery. Storage failure warns to keep the tab open. Concurrent server edits stop
autosave and require an explicit choice. This is not offline browsing or live collaboration.
Server revisions contain prior content, never old sharing grants; deleting Information deletes
its history. This screen does not offer that destructive action.

The app is a single page, `/`, driven by `?tenant=` and `?entry=` (plus `/auth/redirect/` for sign-in).

Deployed at <https://lorenzo-writing.pages.dev/> on Cloudflare Pages; [the setup guide](../../docs/operations/writing-setup.md) records the procedure. `.env.example` lists the build variables.

**Suggested periods** ([ADR 0397](../../docs/adr/0397-reviewed-scene-periods.md)) in direct Scene Details
checks prose for full names of existing visible calendar periods. Review a match and explicitly
set an empty Scene period. Ambiguous names use the manual Period lookup. Existing periods, relative
dates and dates not yet created in a calendar are never filled or replaced automatically.

**Repository updates** ([ADR 0438](../../docs/adr/0438-atomic-manuscript-repository-updates.md))
are available in Details and Outline under **Composition updates**. Review connected writing,
attachments and structure against the original copy, choose which changes to keep or take, then
apply the selected changes together. This covers Books, Editions, Chapters, Scenes and tellings,
biographies and Carriers, including placements, coverage, redirects, numbering and contents.
Stable elements keep their identities when moved between manuscripts. Incomplete dependent
choices are refused without applying part of the update. Local additions and entries removed
upstream remain in the library; ordinary notes retain their existing update behavior.

Older copies explicitly show when the original composition was not recorded. Keeping or taking
that version establishes a baseline without inventing history. Updates read the currently allowed
repository source, including its published release when public. Missing world dependencies and
link-name collisions must be resolved through the ordinary repository review first.

Save or recover affected browser drafts before applying updates, including drafts in other tabs.
Accepted changes preserve manuscript revisions and a private structural checkpoint, retain
existing audiences and reviewer grants, and add no writing-session credit. A change that would
widen access is refused until the author separately reviews sharing. New writing starts private.
Attachments are compared by their contents; the review does not show attachment previews.

The earlier **Repository comparison** remains available for direct text-only updates with unchanged
payloads and copied composition ([ADR 0398](../../docs/adr/0398-copied-manuscript-comparison.md),
[ADR 0429](../../docs/adr/0429-standalone-draft-repository-updates.md),
[ADR 0430](../../docs/adr/0430-placed-chapter-text-updates.md),
[ADR 0435](../../docs/adr/0435-nested-chapter-text-updates.md), and
[ADR 0436](../../docs/adr/0436-parent-chapter-text-updates.md)).

## Exporting saved writing

**Export** opens a preview of saved writing from the editor, assembled reading or Edition review.
It leaves unsent editor changes alone. **Download LorenzoScript** saves a ZIP containing exact
UTF-8 text, original picture bytes and a `lorenzo-writing/1` manifest. The manifest retains stable
entry/payload IDs, reading order, repeated Carrier coverage, shared tellings, source locales and
numbering/contents settings. It describes the selected authorized composition, not a library backup;
there is no import/restore operation. Notes, history and unrelated world references are omitted.

**Print / Save as PDF** opens the browser print dialog. Choose Save as PDF and turn off browser
headers and footers for a clean manuscript. The printable document uses LorenzoScript headings,
tables, local footnotes, pictures, Chapter numbering and contents, with self-hosted brand fonts.
Repeated passages have distinct local link targets. Pagination follows the browser's paper settings;
advanced publishing and other formats remain deferred.

Both outputs recheck access and the preview's version. If saved writing changes, refresh the preview.
Review exports remain limited to the granted Edition. Exports over 5,000 distinct entries, 20,000
reading occurrences or 50 MiB of text/pictures ask for a smaller section rather than truncating it.
See [ADR 0478](../../docs/adr/0478-manuscript-export-snapshots.md) and
[the source archive format](../../docs/reference/writing-source-archive.md).
