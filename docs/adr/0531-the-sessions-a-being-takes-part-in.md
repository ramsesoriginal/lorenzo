# 0531 - The Sessions a being takes part in

Status: accepted and built, 2026-11-27, asked for by the maintainer as slice A2 of UI-H's API work ([ADR 0528](0528-ui-h-retiring-the-old-frame-and-auditing-the-apps.md), H3). It answers what [ADR 0524](0524-beings-and-inventory-move-into-the-web-shell.md) left out of a being's "Where it appears" page: the Sessions a being takes part in without being named in their text, "which needs its own read".

## Context

"Where it appears" (BN11) lists the information whose text links to a being, from the backlinks read ([ADR 0110](0110-lorenzoscript-content-references-and-backlinks.md)). A Session that a being came to, as one of the characters a player brought, or that a Scene tells of, has no text that names it, so the page cannot list it. The data is there: `session_character` (who came), `scene_being` (the Scenes that tell of a being) and `scene_appearance` (the Scenes a Session holds).

## Decision

- **`GET /tenants/{t}/beings/{id}/sessions`** returns the Sessions the being takes part in, each with `via`: `roster` (it is one of the characters on the Session's roster), `scene` (a Scene of the Session tells of it), or both. Ordered by the Session's real date (undated last), then name.
- **A being that is not a being, or is not there for this reader, is a 404** (the gate of [ADR 0529](0529-an-outer-audience-on-a-being.md) applies).
- **A Session is listed only when the reader may read it** (the entry gate). The rest follows what the Session's own pages already say:
  - the roster is read with the Session, so `roster` is shown to anyone who may read the Session;
  - a Scene telling is shown to whoever manages the Session (and the library's administrators) and, to others, only when both the Scene's appearance in that Session and the Scene's telling of the being are shared, as the Session's references say ([ADR 0317](0317-sessions-scenes-and-collaborative-planning.md)). The Scene and its appearance must be readable too.
- **Nothing is written, and nothing is inferred** from text, relationships or events: a being in a Session's notes is the backlinks page's business.

## Consequences

- No migration. One read, three small queries; the list is as long as the Sessions a being is in.
- The page's second list, "Sessions", is drawn from this read (H4). The existing list of mentions stays beside it.
- Tests: `tests/test_being_sessions.py` (who came; a Scene's telling, hidden from a player until the appearance and the telling are both shared; a Fact and a missing id are 404).
