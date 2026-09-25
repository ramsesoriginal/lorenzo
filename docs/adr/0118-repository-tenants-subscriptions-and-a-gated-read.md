# 0118 - Repository tenants, subscription grants, and a gated read

Status: accepted

## Context

[RFC 0024](../rfcs/0024-repositories.md) makes a repository an ordinary tenant that nobody plays a live game in, and lets other tenants read it once its owner grants them access. The read has to cross the RLS boundary that [ADR 0002](0002-multi-tenancy-shared-schema-rls.md) draws around every tenant. The RFC's amendment (A1) narrows when that happens: only inside a request that browses, plans, copies, or diffs a repository, never during play.

This ADR is the foundation: what makes a tenant a repository, how access is granted, how the read works, and what a subscriber can look at before copying anything. The copy itself is [ADR 0119](0119-copying-a-repository-into-a-tenant.md).

## Decision

### A tenant is either for play or a repository

- **`tenant.kind`**, an enum, `play` (the default) or `repository`. `POST /tenants` accepts it, behind the same `tenant-creator` role as any tenant ([ADR 0033](0033-tenant-creation-and-update-api.md)). `TenantOut` shows it, and `GET /tenants` takes an optional `?kind=` filter.
- **It never changes.** A trigger rejects any update to it. Publishing always means creating a new tenant, so a live play tenant can't be relabelled into a repository.
- **A repository holds no campaigns.** A trigger on `campaign` refuses a row in a repository tenant, and `POST .../campaigns` answers `409 repository-has-no-campaigns` before it gets that far. Players, GM grants, and invite links all hang off a campaign, so none of them can exist either.
- **Authoring is membership.** Whoever holds a Membership in a repository tenant edits its content through the same routes as anywhere else. Its OWNERs grant access and publish.

### Published or draft

- **`tenant.published_at`**, null while the repository is a draft.
- `PUT /tenants/{tenant_id}/published` publishes (OWNER only) and `DELETE` withdraws it. Both answer `409 not-a-repository` on a play tenant.
- Publishing again sets a new `published_at`. That is how an owner announces an update: every subscribing tenant's members get a notification ("Faerûn has published an update"). The first publish notifies nobody but the tenants already granted.
- A draft is invisible to every subscriber, whatever grants exist.

### The grant

`repository_subscription (repository_tenant_id, subscriber_tenant_id, created_at, created_by)`, primary key on the pair.

- **It can only point at a repository.** A trigger checks that `repository_tenant_id` is a `kind = 'repository'` tenant, and a CHECK refuses a tenant subscribing to itself. The subscriber may be either kind; a repository that subscribes to others is a bridge ([ADR 0120](0120-bridge-repositories-and-dependency-manifests.md)).
- **Its own RLS.** Either side reads it. Only the repository side inserts it (`WITH CHECK (repository_tenant_id = app.tenant_id)`). Either side deletes it.
- **The repository's OWNER grants.** `PUT /tenants/{tenant_id}/subscribers/{subscriber_tenant_id}` grants, `DELETE` revokes, and `GET /tenants/{tenant_id}/subscribers` lists them, for any member. A grant names the subscriber by id, which its members pass to the repository's owner themselves. That fits RFC 0024's unlisted-only scope (§8), and there is no listing of repositories to browse. The subscriber's members are notified of a new grant.
- **The subscriber sees and can drop it.** `GET /tenants/{tenant_id}/repositories` lists the repositories granted to a tenant, with each one's name, description, and `published_at`, for any member. `DELETE /tenants/{tenant_id}/repositories/{repository_id}` removes the grant, OWNER only. Removing a grant never touches what a copy already produced (RFC 0024 §6).
- **The activity log** records grants, revocations, and publishing in the repository tenant, and removing a grant in the subscriber's ([ADR 0084](0084-activity-log-coverage-and-member-removal-notice.md)).

### The gated read

One function holds the whole rule:

```sql
CREATE FUNCTION repository_read_tenant_id() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT s.repository_tenant_id
  FROM repository_subscription s JOIN tenant t ON t.id = s.repository_tenant_id
  WHERE s.repository_tenant_id = NULLIF(current_setting('app.repository_tenant_id', true), '')::uuid
    AND s.subscriber_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    AND t.kind = 'repository' AND t.published_at IS NOT NULL
$$;
```

It returns the repository's id only when the request asked to read it, the current tenant holds a grant, and the repository is published. Otherwise it returns null. Each content table gets a second policy beside `tenant_isolation`:

```sql
CREATE POLICY repository_read ON entity FOR SELECT
  USING (tenant_id = (SELECT repository_read_tenant_id()));
```

- **Wrapped in `SELECT`** so Postgres runs it once per query, as an init plan, not once per row.
- **`FOR SELECT` only.** Writes still go through `tenant_isolation` alone, so a repository row can never be written from outside it.
- **Asked for, never ambient.** Only one helper, `repository_access.reading_repository(session, repository_id)`, sets `app.repository_tenant_id`. It is a context manager that clears it again on the way out. The routes in this ADR, and ADR 0119's to 0121's, are the only callers. No gameplay request ever sets it, so `v_effective_stat` and every other query that relies on RLS alone never see a repository row.
- **The tables:** `entity`, `item`, `item_instance`, `being`, `character`, `entity_prototype`, `entity_slug`, `stat_group`, `stat_definition`, `stat_definition_enum_value`, `entity_stat_group`, `entity_stat`, `computed_stat`, `computed_stat_linear`, `computed_stat_comparison`, `containment`, `ownership`, `group_member`, `information`, `payload`, `payload_description`, `payload_number`, `payload_picture`, `payload_document`, `knowledge`, and `content_reference`. ADR 0119's copy-record tables join them. Tables relative to a player, a campaign, or tenant administration never do (RFC 0024 §4).

### Browsing before copying

For any member of the subscribing tenant, and only while the repository is published (a `404` otherwise):

- `GET /tenants/{tenant_id}/repositories/{repository_id}/entities` pages the repository's entities, with an optional `q` name filter. Each carries its name, its kinds (`item`, `item_instance`, `being`, `character`), and its prototypes' ids.
- `GET /tenants/{tenant_id}/repositories/{repository_id}/stat-groups` lists its stat groups, each with its definitions.

Browsing shows structure, not text. What a subscriber can read of a repository's information is decided when it's copied, by the ordinary visibility rules.

### Tests

For every table in the list, the RLS suite asserts, directly against the database:

- with the setting unset, a repository's rows are invisible even with a grant;
- with it set and no grant, or with a grant but unpublished, still invisible;
- with it set, a grant, and published, visible to `SELECT`;
- `INSERT`, `UPDATE`, and `DELETE` of a repository's rows are rejected or touch nothing.

A test also fails if a table with `tenant_id` and RLS is neither in the list nor in the named list of exclusions, so a new table can't slip past the decision.

## Consequences

- A tenant can now read another tenant's rows. It is narrow (read-only, one repository at a time, granted, published, and only in the requests that ask), but it is a real hole in ADR 0002's wall, and the test suite is what keeps it that narrow.
- Every surface that lists tenants has to decide what to do with repositories. The API marks them with `kind`. `apps/account-hub` and `apps/inventory-web` show them like any other tenant until they're taught otherwise. That's harmless, since repository authors use those screens to edit content, but "Create campaign" will refuse there.
- Granting by tenant id is plain, not friendly. A proper request-and-approve flow, or invite links like [ADR 0092](0092-campaign-invite-links.md)'s, can replace how a grant is created without changing what a grant is (RFC 0024 §8).
