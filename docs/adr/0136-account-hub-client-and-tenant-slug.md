# 0136 - account-hub: shared API client and tenant slug editing

Status: accepted

## Context

Issue #276 is ADR 0122's deferred account-hub migration. The user also requested tenant slug editing and small improvements in touched account-hub flows. ADR 0033 / RFC 0012 already define slug changes, uniqueness, validation, and tenant-wide administrative access; the API supports them today.

## Decision

- Migrate every account-hub request to `@lorenzo/api-client`, with generated schema aliases, shared bearer-token handling and problem-detail errors. Keep app-specific DOM and presentation in account-hub (ADR 0080). Preserve multipart uploads and empty responses.
- On the tenant page, owners and organizers can edit the tenant slug through the existing PATCH route. Read the current tenant before editing, show a labelled required slug field with format guidance, Save and Cancel, and send its returned `ETag` as `If-Match`. A stale edit requires reopening the editor; collisions and other refusals show the API's message. Changing the slug leaves the name unchanged. Explain that links using the previous slug will stop resolving.
- Scope small improvements to errors, accessible controls, and correctness in touched flows. This does not introduce new permissions or repository management screens.
- Add real-API browser coverage for the slug workflow using the existing fake Authgear approach (ADR 0114), alongside migration regression coverage. The API remains the authority on permissions and slug validity.
- Account-hub's Pages build watch paths include the shared API client and brand package it consumes.

## Implementation finding

The tenant PATCH already checks `If-Match`, but the detail response exposed neither an ETag nor the timestamp needed to construct one. Add an `ETag` header to GET /tenants/{tenant_id}, using the existing `etag_for` helper (ADR 0042/0108). This closes the read-side gap without a database or response-body schema change. The editor refuses to proceed without a version. Real-API browser tests reuse inventory-web's local API/fake Authgear launchers on the same ports, run separately with a dedicated account-hub test database.

## Consequences

Account-hub joins the single generated schema and drift check. Slug editing needs no schema migration or new backend route. The migration is tracked by #276; the slug UI has its own checklist under this decision. The docs PR remains open for review independently of implementation.

