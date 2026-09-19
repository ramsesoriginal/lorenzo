# 0078 - Being listing and search endpoint

Status: accepted

## Context

`being` (RFC 0001/[ADR 0025](0025-character-being-and-ownership.md)) is the broader concept - anything sentient/agentive. `character` ([ADR 0031](0031-character-table-and-read-api.md)) layers a tracked, named individual under some beings; a bare `being` with no `character` row is still perfectly valid - an unnamed monster stub or background NPC not worth individual tracking.

Item-instance ownership already targets any entity generically - `Ownership.owner_character_id` and the item-instance owner write routes never validate that the target is specifically a tracked `Character` - so a GM can already assign an item to *any* being's `entity_id` today, if they already have that id. There's no way to discover one: `GET /tenants/{id}/characters` only returns rows with an actual `character` table entry (a bare being never appears there at all), and `GET /tenants/{id}/entities` returns every entity untyped - items, places, beings, all mixed, with nothing distinguishing a being from anything else. `apps/inventory-web`'s GM item-management board ([issue #77](https://github.com/ramsesoriginal/lorenzo/issues/77)/milestone 3) needs a "pick a being to own this" list, and neither existing endpoint answers it ([issue #94](https://github.com/ramsesoriginal/lorenzo/issues/94)).

## Decision

New `GET /tenants/{tenant_id}/beings?q=&page=&size=`, its own router (`routers/beings.py`, mirroring the one-router-per-resource convention every other resource type already follows), returning:

```python
class BeingSummaryOut:
    entity_id: UUID
    name: str
    is_pc: bool | None  # None when there's no Character row at all
```

A superset of `GET .../characters`, not additive to it - every `Character` is also a `Being`, and the client's actual need ("list every ownership-eligible being") is answered completely by one endpoint rather than two calls merged client-side. `is_pc` is genuinely three-valued, unlike `CharacterSummaryOut.is_pc` (always a real `bool`, since that schema only ever describes rows that already have a `Character`): `None` means no `Character` row exists at all, distinct from `False` (`Character` row exists, but `owner_player_id` is unset - an NPC someone bothered to track by name).

`name` reads `Entity.name` (the internal/reference name, matching `CharacterSummaryOut.name`'s own precedent), not any narrative title - a being's own base identity, not GM-authored flavor text. `q` matches it case-insensitively (`Entity.name.ilike(f"%{q}%")`), the same convention `GET /items?q=` ([ADR 0047](0047-item-catalog-search-and-container-convention.md)) already established.

Authorization: `get_tenant_context` (a full tenant-wide `Membership` row required) at the router level - the same tier `GET /tenants/{id}/characters` already uses, deliberately not loosened to `require_tenant_participant` even though this is a superset: this endpoint additionally reveals bare-being NPC stubs that `GET .../characters` never surfaces at all, so it stays at least as strict, not looser. `Entity.name` itself is not treated as GM-only/secret content anywhere else in this schema (`GET .../characters` already exposes every character's name to any tenant member regardless of who can see that character's other information/payload content, per [ADR 0028](0028-knowledge-and-group-membership.md)'s content-level, not existence-level, visibility split) - this endpoint doesn't introduce a new privacy boundary, only a new discovery path onto identity/roster facts that were already this un-gated elsewhere.

## Not in scope

- Any change to `GET .../characters`'s own behavior, response shape, or the fact that it stays character-only.
- Surfacing `Information`/`Payload` content (descriptions, stats) on a being from this endpoint - it's a lean identity/picker shape, matching `CharacterSummaryOut`'s own restraint, not `v_character`'s fuller narrative view.

## Consequences

- New `routers/beings.py` (registered in `main.py`), `schemas/beings.py` (`BeingSummaryOut`).
- No migration - `being`/`character`/`entity` already exist; this is a pure read addition.
- Closes [issue #94](https://github.com/ramsesoriginal/lorenzo/issues/94).
