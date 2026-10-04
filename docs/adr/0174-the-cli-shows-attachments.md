# 0174 - The CLI shows attachments, and a repository's authors can list theirs

Status: accepted

The CLI half of [RFC 0033](../rfcs/0033-item-repositories-common-equipment-rules-and-bridge.md)'s first slice, which [ADR 0172](0172-attachments-a-parent-a-bridge-adds-to-a-copy-travels-with-it.md) left out ("The CLI's view") and the API of ADR 0172 made possible. It builds on [ADR 0159](0159-lorenzo-repo-commands.md) and [0160](0160-lorenzo-repo-offer.md) (`lorenzo repo`), [ADR 0169](0169-seed-list-and-repo-contents.md) (`repo contents`), and adds one read-only route to the API, because the last of the commands below has nothing to read without it.

## Context

ADR 0172 made a parent a bridge adds to a copy travel with the copy and with `repo updates`. The CLI can already call all of it, since its generated models carry the new fields, but it says nothing: `repo copy-plan` and `repo copy` don't count the attachments a step writes or list the ones dropped, `repo updates` doesn't show the three new lists and `--apply` never takes an attachment, and `repo contents` can't say what a repository attaches.

The last is not only a display. What a repository attaches is what its own copy links' snapshots do not list, and no route shows a snapshot, so an author has no way to ask "what will a table get from this beyond my own rows?". Counting it in the CLI from existing routes would mean guessing which parents arrived with a copy, which is the thing ADR 0172 settled by reading the snapshot.

## Decision

### The API: a repository's own attachments

```
GET /tenants/{tenant_id}/attachments
```

**Lists the attachments the tenant holds**: the parents it added to entities it holds copies of, as [ADR 0172](0172-attachments-a-parent-a-bridge-adds-to-a-copy-travels-with-it.md) defines them. Each entry is the `AttachmentRefOut` the updates already use, `{child_source_id, child_local_id, child_name, parent_source_id, parent_local_id, parent_name}`, here with both local ids set, since both rows are the tenant's own. Paginated like every list, and ordered by child name, then parent name.

- **Repository tenants only.** A play tenant is refused with the `409` that publishing and granting give it (`NotARepositoryError`): the word means something only for a repository, which is where a table's updates come from.
- **For any member of the tenant**, the tier of the other reads of a tenant's own data. It reads nothing of anyone else's, so the gated read isn't involved.
- **It reads little.** Entity names, prototype edges and the copy links, not the stats and payloads a full `load_content` brings.
- **No new table, no migration, no write.** It is `attachments_of` of ADR 0172, run over the tenant's own rows.

An additive change for `oasdiff` and the generated clients, which are regenerated.

### `lorenzo repo copy-plan` and `lorenzo repo copy`

- **A step's line counts its attachments**: "..., 3 attachments", left off when there are none, so a repository that attaches nothing reads as before.
- **A dropped one is listed like any other row** the copy leaves out, with the API's reason ("the item it attaches to isn't here", "the prototype it attaches isn't here", "it would make a prototype loop here"). Its source id is the child's origin id, as the API gives it.
- **`--json` is the API's answer**, so it carries the new fields already.

### `lorenzo repo updates`

Alone it shows, and says what it would take:

- **Added:** `added attachment “Economic Object” on “Weapon”`, and for one that can't be taken yet, why: `..., but it waits: the prototype it attaches isn't here`.
- **Gone upstream:** `gone upstream: attachment “Longsword 5e” on “Longsword”`, which can only be detached.
- **Deleted here:** counted, "N attachment(s) you removed here (nothing to do)", like the rows deleted here.
- **Exit code:** 2 when anything on the first two lists is there, the same rule as for rows, so a script that waits for "nothing new" waits for attachments too.

`--apply` takes what needs no decision, as for rows ([ADR 0159](0159-lorenzo-repo-commands.md)):

- **An added attachment that can be applied is taken.** So is one whose missing end is a row `--apply` is adding in the same call, because that is the case where taking the row and not its attachment would leave one more round to run. One whose end is neither here nor coming stays, and is said.
- **A removed attachment is left**, counted with the rows gone upstream: detaching is a decision, as it is for a row. It is detached by naming it in `--actions`.
- **`--actions FILE`** takes the API's own request. The file is a list of actions, or `{"actions": [...], "attachments": [...]}`, where an attachment is `{child_source_id, parent_source_id, action}` with `add` or `detach` ([ADR 0172](0172-attachments-a-parent-a-bridge-adds-to-a-copy-travels-with-it.md)).
- **The answer** keeps its sentence, "Took N changed, N added, N detached.", and adds one for attachments when there are any: "Attachments: N added, N detached." One that couldn't be applied is said with its reason, and stays on offer, as a field does.
- **`--json`** gains the attachments the apply left, next to what it already says it left.

### `lorenzo repo offer`

Its updates step uses the same choice: `--apply-updates` takes the applicable attachments with the clean rows, and the count of updates waiting for a decision includes the attachments added that can't be taken and the ones gone upstream. Its dry run counts them in "need no decision".

### `lorenzo repo contents`

Adds the attachments the repository holds, from the route above: "Attaches N parent(s) to items it copied" in the text, left off when there are none, and `holds.attachments` in `--json`, always, so a script has a number. It counts and doesn't list; the route does.

### Tests

- Unit tests of each command's output and of the choice of what `--apply` takes, over the same mock transport as the others, including an attachment whose end is added in the same call and one whose end is not coming.
- An end-to-end test against the real API on the stack of RFC 0033: `copy-plan`, `copy`, `updates` and `updates --apply` with attachments, a detach through `--actions`, and `repo contents` of the bridge.
- At the API, with Postgres: the route lists a bridge's three attachments with both ends' names and ids, lists none for what arrived with a copy, drops one whose edge the author removed, and refuses a play tenant and anyone who isn't a member.

## Not in this ADR

- **Naming the item in a dropped attachment.** The API reports it by the child's origin id, like every dropped row.
- **Taking an attached repository back off a tenant.** A later command, as ADR 0172 says.
- **Showing on a table's item which repository each parent came from.** RFC 0033's later list.

## Consequences

- **An author can answer "what will a table get beyond my rows?"** from the CLI, and a person who copies a bridge sees the parents it adds to what they already hold before they say yes.
- **One route more in the API**, for a read that couldn't be made from the others. It is small, and it is the author-side counterpart of the three `attachments_*` lists a subscriber gets.
- **`--apply` takes more than before** where a bridge attaches to rows it is also adding. That is what "needs no decision" already meant for the rows, and it is what a person would have run `--apply` twice to get.
- **Output grows only where there is something to say.** A repository with no attachments prints what it printed before, apart from `holds.attachments: 0` in JSON.
