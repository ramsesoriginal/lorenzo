# 0396 - Reviewed links for selected manuscript names

RFC 0047 W8e uses the LorenzoScript entity link and shared editor from RFC 0027 and ADRs 0106 and 0107.

## Decision

An Author selects one occurrence of a name in a manuscript text block and opens its link review.
Search the authorized entity list by name and compare full names case-insensitively. Show entries
with an assigned link name and distinguish namesakes by that link name. Keep every choice explicit.
Recheck the target identity, name and link name before insertion. Require the same editor, source
and selection. A stale choice requires a fresh search.

Use a labelled wikilink containing the target's assigned slug and the exact selected wording.
Limit the action to whole names in ordinary inline prose. Verify the replacement with the canonical
parser so the selected text becomes exactly one entity link and all surrounding syntax retains its
meaning. A selection spanning syntax, a link, code or other protected material stays available for
manual editing. Apply through the shared editor's ordinary edit primitive for focus, undo, autosave,
draft recovery and session word counts.

The review belongs to the direct Write surface. It creates a prose backlink through the existing
save path. Scene reference suggestions and calendar suggestions have their own controls and scope.

## Validation

Test literal wording, namesakes and assigned slugs, stale source and target, protected syntax,
undo, persisted backlinks, reader scope and phone accessibility through the real editor.
