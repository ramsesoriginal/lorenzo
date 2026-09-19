# 0085 - Tenant data export: audit of existing reads, three small missing read endpoints, and a runbook

Status: proposed

## Context

Lorenzo is AGPL-3.0 ([ADR 0006](0006-agpl-3.0-license.md)) and meant to be self-hostable. The practical half of that promise is that a tenant owner can take **their own data** out - to back it up, to move to a self-hosted instance, or to leave. Nothing today says whether that is possible, and no document tells an owner how.

The obvious answer - a single "export my tenant" endpoint returning an archive - is the wrong first move. It would be an unbounded response on a request-scoped Cloud Run service ([ADR 0011](0011-deploy-target-cloud-run-neon.md)), it would need its own visibility rules duplicated from every read, and it would have to be kept in sync with every table added afterwards. Every tenant-scoped table is already reachable, or should be, through an authenticated, paginated, visibility-aware read ([ADR 0020](0020-rest-api-tenant-scoping-and-schemas.md)). So the question this ADR answers is narrower: **is every table an owner would want actually reachable through those reads, and if not, what is the smallest fix?**

## Decision

### Audit result

Checked against the tables and views under `apps/api/src/lorenzo_api/models` and the `GET` routes in `routers/`. "Reachable" means an authenticated read returns the table's content in a form an owner could store.

| Table | Reachable via | Status |
| --- | --- | --- |
| `tenant`, `membership` | `GET /tenants/{id}`, `.../memberships` | yes |
| `campaign`, `campaign_gm`, `player` | `.../campaigns`, `.../campaigns/{id}/gms`, `.../players` | yes |
| `character`, `being`, `character_player` | `.../characters`, `.../beings`, character detail's `players` | yes |
| `entity`, `item`, `item_instance` | `.../entities`, `.../items`, `.../item-instances` | yes |
| `ownership`, `containment` | item-instance `owner`, entity detail `children[]` | yes |
| `entity_prototype` | entity detail, `.../items/{id}/prototypes/ancestry` | yes |
| `group_member` | `.../groups`, `.../groups/{id}/members` | yes |
| `information`, `payload`, `payload_description` | entity detail's `information` (visibility-filtered) | yes, per entity |
| `payload_picture`, `payload_document` (bytes) | `.../payloads/{id}/content` | yes |
| `*_profile_picture`, `profile_picture` (bytes) | `.../picture` routes | yes |
| `audit_log` | `.../activity-log` (OWNER/ORGA after [ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md)) | yes |
| `entity_stat` | entity detail's `stats` - **effective** values (inherited included), not the entity's own rows | partial |
| `stat_group`, `stat_definition` | `GET` by id only - **no list**, so ids can't be discovered except from entity stats | **gap** |
| `knowledge` (who knows what) | none - visible only as a *filtering effect* on information reads | **gap** |
| `tenant_admin_campaign_opt_out` | none (`PUT`/`DELETE` only) | not exported, see below |
| `notification` | own rows only, `/me/notifications` | not exported, see below |
| `app_user` | global, not tenant data; roster/membership reads expose the fields tenant members can already see | not exported |
| `entity_stat_group`, `payload_number` | not confirmed from routers during this audit | **verify in the implementation slice** |

The last row is stated as unverified on purpose: this audit read routes and schema modules, not every serialization path. The implementation slice must settle each "verify" line with a real request before the runbook claims completeness.

### Three small read endpoints to add

- `GET /tenants/{id}/stat-groups` and `GET /tenants/{id}/stat-definitions` - paginated lists, same authorization as the existing `GET`-by-id routes in `routers/stats.py`. Closes the discoverability gap.
- `GET /tenants/{id}/knowledge` - paginated, **OWNER/ORGA only**, rows of `(information_id, entity_id, knower_entity_id | knower_player_id)`. A tenant-wide listing rather than a per-information `.../knowers` read, because information has no collection endpoint yet ([RFC 0015](../rfcs/0015-information-metadata-shape.md) proposes one) and a per-information walk would make an export do one request per row. No content is returned, ids only.

`entity_stat`'s effective-only exposure is left as is for now: the effective view is what the product shows, and adding a raw own-values read is worth doing only once someone needs to *re-import* rather than back up. Named as a limitation in the runbook, not fixed here.

### Deliberately not exported

- **`notification`**: a per-user inbox. An owner reading everyone's notifications is a privacy regression, not an export feature. Users export their own via `/me/notifications`.
- **`tenant_admin_campaign_opt_out`**: a per-admin personal preference, reproducible in one call.
- **`app_user`**: global identity, not tenant data.

### One open question, resolved during implementation

Reads are filtered by `information_visibility`. The bypass code documents its own bypass as **ORGA-only** and states that tenant OWNER is "deliberately not folded in" to GM-knowledge reachability. If that means a tenant OWNER who is not also ORGA silently receives *fewer* information rows than the data actually holds, an export made with an owner's token would be incomplete without saying so - the worst kind of export bug. The implementation slice must prove or disprove this with a test (an OWNER-only token reading a GM-only information row) and record the outcome as an addendum here. If it is real, the fix is a decision for this ADR's addendum, not a runbook footnote.

### The runbook

`docs/operations/exporting-your-tenant.md`: an ordered, copy-pasteable procedure - authenticate, then walk each table's read above with pagination, then fetch binary payloads and pictures, with the known limitations (effective stats, visibility filtering, per-entity information) stated up front. **Written with the implementation, not before it**: it documents endpoints and behavior that must exist and have been run, and a runbook that describes unbuilt endpoints is exactly the kind of prose this repo's docs discipline ([ADR 0070](0070-planning-milestones-issues-and-a-deferred-roadmap.md)) warns drifts.

## Not in scope

- A one-call archive/`.zip`/streaming export endpoint.
- Import. The runbook says what is exported, not how to load it elsewhere.
- Cross-tenant data (repositories, [docs/domain/repositories.md](../domain/repositories.md)) - not designed yet.
- A raw-own-values `entity_stat` read.

## Consequences

- Three read-only endpoints and their schemas/tests; no migration, no new table.
- The runbook doubles as the acceptance test: if a step can't be run end to end against a real tenant, the audit table above is wrong and gets corrected.
- The knowledge listing is the first endpoint that lists `knowledge` at all; because it returns ids only and is OWNER/ORGA-gated, it adds no way for a player to learn who knows what.
