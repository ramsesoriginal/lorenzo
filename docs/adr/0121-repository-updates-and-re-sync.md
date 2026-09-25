# 0121 - Repository updates and re-sync

Status: accepted

## Context

A copy never changes by itself ([ADR 0119](0119-copying-a-repository-into-a-tenant.md)). When a repository's author corrects a stat or adds an entity, [RFC 0024](../rfcs/0024-repositories.md) §7 wants subscribers told. It wants each update applied as a deliberate, reviewable act on one row, with a real diff, never a blanket "re-sync everything". Local additions are never touched, and a collision is always a choice.

The amendment's A7 replaces the RFC's timestamp comparison with snapshots. `entity_prototype` has no timestamps, and a stat change never moves `entity.updated_at`. Every copy link therefore records what was copied, with ids translated to their origins. That gives three versions of each row to compare:

- **base**: the snapshot, what was copied or last synced;
- **upstream**: the repository's row now;
- **local**: the subscriber's copy now.

## Decision

### Finding updates

`GET /tenants/{tenant_id}/repositories/{repository_id}/updates`, for any member of the subscribing tenant. It reads the repository through [ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)'s gated read, so the repository must still be granted and published. It returns:

- **`changed`**: one entry per copied entity, stat group, or stat definition whose upstream differs from its base. Each field that differs is shown with its base, upstream, and local values, marked as either:
  - **clean**, where local still equals base, so the upstream value can simply be taken;
  - **conflict**, where local changed too, to something else.
- **`removed`**: rows gone upstream. Shown, never deleted here; the only action is `detach`, which drops the link so the row stops being reported.
- **`deleted_locally`**: rows the subscriber deleted, whose link now has a null local id. Shown for completeness; nothing to apply.
- **`added`**: own rows of the repository with no link here. Each is shown with any collision it would hit, exactly as a first copy would (ADR 0119).

Rows copied with `mode = merged` are the subscriber's own rows, so they are never offered for update.

### The fields that are compared

| Row | Fields |
| --- | --- |
| entity | name, `in_public_catalog`, slug, each stat value, each formula, prototypes, stat groups |
| stat group | name, priority, `mandatory` |
| stat definition | name, group, enum values, value type |

- **Scalars** (a name, a value, a formula) are compared three ways, as above.
- **Sets** (prototypes, stat groups, enum values) are merged element by element, so they never conflict. Whatever upstream added is added, whatever upstream removed is removed, and whatever the subscriber added stays.
- **A changed value type** is shown but can't be applied, since the subscriber's values would have to be converted. It has to be changed by hand.

Information, payloads, containment, ownership, group membership, and knowledge are copied once and aren't compared, as RFC 0024 §6 already scoped.

### Applying

`POST /tenants/{tenant_id}/repositories/{repository_id}/updates`, same tier, one transaction. The body lists what to do, row by row:

- `{"kind": "entity", "source_id": …, "action": "apply", "keep_local": ["name"]}` takes upstream's value for every clean field, and for every conflicting field not named in `keep_local`. Naming a conflict in neither is refused with `409` and the conflicts listed.
- `{"kind": …, "source_id": …, "action": "add", "resolution": …}` copies an added row, exactly as ADR 0119 would, with a collision choice where one is needed.
- `{"kind": …, "source_id": …, "action": "detach"}` drops a removed row's link.

Anything not listed is left as it is. Once a row is applied, its snapshot becomes the upstream version, including the fields kept local. So the same difference isn't reported again, while a later upstream change still is. `repository_copy.synced_at` records the time. An applied row's references are re-targeted as in [ADR 0120](0120-bridge-repositories-and-dependency-manifests.md), and anything unresolvable is reported rather than stored. The formula-cycle check runs as in ADR 0119. The activity log records one entry per call, with counts.

### Being told

- **Publishing again notifies** every subscribing tenant's members (ADR 0118). That is the proactive signal RFC 0024 §7 asks for.
- **`GET /tenants/{tenant_id}/repositories` shows `published_at` beside `copied_at` and `synced_at`**, so a client can say "updated since your last sync" without computing a diff.

For a bridge, each repository in its manifest is checked and applied on its own route.

## Not in scope

- Updates to information, payloads, containment, ownership, group membership, and knowledge. They need their own links and snapshots first.
- Deleting a local row because it was removed upstream. It may be in use in a campaign, so that stays a manual act.

## Consequences

- An update is always a reviewed choice, and a subscriber's own edits are never overwritten without being named.
- Finding updates reads the whole repository and every link. It's fine at today's sizes and unmeasured at large ones, like the copy itself.
- Snapshots take space: one JSON document per copied row.
