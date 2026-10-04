# 0172 - Attachments: a parent a bridge adds to a copy travels with it

Status: accepted

The first slice of [RFC 0033](../rfcs/0033-item-repositories-common-equipment-rules-and-bridge.md), decided with the maintainer on 2026-10-04. It amends [ADR 0119](0119-copying-a-repository-into-a-tenant.md), [ADR 0120](0120-bridge-repositories-and-dependency-manifests.md) and [ADR 0121](0121-repository-updates-and-re-sync.md), and the list of what a bridge carries in [RFC 0024](../rfcs/0024-repositories.md) A8.

## Context

A bridge holds copies of its dependencies and authors on top of them. ADR 0120 says what it carries to a subscriber: its own rows, re-targeted onto the subscriber's copies, and nothing it did to its copies of somebody else's. "To make an upstream entity behave differently under a system, the bridge authors a new entity that inherits from it."

RFC 0033 wants the opposite for one thing. A rules repository's prototypes (Longsword 5e, Economic Object) should be **attached** to the equipment's own items (Longsword, Weapon), so that a tenant holding the equipment gets the rules added to the items it already has, and no item is defined twice. An attachment is a parent added to an entity the repository holds a copy of. Today it works inside the bridge and goes no further: a table that already held the equipment took the bridge, got the bridge's prototype attached to nothing, and its Longsword was unchanged. Nothing said so.

What makes this safe to carry is already recorded. Every copy link keeps a snapshot of its entity as it was copied or last synced, with every id translated to its origin, and the snapshot includes the entity's prototypes ([ADR 0119](0119-copying-a-repository-into-a-tenant.md), [0121](0121-repository-updates-and-re-sync.md)). The parents a copy has beyond its snapshot are, by construction, the ones the repository's authors added.

## Decision

### What an attachment is

For an entity a repository holds as a copy, an **attachment** is a parent it has now that its copy link's snapshot does not list. It is the pair *(the entity's origin id, the parent's origin id)*.

- **The parent may be the repository's own entity or another repository's copy**, including one that came from the same repository as the child. Nothing about whose edge it is has to be guessed: what arrived with a copy is in the snapshot, and what is beyond it was added by the repository's authors.
- **Only additions.** A parent the repository removed from a copy is an edit to the copy, and does not travel.
- **Authors make one with what exists**, `PUT /tenants/{tenant_id}/items/{entity_id}/prototypes` on the copy. There is no new write route.
- **A parent the dependency adds later** enters the snapshot at the next sync, and the pair stops being an attachment: it now arrives as the dependency's own change.

### In a copy

After a step plans a repository's own rows, it plans the repository's attachments:

- It finds the subscriber's local row for the child and for the parent through the origin both copies share ([ADR 0120](0120-bridge-repositories-and-dependency-manifests.md)): the subscriber's own links first, then what this plan copies. The dependency may be one the subscriber already held, one an earlier step of the same manifest copies, or the repository's own entity copied in this step.
- With both found, it plans an `entity_prototype` row between them (none if the edge is already there) and a link for the attachment.
- With either missing (the subscriber skipped it or deleted it), that one attachment is **dropped and reported**, as any row whose target is missing is: kind `attachment`, source id the child's origin id, and the reason "the item it attaches to isn't here" or "the prototype it attaches isn't here".
- The edges are written after the step's entities, **one at a time, each in a savepoint**, because `entity_prototype`'s trigger refuses a loop ([ADR 0015](0015-entity-prototype.md)). A loop drops that one attachment with the reason "it would make a prototype loop here", the same as an update already does.
- **Counted.** `CopyStepOut` gains `attachments`, the edges the step wrote, so a plan and a dry run show them.

### Recording it

A new table, `repository_copy_link_attachment`:

| Column | |
| --- | --- |
| `tenant_id` | the subscriber, with the tenant's RLS (`FORCE ROW LEVEL SECURITY`, [ADR 0002](0002-multi-tenancy-shared-schema-rls.md)) |
| `source_tenant_id` | the repository the attachment came from |
| `child_source_id`, `parent_source_id` | the pair, as origin ids; plain ids, like `repository_copy.repository_tenant_id`, with no key to a local row |
| `copied_at` | |

The primary key is all four of `tenant_id`, `source_tenant_id` and the two ids. One row is kept for each attachment a tenant took, whether the copy wrote the edge or it was already there. The table is copy bookkeeping, not repository content, so it goes in the "not content" list of `repository_access` ([ADR 0118](0118-repository-tenants-subscriptions-and-a-gated-read.md)), and the tests that fail on a table missed from either list cover it. Without it, a later removal could not be told from an edge the tenant added itself.

### In updates

Changed and added **fields only**: no existing enum is widened, so the change is additive for `oasdiff` and for the generated clients.

