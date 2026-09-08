# 0013 - Tenant table bootstrap

Status: accepted

## Context

The parallel "simple inventory management" vertical slice ([ADR 0012](0012-entity-table.md), on `feat/inventory-management`) needed `entity.tenant_id` to reference a real table rather than stay a bare, FK-less column indefinitely. Building [ADR 0010](0010-user-tenant-membership-model.md)'s full Tenant model (name, owner, the rest of User/Membership) isn't in scope for either branch yet — that's real work for when the auth/users slice actually starts. This is deliberately just enough to unblock the other branch's FK reference now, rather than leaving it dangling until this branch catches up on its own schedule.

Numbered 0013, not 0012, even though 0012 is the next free number from this branch's own history: `feat/inventory-management` already claimed 0012 for the entity table. Using 0012 here too would collide the moment these branches merge — the exact kind of conflict this bootstrap exists to avoid elsewhere.

## Decision

`tenant`: just `id` (UUID, server-generated `gen_random_uuid()`, primary key). No name, no owner, no other columns, no RLS (a tenant isn't tenant-scoped by itself). No ADR-0010-shaped fields yet — those land when auth/users actually builds Tenant/User/Membership for real, at which point this migration gets extended (not replaced; the table already exists and other tables already reference it).

## Consequences

- `feat/inventory-management` can now add a real `entity.tenant_id REFERENCES tenant.id` foreign key instead of a bare, unconstrained UUID column.
- A bare `tenant` row has no other meaning yet — it's not usable for anything auth/users-shaped until that slice adds the rest.
- This migration will need a follow-up (`ALTER TABLE tenant ADD COLUMN ...`) once the real Tenant model is built - expected and fine, not a sign this bootstrap was wrong.
