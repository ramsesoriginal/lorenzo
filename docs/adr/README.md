# Architecture Decision Records

Numbered sequentially, never renumbered. Superseded ADRs stay in place with a status update pointing at the replacement — see [0001](0001-record-architecture-decisions.md).

- [0000 - Template](0000-template.md)
- [0001 - Record architecture decisions as ADRs](0001-record-architecture-decisions.md)
- [0002 - Multi-tenancy: shared schema + PostgreSQL row-level security](0002-multi-tenancy-shared-schema-rls.md)
- [0003 - Polyglot monorepo tooling](0003-polyglot-monorepo-tooling.md)
- [0004 - Web frontends are static Astro sites](0004-static-astro-frontend.md)
- [0005 - Git branching and merge strategy](0005-git-branching-and-merge-strategy.md)
- [0006 - License: AGPL-3.0](0006-agpl-3.0-license.md)
- [0007 - apps/ layout: one directory per deployable app, multiplicity per type](0007-apps-layout-and-multiplicity.md)
- [0008 - Background jobs and rate limiting: taskiq + fastapi-limiter, deferred](0008-deferred-taskiq-and-fastapi-limiter.md)
- [0009 - Identity provider: Authgear (self-hosted OIDC)](0009-identity-provider-authgear.md)
- [0010 - User, tenant, and membership model](0010-user-tenant-membership-model.md)
- [0011 - Deploy target: Google Cloud Run + Neon](0011-deploy-target-cloud-run-neon.md)
- [0012 - The entity table](0012-entity-table.md)
- [0013 - Tenant table bootstrap](0013-tenant-table-bootstrap.md)
- [0014 - Stats: definitions, groups, and per-entity values](0014-stats.md)
- [0015 - entity_prototype: the inheritance graph](0015-entity-prototype.md)
- [0016 - Containment: the generic entity-to-entity physical relation](0016-containment.md)
- [0017 - Information and payloads](0017-information-and-payloads.md)
- [0018 - SQLAlchemy modeling conventions: type map, relationships, cascades](0018-sqlalchemy-modeling-conventions.md)
