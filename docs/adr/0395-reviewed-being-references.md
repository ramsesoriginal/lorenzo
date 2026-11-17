# 0395 - Reviewed Being references from Scene prose

RFC 0047 W8d extends the explicit Scene references of ADR 0342.

## Decision

In the direct Scene editor, an Author can ask Details to find Being names in the current
manuscript, including unsaved prose. Use the existing authorized, paginated Being list.
Match names locally against the rendered text of each description payload. Use Unicode
normalization, case-insensitive whole-name matching and the prose boundaries of ADR 0382.
Keep each payload separate. Skip code, math, pictures and generated navigation. Start a
fresh scan on request and keep matches only in the mounted review.

Present a unique visible match as an individual choice. Flag duplicate visible names and
leave their resolution to the author's manual Being lookup. Group before filtering existing
references so adding one namesake cannot make another namesake appear unambiguous.

Only an explicit acceptance writes the ordinary private Being reference using its conditional
version. Require the same draft and check the current target name before accepting. The API
enforces permission on both entries. A stale result asks the author to check again. Accepted
references retain the existing removal, sharing and repository behavior.

Prose linking and explicit-date suggestions have separate delivery slices. No participation,
knowledge or causal assertion follows from a name match.

## Validation

Exercise formatted and Unicode names, punctuation, substrings, ambiguity, existing references,
stale text and permission-filtered candidates. Verify a scan performs only reads and a single
acceptance creates the selected reference while preserving the manuscript.
