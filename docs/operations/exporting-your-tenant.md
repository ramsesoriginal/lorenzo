# Exporting your tenant

Lorenzo is [AGPL-3.0](../adr/0006-agpl-3.0-license.md) and meant to be self-hostable, so the data in a tenant is yours to take. There is deliberately no "download everything" button ([ADR 0085](../adr/0085-tenant-data-export-audit-and-runbook.md)): an archive endpoint would be an unbounded request on a request-scoped service, and would need its own copy of every visibility rule. The paginated reads below cover a play library's roster, inventory and visible information. A newer bulk entity export (ADR 0262) supplies the entry content an authoring mirror needs, but neither method is a database backup or a complete restore format.

`apps/api/tests/test_tenant_export_walk.py` performs this same walk against a populated tenant, page size of two, on every change. If a step here stops working, that test fails.

## Before you start

- **A bearer token** for the API, issued by Authgear or a personal access token (ADR 0268; see [local Authgear setup](local-authgear-setup.md); the `dev-token` script in `apps/api` fetches one for a local instance).
- **Your tenant id** (`GET /me` lists your memberships; `GET /me/managed` lists the tenants you run).
- **Read [what you will not get](#what-you-will-not-get) first.** Some of those limits can make an export look complete when it is not.

```bash
export API="https://your-api.example"      # or http://localhost:8000
export TOKEN="…"
export TENANT="00000000-0000-0000-0000-000000000000"

# Every list below is a page: {"items": [...], "total", "page", "size", "pages"}.
# Walk one, printing a JSON row per line. `size` is capped at 100.
walk() {
  local path="$1" page=1 pages=1 body
  while [ "$page" -le "$pages" ]; do
    body=$(curl -sfS -H "Authorization: Bearer $TOKEN" "$API$path?page=$page&size=100") || return 1
    printf '%s' "$body" | jq -c '.items[]'
    pages=$(printf '%s' "$body" | jq '.pages')
    page=$((page + 1))
  done
}
```

## The walk

Save each result to its own file (`walk /tenants/$TENANT/campaigns > campaigns.jsonl`).

| Table(s) | Read | Shape |
| --- | --- | --- |
| `tenant` | `GET /tenants/$TENANT` | one object |
| `membership` | `/tenants/$TENANT/memberships` | page |
| `campaign` | `/tenants/$TENANT/campaigns`, then `/campaigns/{campaign}` | list is a summary (id, slug, name, system); the detail has the rest |
| `campaign_gm` | `/tenants/$TENANT/campaigns/{campaign}/gms` | **plain list**, per campaign |
| `player` | `/tenants/$TENANT/campaigns/{campaign}/players` | page, per campaign |
| `character`, `character_player`, `being` | `/tenants/$TENANT/characters`, `/beings`, then `/characters/{id}` | lists are summaries (id, name, is-PC); the character detail has the owner and the roster |
| `entity` | `/tenants/$TENANT/entities`, then `/entities/{id}` | list includes kinds and parent ids; see below |
| `item`, `entity_prototype` | `/tenants/$TENANT/items` | page; each row lists its direct `prototype_ids`, and `/items/{id}/prototypes/ancestry` resolves the whole chain |
| `item_instance`, `ownership`, `containment` | `/tenants/$TENANT/item-instances` | page; each row carries its owner, container, quantity and prototypes |
| `group_member` | `/tenants/$TENANT/groups`, `/groups/{group}/members` | groups: page; members: **plain list**, per group |
| `stat_group` | `/tenants/$TENANT/stat-groups` | page |
| `stat_definition` | `/tenants/$TENANT/stat-definitions` | page |
| `knowledge` | `/tenants/$TENANT/knowledge` | page (ids only) |
| `audit_log` | `/tenants/$TENANT/activity-log` | page |

Two of these return a bare JSON array instead of a page (`.../gms` and `.../groups/{group}/members`); use `curl … | jq -c '.[]'` for them rather than `walk`.

### Details and information: one at a time

For every campaign in `campaigns.jsonl` fetch `/tenants/$TENANT/campaigns/{campaign}`, and for every character in `characters.jsonl` fetch `/tenants/$TENANT/characters/{id}`; the lists above are summaries.

Information arrives inside each entity's detail. There is also a paginated, visibility-filtered `/tenants/$TENANT/entities/{id}/information` read (ADR 0109). To use the detail walk, for every id in `entities.jsonl`:

```bash
curl -sfS -H "Authorization: Bearer $TOKEN" "$API/tenants/$TENANT/entities/$ENTITY_ID"
```

The detail carries that entity's information (visibility-filtered, see below), its stats, and its children. Descriptions are inline; a `picture` or `document` payload carries a `url` instead of its bytes.

### Binary content

- **Payload pictures and documents**: fetch each payload's `url` (`/tenants/$TENANT/payloads/{payload}/content`) with your token.
- **Profile pictures** (`/tenants/$TENANT/picture`, `.../campaigns/{campaign}/picture`, `/users/{user}/picture`): no token needed; they are served unauthenticated so a plain `<img>` can load them ([ADR 0056](../adr/0056-profile-pictures.md)).

## What you will not get

State these to yourself before trusting an export.

1. **An administrator who has opted out of a campaign's secrets sees only what a player would.** A tenant `OWNER` or `ORGA` reads GM-only information ([ADR 0096](../adr/0096-owner-joins-orga-in-the-information-visibility-bypass.md)), *unless* they hold a campaign admin opt-out ([ADR 0034](../adr/0034-campaign-crud-api.md)) - and that opt-out suppresses the bypass tenant-wide, not just for the one campaign. If you have opted out of any campaign, either remove the opt-out (`DELETE .../campaigns/{campaign}/admin-opt-out`) for the duration of the export, or export with a different administrator's token. A quick check: the count of `information` rows an entity returns to you should match what its GM sees.
2. **The detail walk reads effective stats.** They include inherited values, now with provenance (ADR 0276). Use the bulk export below for direct stored values by definition id; formulas have their own reads and are not included in that export.
3. **Stat-group membership is real state.** Stat writes can acquire a group (ADR 0142), and the bulk export includes `stat_group_ids`. A detail-only walk does not preserve that relationship exactly.
4. **Not exported, on purpose:** notifications (each person's own inbox; read yours at `/me/notifications`), other users' global account data, and each admin's personal campaign opt-outs.

## Bulk entry content

`GET /tenants/$TENANT/entities/export` ([ADR 0262](../adr/0262-bulk-entity-export.md)) returns cursor pages of `items`, `revision` and `next_cursor`. It includes each entry's kinds, link name, ordered parents, acquired stat groups, direct stored stat values by definition id, and the information the caller may read. Picture/document payloads still point to authenticated binary reads.

```bash
curl --compressed -sfS -H "Authorization: Bearer $TOKEN" \
  "$API/tenants/$TENANT/entities/export?limit=100" > entries-page-1.json
```

Continue with `cursor` set to the returned `next_cursor` until it is null. URL-encode the cursor (for example with curl's `--get --data-urlencode`). Every page must have the same `revision`; a `409` means content or visibility changed and the export must restart. The first page supports `If-None-Match`/`304`, and `--compressed` asks for gzip. The numbered-page `walk()` helper above does not apply to this route.

This is entry content, not every table of a library. Export the stat vocabulary, formulas, ownership, containment, campaigns and roster through their separate reads, and likewise what the Calendars, Sessions and Maps apps keep beside their entries (periods, scenes, placements and the like). Repository profiles, grants, copy snapshots and release history likewise need their own routes; neither this export nor the old walk reconstructs the complete repository update machinery. Use a database backup for a complete instance restore.

## Keeping an export honest

`total` on every page is authoritative. After a walk, the number of rows you saved should equal it. If you export while people are still playing, run the walk twice and compare `audit_log` between the two: anything logged in between changed under you.

## See also

- [ADR 0085](../adr/0085-tenant-data-export-audit-and-runbook.md): why this is a walk and not an endpoint, and the audit behind the table.
- [ADR 0020](../adr/0020-rest-api-tenant-scoping-and-schemas.md): pagination and tenant scoping.
