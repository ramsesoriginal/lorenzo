# 0304 - Atomic information audiences

Status: accepted, decided with the maintainer on 2026-10-16. First slice of RFC 0044.

## Context

Information already has `is_public` and character/group/player knowledge grants. Clients
currently patch and add/remove grants in separate requests, allowing partial audience edits.
Every authorized editor should inspect and change the same explicit audience.

## Decision

`GET /tenants/{t}/information/{id}/audience` is gated exactly like editing. It returns
`is_public`, `entity_ids`, `player_ids` and the information version as an ETag.
`PUT` to the same resource atomically replaces the public flag and both grant sets. It
requires `If-Match`; a missing precondition is 428, a stale one is 412. Unknown or other-tenant
recipients are 422 and change nothing. Entity recipients use the existing same-tenant entity validation, which includes bare empty
groups without imposing a new kind requirement. Explicit Player grants remain supported.

The information row is locked before checking the version. Grant changes advance its
`updated_at`, including the older single-grant endpoints, so an old audience cannot overwrite
a concurrent share. An unchanged replacement is a no-op. Audit entries record ids/counts and
public/restricted state, never content. Existing endpoints remain usable.

Editors display explicit recipients and a brief explanation of role-based access, rather than
pretending that a named grant enumerates every effective reader. Public does not mean internet
publication; it means everyone with applicable library access. Restriction cannot bypass the
entry's outer gate, and no operation silently adjusts that gate.

## Consequences

One request can safely change several recipients. Existing edit authorization, current group
membership and campaign-independent read semantics remain in force. No migration or new
knowledge model is needed. Beings and inventory-web replace request chains with this operation;
Bench and Android consume it in their respective slices. SQL filtering and byte reads continue
to use the common visibility resolver.


## Web controls

`packages/information-editor` holds the small framework-free audience control used by Beings
and inventory-web, and subsequently Bench. It opens from Who can read this, reads recipients
only when opened, and uses the atomic endpoint to save. It offers characters and groups and
preserves existing Player grants, which can be removed explicitly. Ordinary note creation
retains its current defaults; the control is available on the saved information, including
existing descriptions. Bench and native note creation add it in their slices.