- **`UpdatesOut`** gains `attachments_added`, `attachments_removed` and `attachments_deleted_locally`. Each entry is `{child_source_id, child_local_id, child_name, parent_source_id, parent_local_id, parent_name}`, with the local ids null where the tenant has no such row. An added entry also says whether it can be applied now, `applicable` and a `reason`.
  - **Added:** an attachment the repository has now and the tenant has no link for. That includes one dropped at the copy because an end was missing, which becomes applicable once the end is there.
  - **Removed:** a link whose attachment the repository no longer has, because it dropped the edge, or the child, or the parent, or the dependency now carries the parent itself.
  - **Deleted locally:** a link whose edge the tenant removed while both rows are still there.
- **`ApplyUpdatesRequest`** gains `attachments`: `{child_source_id, parent_source_id, action}` with `add` or `detach`. `add` writes the edge and the link. `detach` drops a removed attachment's link and leaves the edge, as `detach` does for any row. Entities are added before attachments in the same call, so an attachment can point at a row added in that call.
- **`ApplyUpdatesOut`** gains `attachments_added` and `attachments_detached`. An attachment that can't be applied is a `not_applied` entry with kind `attachment`, field `prototypes` and the reason, and keeps being offered.
- **Never a conflict.** A parent is an element of a set, and ADR 0121 merges sets element by element. A tenant's own parents on an item stay.
- **Never deleted by an update.** A `removed` attachment is only offered `detach`. Taking D&D off a tenant is not what updating does, as with any copied row.

### Keeping and purging a copy

`again: keep` ([ADR 0119](0119-copying-a-repository-into-a-tenant.md)) deletes the repository's attachment links and leaves the edges. `again: purge` deletes the edges those links recorded too, and counts them under `also_removed["attachment"]`. An edge whose parent a purge deletes still goes with that entity and is counted as it was.

### What a copy contributed

`ContributionCountsOut` gains `attachments`, the number the tenant took from the repository. The listing of contributed rows is unchanged, and `ContributionOut.kind` keeps its three values.

### What does not change

- **Everything else a bridge does to a copy stays in the bridge**: a stat value, a name, a description, a removed parent. ADR 0120's two bullets of what a bridge doesn't carry, edits to its copies and rows between two copied entities, each get an exception for an added parent and keep the rest, and so does RFC 0024 A8. Containment, ownership and every other row between two copies still stay.
- **Nothing is live.** Attachments reach a tenant by copy or by `repo updates`, when the tenant chooses, through the same gated read, so RFC 0024's "curated, reviewed composition over live pass-through" holds.
- **Grants, manifests and collisions** are as ADR 0119 and 0120 have them. An attachment has no name or slug to collide on.
- **Authorization** is the tier of a copy and of updates: any member of the subscribing tenant.

### Tests

At the API, with a real Postgres, in the style of the existing repository tests:

- A copy carries an attachment whose parent is the bridge's own entity and one whose parent is another repository's copy, onto the table's own rows, and a plan and a dry run count them.
- The order does not matter: a table that takes the equipment first and the bridge later, one that takes the bridge first (the manifest copies the equipment before it), and one that holds both.
- An attachment with the child or the parent missing is dropped and reported; one that would make a loop is dropped with its reason, and the rest of the copy goes ahead.
- Updates: an attachment the bridge adds later is offered and applied; one it removes is offered `detach`; one the tenant removed is shown as deleted locally; applying twice changes nothing; an entity and an attachment to it are added in one call.
- `keep` and `purge`, with the counts.
- The stack of RFC 0033: a core repository, equipment, a rules repository over core, and a bridge over the equipment and the rules, with the economic prototype attached to a form and a system prototype attached to an item, taken by a table that held the equipment first.
- Isolation and RLS of the new table, the "not content" list, and the OpenAPI diff showing only additions. The generated clients (`packages/api-client` and the CLI's models) are regenerated.

## Not in this ADR

- **The CLI's view.** `copy-plan`, `copy`, `updates` and `repo contents` show attachments in a follow-up, in `apps/cli`, once the API has them.
- **Taking a repository's attachments back off a tenant.** A later command.
- **Resolving through a campaign's game system.** RFC 0033 §9 makes the data available and leaves the resolution to its own RFC.

## Consequences

- **A system can be added to what a tenant already has.** The equipment is usable on its own, and taking the bridge later adds the rules to the same items, which is what RFC 0033 is for.
- **Two repositories can attach the same pair.** There is one edge and two links. Purging one removes the edge, and the other's next update offers it again.
- **A bridge's author has a new power over subscribers' items**, to add a parent to an item the subscriber copied from somebody else. It is bounded the way any bridge row is: it arrives by copy or by an update the tenant applies, it is shown first in a plan or a diff, and it adds a prototype and nothing else.
- **A parent the dependency later adds on its own** turns a bridge's attachment into a no-op that is offered as `removed`, to be detached. That is accurate and a little noisy.
- **ADR 0119, 0120 and 0121 and RFC 0024 A8 carry addenda** pointing here.
