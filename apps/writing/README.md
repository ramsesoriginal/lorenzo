# Lorenzo Writing

A quiet writing surface for library and repository Authors. Start with a standalone Scene,
an unassigned Chapter or a Book. Books create their first Edition automatically. Write
LorenzoScript and ordered pictures, nest Chapters in an outline, interleave them with prose,
and read the composition continuously. Another Edition independently copies the manuscript.
Descriptions and notes stay separate. See RFC 0047 and ADRs 0327–0329, 0341–0343.

The outline offers explicit up/down ordering and placing unassigned Chapters; removing a Chapter
from an outline keeps its text and subchapters. Edition copying starts private, without copying
notes or history. All editing retains conditional autosave, per-account browser recovery and
saved prose revisions. Cross-parent moves, splitting/joining, Carriers and
subsequent slices remain in [the accepted proposal](../../docs/rfcs/0047-lorenzo-writing.md).

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
Splitting within a text block, joining and redirects remain subsequent W5 slices.

## Run and verify

- `mise run //apps/writing:dev` — port 4327.
- `mise run //apps/writing:lint`, `:test`, `:build` — normal app checks.
- `mise run //apps/writing:test-e2e` — real API, isolated Postgres database, fake Authgear.
  Set `E2E_BROWSER_CHANNEL=msedge` to use installed Edge locally.

The app uses the shared brand, app shell, API client, LorenzoScript editor and Information
bundle editor. No app-specific CSS. `PUBLIC_API_BASE_URL`, `PUBLIC_AUTHGEAR_ENDPOINT`,
`PUBLIC_AUTHGEAR_CLIENT_ID` and optional `PUBLIC_BRANDING_CSS_URL` configure the build.

Unsent drafts (including image Files) live in IndexedDB, separately by API/account/library/
manuscript and editor session. They survive closing a tab. Local drafts are opened only after
the server authorizes the current editor; signing out clears the visible page, not that account's
pending recovery. Storage failure warns to keep the tab open. Concurrent server edits stop
autosave and require an explicit choice. This is not offline browsing or live collaboration.
Server revisions contain prior content, never old sharing grants; deleting Information deletes
its history. This screen does not offer that destructive action.

Hosting is **not configured or deployed**. Follow [the setup guide](../../docs/operations/writing-setup.md).
