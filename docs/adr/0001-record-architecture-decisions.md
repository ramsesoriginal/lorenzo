# 0001 - Record architecture decisions as ADRs

Status: accepted

## Context

Non-obvious decisions (why Postgres RLS instead of schema-per-tenant, why merge commits instead of squash, why AGPL) need to survive past the conversation or commit that made them — otherwise every new contributor (human or agent) re-litigates them from scratch.

## Decision

We record architecturally significant decisions as short ADRs in `docs/adr/`, using the template in [0000-template.md](0000-template.md). Numbered sequentially, never renumbered. Superseded ADRs stay in place with a status update pointing at the replacement.

## Consequences

Every non-obvious "why" question should be answerable by grepping `docs/adr/`. Decisions that are still open go through `docs/rfcs/` first; an ADR records something that's already been decided.
