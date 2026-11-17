# 0488 - Features and grants from the command line

Status: accepted (2026-11-17), decided with the maintainer, not built. Slice C8 of [RFC 0057](../rfcs/0057-the-command-line-for-game-systems.md).
Builds on [ADR 0454](0454-features-two-kinds-and-what-a-holder-has.md) to [ADR 0457](0457-the-features-slot-of-a-template.md), [ADR 0467](0467-an-award-by-the-holders-controller.md)
and [ADR 0468](0468-the-card-of-a-feature-shows-the-stats-a-template-names.md).

## Context

A feature is an entry of kind `feature`; an entry holds one as a `feature_instance`, awarded, granted by a rule, or picked from a rule's
choice. A grant rule sits on a source (an ancestor, or a held active thing), has conditions, a mode (`all` or `choose` with a minimum and a
maximum) and options; a feature has prerequisites. `grants/apply` takes picks, `dry_run` and a GM's `override`. The CLI has none of it.

## Decision

- **In the document**: an `[[entry]]` with `kinds = ["feature"]`, `repeatable`, `starts_inactive` and `prerequisites`
  (`[{stat, comparator, value | stat}]`); `[[grant_rule]]` `on`, `label`, `position`, `mode`, `min`, `max`, `count` (a stat), `options`
  (entries) or `option_category` (an entry), `lasts`, `changeable`, `conditions` (`[{subject, stat, comparator, value | stat}]`).
- **`lorenzo feature list [--system S]`** (the library's features), **`show FEATURE`** (its prerequisites, the rules that grant it),
  **`award FEATURE --to HOLDER`**, **`activate` / `deactivate FEATURE --on HOLDER`**, **`remove FEATURE --from HOLDER`** (a removal is a
  revocation; the record stays).
- **`lorenzo grant-rule list [--on ENTRY]`**, **`show`**, **`create --from FILE`**, **`delete`**; a rule is replaced whole, its source fixed.
- **`lorenzo grants show HOLDER`** prints four sections: held (with how each came: awarded, granted by a rule from a source, picked),
  due, open choices (each with its rule, source, minimum, maximum, what is picked and the numbered options) and orphaned (with the reason).
- **`lorenzo grants apply HOLDER`** follows [ADR 0482](0482-one-write-contract-for-every-cli-command.md): it asks the API for a dry run and
  shows what would be created and revoked and the open choices; without `--yes` it stops there, exit 2 if anything is due. At a terminal
  with `--yes` absent and choices open it asks each choice as a numbered list, checking the count against the rule. `--pick "RULE=OPTION"`
  (a rule by label or id, an option by name, slug or id; repeated, or `RULE=A,B` for several) answers choices for a script; an open
  choice with no pick is left open and reported, exit 2.
- **`--override`** (a GM's) is passed to the API, and the output names each prerequisite or count that was passed over, on its own line.
- The truncation the API reports (a chain deeper than its cap) is printed as a warning with the advice to apply again.

## Consequences

- A character's features can be granted, chosen and inspected from a terminal or a script, with the same rules as the apps.
- A GM's override is never silent.

## As built (slice C8)

- `--override` prints one warning that prerequisites and counts were not held to: the apply's answer does not list what was
  passed over, so naming each would need an API change.
- A grant rule is found by its entry and its `label`, so a rule in a document has a label. `grant-rule create --from FILE` creates
  one, or replaces the one with that entry and label.
- At a terminal `grants apply` asks each open choice `--pick` left; with `--yes`, `--json` or no terminal it asks nothing, and an
  open choice is left open (exit 2).
