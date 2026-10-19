# 0309 - Calendar period entries, minimal Events and date associations

Status: accepted, decided with the maintainer on 2026-10-19. Builds on ADR 0308.

## Context

A calculated calendar must also support notes on a particular day, descriptions of a year,
and imported story events. The maintainer explicitly chose period entries in the first slice.

## Decision

A `calendar_period` component gives an entry a calendar-relative year, segment-in-year or day
identity. Its coordinate uses calendar id, signed year, granularity, stable segment key and
day as applicable; database uniqueness rejects duplicate coordinates. Materialization is an
explicit write: a day creates/reuses its year and segment parents atomically. Concurrent calls
return the same period identity. Browsing calculates empty periods without creating rows.
Period hierarchy is structural, never containment or prototype inheritance. The definition's
repeating segment is distinct from a segment period in a particular year.

A `story_event` marker is a minimal entry kind, shown as Event. It adds no order key, clock,
participant or happened/expected status. A tenant-scoped `entry_calendar_period` n:m relation
associates an entry (including an Event or existing Fact) with materialized periods. An
association means only associated with; it is not a validity interval, a learning event,
causal evidence, or proof of existence at that date. Multiple selected days are not implicitly
a continuous span. A month-only association does not invent a day. Marker combinations stay
explicitly bounded by the repository kind matrix; no physical kind combinations are added.

Ordinary dated notes are Information on one period entry, with ordinary ordered payloads and
explicit audiences. There is no information-to-period join or generic dated-content wrapper.
A note on a year/month does not inherit to its days. Existing Facts remain canonical anchors,
with About independent of date associations and LorenzoScript links.

Structured period coordinates require both calendar and period outer visibility. Entry-date
links require visibility of the associated entry, period and calendar; reading either end
never opens the other. Inner Information audiences still apply. Hidden links do not affect
returned counts, pagination, summaries, previews or placeholders. Authoring needs existing
standing and visible targets. New temporal entries have explicit restricted outer audiences;
the app may deliberately broaden them. Existing administrative opt-outs remain effective.

Calendar and period locks serialize materialization and definition edits. Updates that would
invalidate periods are refused; display-name changes preserve stable coordinates. Referenced
period/calendar deletion is refused with no hidden id/count disclosure. Whole-tenant deletion
must still work. Date links are versioned on their source entry; races cannot discard another
association. No operation silently changes current containment, ownership or knowledge.

The kind API, generic entry reads, exports, slugs, previews and ancestry recognize the new
kinds consistently. Copies remap all ids, materialized parent links and date associations;
missing targets are reported. Public release reads apply the same visibility. Existing copied
relation policy applies: associations are copied once rather than silently synchronized.

## Validation

Concurrent day materialization; period coordinates and invalid dates; month-only and multi-day
Event associations; Fact dates without temporal truth semantics; independent outer/inner
visibility; cross-tenant targets; conditional writes; invalidating edits; copy/release remapping;
purge and whole-tenant deletion. No new query joins on existing inventory reads.

## Not in scope

Causal ordering, participations, history, clocks, timeline variants, and multiple dates for an
ordinary Information row. Minimal Events do not accept RFC 0028's order-core candidate.
