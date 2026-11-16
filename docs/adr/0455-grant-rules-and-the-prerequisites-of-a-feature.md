# 0455 - Grant rules, and the prerequisites of a feature

Status: accepted, built (2026-11-12). Slice F2 of [RFC 0054](../rfcs/0054-features-grants-and-choices.md). Builds on
[ADR 0454](0454-features-two-kinds-and-what-a-holder-has.md) (features and what a holder has),
[ADR 0451](0451-templates-a-sheet-as-data.md) (authoring at the vocabulary's tier, and how a row of content is copied),
[ADR 0104](0104-computed-stats.md) (the comparators), [ADR 0218](0218-the-copyable-table-registry.md) (the registry)
and [ADR 0208](0208-the-release-digest-and-the-breaking-change-detector.md) (the breaking reasons). Nothing is granted by this slice:
that is the apply of ADR 0456.

## Context

A class, a race or a boon says what a holder is entitled to ("at level 3, one of these"), and until now that was a chain of level
prototypes whose parent is swapped at each level-up, or a container with a capacity of two. This slice adds the data: the rules a
source carries and what a feature needs, with the routes that author them and the repository machinery that carries them.

## Decision

- **A rule hangs on a source entry** (any entry: a race, a class, an archetype, a feature, an item prototype). It says what the source
  entitles a holder to:
  - `mode`: `all` (every option is granted) or `choose` (the holder picks). A choose rule has `min_count` (0) and one maximum,
    `max_count` or, with `count_stat_definition_id`, that stat of the holder read when the rule is applied; an `all` rule has no
    count and is not `changeable`.
  - its options: an explicit list of features (in order), or `option_category_entry_id`, the features under that entry; not both,
    and not neither.
  - `conditions`, all of which must hold (an OR is a separate rule): `subject` (`holder` or `source`), a stat, a comparator
    (`lt le eq ne ge gt`, as the `comparison` formula has them), and a right side that is a constant or another stat of the same
    subject. A stat is an int, a float, a bool or an enum, read as a number as ADR 0444 has it; a text stat is a 422.
  - `lasts` (`while_source`, the default, or `permanent`), `changeable` (a pick of a choose rule may be swapped), `label`, and its
    place among its source's rules.
- **A feature has prerequisites**: the same comparisons, on the holder, which every rule that offers the feature respects. All of them
  must hold.
- **The routes** (the vocabulary's tier: any member of the library, an Author included, reads and writes; deleting a rule is an
  administrator's, as a template's is):
  - `GET /grant-rules` (a page, by source name then place; `entry_id` narrows it), `POST /grant-rules` (`entry_id` and the rule;
    appended unless `position` places it), `GET`, `PUT` and `DELETE /grant-rules/{id}`. A `PUT` replaces everything but the source.
  - `GET` and `PUT /features/prototypes/{feature}/prerequisites`: the whole list, in order; an empty list clears it.
  - 422 for an entry, option, category or stat that is not the library's (a hidden entry is answered as an unknown one, ADR 0437), an
    option that is no feature, a text stat, and the shapes above. A rule on an entry the library hides is not listed and is a 404.
    A hidden entry among the options or the category of a rule that is read is named `a hidden entry`, with no id (ADR 0454).
  - A stat a rule counts with or a condition reads, and one a prerequisite reads, is not deleted (409). A rule goes with its source
    and with its category entry, an option with its entry, a prerequisite with the feature kind (the keys cascade).
- **A repository carries them.** The release document moves to **format 44** (`grant_rules` and `prerequisites`; version 43 is read
  with none). A copy re-points the source, the options, the category and the stats to the library's rows; a rule whose category, count
  stat or condition stat was not copied, or none of whose options was, is left out and said (`dropped`, kind `grant_rule`), and an
  option not copied is left out of a rule that has others; a prerequisite on a stat that was not copied is left out and said. Only
  the entries a plan makes get rules: an entry the library already had (a merge) keeps its own. An update that adds an entry brings its
  rules. A purge of a copy takes the rules that read or are on what goes, and the prerequisites on it.
- **The rules update as an entry's field.** The snapshot of an entry carries `grant_rules` (and a feature `prerequisites`), said only
  when it has some, so an entry without any is hashed as before. An update proposes the field when it differs and applies it by
  replacing the entry's rules with the repository's in the repository's order, with what cannot be resolved here left out and said.
- **Removing a rule is breaking.** A release that gives an entry fewer rules than the last one has the reason `grant_rule_removed`
  beside `entity_removed` (the check is the count, since a rule has no identity across releases but its place; the detail names a
  label that went). Libraries that copied it keep the rule, and holders keep what it granted.

## Design

`grant_rule` (source `entry_id`, `label`, `position`, `mode`, `min_count`, `max_count`, `count_stat_definition_id`,
`option_category_entry_id`, `lasts`, `changeable`), `grant_rule_condition` (`rule_id`, `position`, `subject`, `stat_definition_id`,
`comparator`, `right_constant`, `right_stat_definition_id`), `grant_rule_option` (`rule_id`, `option_entry_id`, `position`) and
`feature_prerequisite` (`feature_id`, `position`, a comparison). Every key is composite with `tenant_id` (ADR 0117), each table has the
two policies of a content table with `FORCE ROW LEVEL SECURITY`, and checks hold the shapes (`mode`, `lasts`, `min_count <= max_count`,
one maximum for a choose rule and none for an all rule, one right side). The registry has the four (`grant_rule` and
`feature_prerequisite` counted on purge, the other two carried by the rule). The snapshot, the document and the planner treat a rule
as a record of names and ids in `Content.grant_rules`.

## Validation and delivery

A test for each: a rule of each mode made, read, listed, replaced and deleted, with its place; what must resolve and each shape that is
refused; a stat that is read and is not deleted; a rule going with its source and an option with its entry; the prerequisites replaced
whole and refused on a text stat; a copy bringing the rules and the prerequisites re-pointed; the release document round trip and the
version 43 reader; the digest's reason. The OpenAPI change is the new routes and `grant_rule_removed` (accepted in
`openapi-breaking-accepted.txt`: a response enum that grew); the CLI models and `packages/api-client` are regenerated.

## Not in scope

Granting, records, picks and revocation (ADR 0456); a rule edited in a library being merged with the repository's by the update, which
replaces the entry's rules as one field; a rule's identity across releases beyond its place.

## Consequences

- A class is one entry with conditional rules in place of a chain of level prototypes, and a feature says what it needs in one place.
- Four more tables, each needing the same care as the templates': RLS, a registry line, copy, purge and the document.
- A stat that a rule reads is one more thing that blocks deleting it, with the message that says so.
