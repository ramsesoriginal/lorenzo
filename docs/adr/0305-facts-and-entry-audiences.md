# 0305 - Facts, their subjects and an entry's outer audience

Status: accepted, decided with the maintainer on 2026-10-16. Slice of RFC 0044.

## Context

A canonical fact is a tenant-wide statement about the world, represented as an information
anchor with its own entry identity. Its existence and name may be secret. Information audiences
alone cannot provide that boundary: entity lists, link resolution and relationship summaries
currently expose identity independently of information.

## Decision

A `fact` marker gives an entry its kind, through the existing kind API. The initial slice
supports standalone facts; combinations with mechanical kinds are not enabled until their
semantics and repository matrix are proven. Facts carry ordinary information, text and pictures.
`fact_about(fact_entity_id, subject_entity_id, tenant_id)` is an optional many-to-many relation,
independent of LorenzoScript links. An entry may concern several subjects, and need concern none.

`entity_audience(entity_id, tenant_id, is_public, updated_at)` is the outer gate.
No row preserves an existing entry's access rules. A new fact has a restricted row.
`entity_knowledge` names its character/group or Player recipients, with the same exactly-one
knower shape as information knowledge. The two audiences remain independently explicit.
The gate applies to both existence and displayed name; there is no separate secret-name field.

Initially only facts expose audience changes. The shared gate is not enabled as a user control
for beings, catalog items or inventory instances in this slice. A hidden physical object's
containment and aggregate effects need the later decision already named in RFC 0044.

### Enforcement and roles

Entry reads use a restrictive SELECT policy in addition to tenant isolation. It preserves the
existing resource gates and filters before SQL pagination/counts. Information and payload reads
also require a visible containing entry, including binary content and cache revalidation.
A restricted entry is readable through explicit grants, by its applicable GMs, or by library
Owners/Organizers who have not opted out. Authors read facts as authored world content, alongside
the catalog; repository Authors continue to read all authored content. Group grants follow current
membership; Player grants keep the existing tenant-wide union of campaign seats.

The SQL rule is security-invoker and does not bypass tenant RLS. Tests compare its behavior
against the established role/knower cases. Request-local user context is restored alongside
tenant context after a commit. All new tables force RLS and use composite same-tenant references.

The gated repository content read remains available to the copy engine. Public previews and
release-document reads that present entries to visitors filter the outer audience explicitly;
they do not treat a public inner description as permission to reveal a restricted fact.
No generated name, thumbnail, relation, count or placeholder identifies an inaccessible fact.
Authored prose and explicitly written link labels are not automatically redacted.

### Editing and subjects

An entry audience has edit-gated GET and atomic, versioned PUT operations analogous to ADR 0304.
Information sharing never changes it. A mismatch is explained, not silently repaired.
Adding and removing subjects requires standing over the fact and visibility of the subject.
Listing facts about a subject and listing a fact's subjects return only visible entries.

Bench creates facts in its existing explorer and edits their ordinary information in place.
An About picker and a quiet entry audience control extend the entry pane. Beings and inventory
show a small Facts about section and a reading page using their information renderer; no app is
added. Fact links resolve through the existing entry resolver.

### Repositories

Facts, entry audiences and entity-recipient grants travel with a copy, remapping entity ids.
Player seats are never imported as foreign recipients. About edges travel when both ends can
be mapped. They are copied once like information/knowledge, not silently offered as synchronized
relations. The release document retains the data and the kind matrix proves copy and purge;
public-facing counts and previews exclude restricted facts. Restricted facts with no imported
recipients remain restricted, readable by the destination's appropriate privileged authors/GMs.

## Consequences

Concealment is an entry-level rule, not a collection of UI exceptions. Existing entry access
and all inner audiences remain unchanged unless an explicit outer gate is introduced. Facts
reuse entity identity, notes, links and pictures without implementing epistemic judgments,
confidence, temporal learning or campaign relevance.
