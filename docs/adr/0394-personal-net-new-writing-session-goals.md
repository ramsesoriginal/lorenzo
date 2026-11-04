# 0394 - Personal net-new writing-session goals

RFC 0047 W8c follows length targets (ADR 0383) and the personal timer (ADR 0393).

## Decision

Inside Word count in Write, an Author can choose a positive whole-word session target, start
counting from the current draft, finish, and explicitly begin a new session. Show signed net
words and words remaining or that the target is reached. Deletions subtract, including below
zero; undo adds or subtracts the corresponding difference. Use ADR 0382's exact browser prose
counter, including its footnote and non-prose rules. Counts include unsaved editing and pasted
prose. This is personal drafting progress in this tab, not saved activity or a contribution audit.

Count only changes made through the current Writing editor after Start. Starting takes the
current draft as a baseline, so earlier text and recovered unsent work do not earn new credit.
Rebase without credit when mounting a revision, accepting a server version or opening an entry.
Structural operations live outside the editor's change path and contribute zero; picture-only,
ordering and formatting changes contribute zero when prose length is unchanged. A session spans
entries within one library. Save retries and successful saves do not themselves change progress.
Flush pending local edits before a rebase, Finish or page exit. Debounce counting while typing,
and do no session parsing when inactive. Neither counting nor saving replaces the editor or focus.

Keep target, signed net count, active state and a session identifier in sessionStorage under
API/account/library, independently of the timer. Only the current tab participates, with normal
reload recovery; other tabs and devices do not synchronize. Authorization precedes reading local
state, and existing sign-out/revocation teardown removes the controls. A storage failure shows
that reload recovery is unavailable while retaining in-memory progress. Malformed state is ignored.
Closing the tab ends its recovery lifetime; abrupt browser loss before a pending local update is
stored may lose progress, while manuscript draft recovery remains its separate existing mechanism.
No server table, repository content or campaign Session record is introduced.

## Validation

Exercise positive and negative changes, undo, retries, formatting/pictures/reordering, session
boundaries, revision/external-version rebasing, entry navigation, reload and account isolation.
Test storage failure and malformed state. Verify the real API browser flow, phone accessibility,
long-text responsiveness and editor focus, and run all affected CI checks. Timer and manuscript
length targets remain independent measures.
