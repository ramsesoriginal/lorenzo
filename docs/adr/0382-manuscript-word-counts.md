# 0382 - Manuscript word counts

RFC 0047 W7c implements the manuscript-length measure from ADR 0327.

## Decision

Word count is an optional inline disclosure in Writing. In Write it measures current direct
manuscript text, including unsaved edits. In Read it measures the assembled manuscript after
loading finishes. A Book opens its Edition. Chapter subtrees, Scenes, shared or independent
tellings, Carriers and selected payload references use the reading view's existing ordering and
access checks. Each occurrence counts each time it is read. A reader can count a highlighted
passage or choose individual text occurrences. The Book review uses its existing scoped read.

Measure only manuscript text payloads. Use the same LorenzoScript rendering as the reading
view and count the visible prose in paragraphs, headings, tables, lists and link labels.
Inline formatting does not split a word. Block boundaries and breaks separate words. Exclude
code, math, generated contents, footnote reference numbers and backlinks. Referenced footnote
prose counts once per rendered payload. Include captions and image alternative text when shown
as prose. Picture payloads alone contribute zero. Entry titles, generated Chapter labels,
notes, structural contents and redirects are outside the text payloads. Count displayed inline
labels without resolving additional world data. Selection intersects the same text nodes, so
highlighting across headings, markup and notes cannot introduce extra words.

Use the browser's Unicode word segmenter with a fixed English locale, counting word-like
segments (including numbers). This gives the writer and reviewer the same rule independent of
browser language, with dictionary segmentation for supported scripts. Browser ICU versions may
differ. Count only on request, debounce active editor counts, and keep selection listeners
scoped to the reading surface. No count is stored, sent to the API, cached across readers or
copied into releases. Review revocation removes the count with its manuscript. Selection in
Read measures displayed text, and the Write view measures the current draft's own prose.

Goals, writing-session attribution, timers and exports remain their separately scoped slices.

## Validation

Exercise markup, Unicode, footnotes, code, generation, inline boundaries, multiple occurrences,
selected pieces and a partial passage in the real browser. Check live unsaved writing, repeated
Carrier coverage and Book-review access. Verify the normal desktop/phone views and accessibility.
