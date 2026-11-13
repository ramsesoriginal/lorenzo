# 0461 - Warnings on the writes of a stat and of a formula

Status: accepted, built (2026-11-12). Slice V4 of [RFC 0055](../rfcs/0055-vocabulary-check.md), the last. Builds on
[ADR 0458](0458-the-vocabulary-check-route-and-its-first-findings.md),
[ADR 0459](0459-findings-an-unset-input-and-an-own-value-that-shadows-a-formula.md) and
[ADR 0460](0460-the-tie-finding-read-for-one-entry.md) (the findings), and
[ADR 0285](0285-api-reads-that-cost-what-they-read.md) (what a request may cost).

## Context

An author finds out that a write passed over a formula, left a stat without a value or went beyond a hint only by reading the check
afterwards. The write is the moment to say so, without refusing anything: an unset input and a shadowing value are legitimate while an
author is part-way through.

## Decision

- **`warnings=true`** on `PUT /entities/{id}/stats/{stat}`, `PUT` and `PATCH /entities/{id}/tags/{stat}` and
  `PUT /entities/{id}/computed-stats/{stat}`. The response then has `warnings`: the findings, in the shape of the check, of any
  severity, for the stat just written on the entry just written (`GET .../vocabulary-check?entry_id=&stat_definition_id=` with every
  code, a tie and the chain of formulas included). An empty list says the check ran and found nothing.
- **Without the parameter** the response is exactly as it was (no `warnings` key at all) and no check runs, so a stepper or a bulk
  script pays nothing. A test says the check's queries are not among the statements of a write that does not ask.
- **It refuses nothing and the write is made as before.** The check reads the entry after the write is committed. A write that is
  refused (a formula over a direct value, a bad body) answers its error as it did, with no warnings.
- **Cost.** A fixed number of statements, whatever the entry holds: the visibility of the caller, one entry's loading for the bulk
  read, its prototype walk and candidates, the names (a test bounds the difference at thirty).
- **The schemas.** `EntityStatWriteOut` and `ComputedStatOut` have an optional `warnings` that is left out of the answer when not
  asked for (`exclude_if` on the field), so no existing answer changes.

## Design

`warnings_for_write` in `vocabulary_check.py` runs the entry findings and the tie for the one entry and stat and the chain finding for
the stat, and the routes call it after their commit when asked.

## Validation and delivery

A test for each: a stat write with and without the parameter (and the value held either way, an empty list when nothing is found), the
tag writes, a formula write saying what it leaves unset and a value that shadows a formula said on its own write, the refused write
without warnings, and the statements with and without. The OpenAPI change is the optional query value and the optional field; the CLI
models and `packages/api-client` are regenerated.

## Not in scope

Warnings on the other writes (a bulk write, a relationship type's formula, a parents change); refusing a write because of a finding.

## Consequences

- RFC 0055 is built (ADR 0458 to 0461): one read and a word at the write, with nothing refused.
- A client that wants the word asks for it; everything else is as it was.
