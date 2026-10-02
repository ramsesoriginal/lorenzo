# 0150 - `lorenzo pack give` on the API, and a pack list in which every line links

Status: accepted

Slice 2 of [RFC 0032](../rfcs/0032-giving-a-pack-from-the-api.md) (§10). Builds on [ADR 0149](0149-giving-a-pack-from-the-api.md) (the route) and [ADR 0145](0145-pack-contents-in-the-description.md) (the list, and how the importer writes it).

## Context

`lorenzo pack give` reads a pack's list and makes one `POST /item-instances` per line, as ADR 0145 designed it. ADR 0149 does that in the API, as one transaction that refuses a pack it can't give whole, and refuses any line that doesn't link. The CLI should call it, and the importer should never write a line it would refuse.

## Decision

### The command

```text
lorenzo pack give PACK --tenant T --owner OWNER [--override] [--dry-run]
```

- **One call** to `POST .../item-instances/from-pack` (`operationId` `create_item_instances_from_pack`, in the CLI's `OPS` table). A POST isn't retried by the transport (ADR 0137), which is right for something that creates things. `--dry-run` is `?dry_run=true`.
- **`--owner` is required**: the slug or id of a being or a group. A pack goes to someone.
- **`--into` is removed.** The route puts a being's things in its hands and a group's in no container; there is nowhere else to put them. This is a breaking change to a pre-1.0 command, committed as one (`feat(cli)!` with a `BREAKING CHANGE` footer).
- **`--override`** is passed through. It is a GM's, and skips capacity.
- **Slugs** for the pack and the owner are resolved to ids with `GET .../entities/resolve`, as the CLI resolves every slug it is given. The API takes ids.
- **The answer is printed as a tree**, a line for each instance made, indented by what it is inside, `5 x Rations` where it has a count and the name alone where it doesn't (a group's top level). Then one line: `Gave N item(s)` or, with `--dry-run`, `Would give N item(s)`, as today's wording has it.
- **Refusals** are the API's: its `detail` already names the lines or the container, and is shown as any API error is, exit `1`.

`importer/give.py` shrinks to resolving the two slugs and making the call. What goes: reading and parsing the description, grouping lines, creating the container and then each child, the 50-loose guard, the `into` option.

### Every line links

The importer writes lists in which every line links, since the API refuses one that doesn't.

- **`"text"` stops being a `[pack_items]` disposition.** A row that says it fails to load, with the message that already lists the choices, now without it: `'item'` (a plain catalog item) or `'list:key'`. `Ref("text")` and the branch that built it are removed, so a pack entry resolves to an item of the run or to a plain one made for it, and never to nothing.
- **What the built-in map already does** is unchanged: its seven gaps are `"item"` (ADR 0146).
- **A pack written earlier with a line that doesn't link** is not rewritten. A description is written once, at first import (ADR 0145, 0121), and editing an existing one would need an edit path the importer doesn't have. The API's refusal names the lines, and editing the description is the fix.

### One grammar, two parsers

`apps/cli`'s parser, which stays (the importer's own tests prove what it writes reads back), runs `apps/api/tests/data/pack_lists.json`, the examples ADR 0149's parser runs. `.github/ci-graph.toml` gains `depends_on = ["apps/api"]` for `apps/cli`, so a change to the examples runs the CLI's tests (ADR 0148); its unit tests still need neither a running API nor a database.

## Not in scope

`--json`, a `--tenant`-less form, giving several packs in one call, and anything about how the importer resolves names (ADR 0144, 0146).

## Consequences

- The CLI has one place that knows how a pack becomes instances, and it is the API's.
- `lorenzo pack give` for a being now puts things in its hands, which it never did: earlier it only set an owner.
- A script that passed `--into` or no `--owner` breaks, loudly: both are now errors from the option parser.
- The list writer and the API's parser can only drift apart as far as the shared examples allow.
